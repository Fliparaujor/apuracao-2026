"""Base dos adaptadores de provedores de IA.

Cada adaptador oferece: verificação de configuração, teste de autenticação,
descoberta/validação de modelos, chat com resposta padronizada, tratamento de
HTTP 401/403/404/429/5xx, timeout, retry limitado com backoff e comunicação
exclusivamente HTTPS. Nenhum adaptador habilita faturamento.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from .. import config
from ..cotas import COTAS, Cancelamento, CotaExcedida, estimar_tokens

TIMEOUT_CHAT = 70
TIMEOUT_LISTA = 15


class ErroProvedor(RuntimeError):
    """Erro padronizado. `categoria` ∈ sem_chave, chave_invalida, sem_permissao,
    modelo_indisponivel, limite, pagamento, rede, formato, servidor, cancelado."""

    def __init__(self, categoria: str, mensagem: str, http: int | None = None, retry_after: float | None = None):
        super().__init__(mensagem)
        self.categoria = categoria
        self.http = http
        self.retry_after = retry_after


def _retry_after(headers, corpo: str) -> float | None:
    try:
        ra = headers.get("Retry-After") if headers else None
        if ra:
            return float(ra)
    except (TypeError, ValueError):
        pass
    m = re.search(r"try again in\s+([0-9.]+)\s*(ms|s|m)?", corpo or "", re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return v / 1000 if m.group(2) == "ms" else v * 60 if m.group(2) == "m" else v
    return None


def classificar_http(http: int, corpo: str, headers=None) -> ErroProvedor:
    resumo = config.mascarar(re.sub(r"\s+", " ", corpo or ""))[:160]
    if http in (401,):
        return ErroProvedor("chave_invalida", "Chave rejeitada pelo provedor (HTTP 401).", http)
    if http == 403:
        return ErroProvedor("sem_permissao", "Acesso negado pelo provedor (HTTP 403): conta sem permissão para este recurso.", http)
    if http == 402:
        return ErroProvedor("pagamento", "O provedor exigiu crédito/pagamento (HTTP 402); chamada interrompida.", http)
    if http == 404:
        return ErroProvedor("modelo_indisponivel", "Modelo ou rota inexistente para esta conta (HTTP 404).", http)
    if http == 429:
        return ErroProvedor("limite", "Limite gratuito atingido (HTTP 429). " + resumo, http, _retry_after(headers, corpo))
    if http in (400, 422):
        if re.search(r"api key not valid|API_KEY_INVALID|invalid api key|invalid_api_key|incorrect api key", corpo or "", re.IGNORECASE):
            return ErroProvedor("chave_invalida", f"Chave rejeitada pelo provedor (HTTP {http}: chave inválida).", http)
        return ErroProvedor("formato", f"O provedor rejeitou os parâmetros (HTTP {http}): {resumo}", http)
    if http >= 500:
        return ErroProvedor("servidor", f"Provedor instável (HTTP {http}).", http)
    return ErroProvedor("servidor", f"Resposta inesperada (HTTP {http}): {resumo}", http)


def requisitar(url: str, metodo: str = "GET", headers: dict | None = None, corpo: dict | None = None,
               timeout: int = TIMEOUT_CHAT, tentativas: int = 2) -> tuple[int, dict | list | str, dict]:
    """HTTPS JSON com retry limitado (5xx/timeout; 429 só com Retry-After curto)."""
    if not url.lower().startswith("https://"):
        raise ErroProvedor("formato", "Somente HTTPS é permitido para provedores de IA.")
    dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8") if corpo is not None else None
    cab = {"Accept": "application/json", "User-Agent": "Radar2026/3.0"}
    if dados is not None:
        cab["Content-Type"] = "application/json"
    cab.update(headers or {})
    ultimo: ErroProvedor | None = None
    for tentativa in range(max(1, tentativas)):
        req = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                bruto = resp.read(2_000_000)
                cabecalhos = dict(resp.headers.items())
                texto = bruto.decode("utf-8", "replace")
                try:
                    return resp.status, json.loads(texto) if texto.strip() else {}, cabecalhos
                except ValueError:
                    return resp.status, texto, cabecalhos
        except urllib.error.HTTPError as exc:
            corpo_erro = exc.read(4000).decode("utf-8", "replace") if exc.fp else ""
            erro = classificar_http(exc.code, corpo_erro, exc.headers)
            if erro.categoria == "servidor" and tentativa + 1 < tentativas:
                ultimo = erro
                time.sleep(1.5 * (tentativa + 1))
                continue
            if erro.categoria == "limite" and erro.retry_after and erro.retry_after <= 20 and tentativa + 1 < tentativas:
                ultimo = erro
                time.sleep(erro.retry_after + 0.5)
                continue
            raise erro
        except urllib.error.URLError as exc:
            ultimo = ErroProvedor("rede", "Falha de rede ao contatar o provedor: " + str(getattr(exc, "reason", exc))[:80])
        except (TimeoutError, OSError):
            ultimo = ErroProvedor("rede", "O provedor demorou demais para responder (timeout).")
        if tentativa + 1 < tentativas:
            time.sleep(1.5 * (tentativa + 1))
    raise ultimo or ErroProvedor("rede", "Falha desconhecida de rede.")


def texto_conteudo(conteudo) -> str:
    if isinstance(conteudo, str):
        return conteudo.strip()
    if isinstance(conteudo, list):
        return "\n".join(str(x.get("text", "")) for x in conteudo if isinstance(x, dict) and x.get("type") in (None, "text")).strip()
    return ""


class Provedor:
    id = "base"
    nome = "Base"
    variaveis: tuple[str, ...] = ()
    link_chaves = ""
    nota_gratuita = ""
    assentos_maximos = 1
    preferencias: list[str] = []          # ids exatos, em ordem
    padroes: list[str] = []               # regex de fallback, em ordem
    excluir: list[str] = []               # regex de exclusão
    url_modelos = ""
    url_chat = ""

    # ------------------------------------------------------------ utilidades
    def segredo(self, nome: str | None = None) -> str:
        return config.segredo(nome or self.variaveis[0])

    def configurado(self) -> bool:
        return all(config.segredo(v) for v in self.variaveis)

    def cabecalhos(self) -> dict:
        return {"Authorization": "Bearer " + self.segredo()}

    def filtrar_modelos(self, ids: list[str]) -> list[str]:
        """Ordena os modelos disponíveis conforme preferências e padrões; exclui os impróprios."""
        exc = [re.compile(p, re.IGNORECASE) for p in self.excluir]
        disponiveis = [m for m in ids if m and not any(e.search(m) for e in exc)]
        escolhidos: list[str] = []
        for pref in self.preferencias:
            if pref in disponiveis and pref not in escolhidos:
                escolhidos.append(pref)
        for padrao in self.padroes:
            rx = re.compile(padrao, re.IGNORECASE)
            for m in disponiveis:
                if rx.search(m) and m not in escolhidos:
                    escolhidos.append(m)
        preferido = config.carregar_config().get("modelos_preferidos", {}).get(self.id)
        if preferido and preferido in disponiveis:
            escolhidos = [preferido] + [m for m in escolhidos if m != preferido]
        return escolhidos

    # ------------------------------------------------------------ interface
    def listar_modelos(self) -> list[str]:
        """Descoberta real no provedor. Deve lançar ErroProvedor em falha."""
        raise NotImplementedError

    def autenticar(self) -> dict:
        """Testa a chave sem revelá-la. Nunca conclui 'autenticado' só por existir variável."""
        if not self.configurado():
            faltam = [v for v in self.variaveis if not config.segredo(v)]
            return {"ok": False, "estado": "sem_chave", "http": None, "modelos": [], "modelo": None,
                    "mensagem": "Sem chave configurada (" + ", ".join(faltam) + ").", "link": self.link_chaves}
        inicio = time.monotonic()
        try:
            ids = self.listar_modelos()
        except ErroProvedor as exc:
            estado = {"chave_invalida": "chave_invalida", "sem_permissao": "sem_permissao", "limite": "limite",
                      "pagamento": "pagamento", "rede": "rede"}.get(exc.categoria, "erro")
            return {"ok": False, "estado": estado, "http": exc.http, "modelos": [], "modelo": None,
                    "mensagem": config.mascarar(str(exc)), "link": self.link_chaves,
                    "duracao_ms": int((time.monotonic() - inicio) * 1000)}
        escolhidos = self.filtrar_modelos(ids)
        if not escolhidos:
            return {"ok": False, "estado": "modelo_indisponivel", "http": 200, "modelos": ids[:60], "modelo": None,
                    "mensagem": "Autenticação aceita, mas nenhum modelo de texto compatível foi encontrado nesta conta.",
                    "link": self.link_chaves, "duracao_ms": int((time.monotonic() - inicio) * 1000)}
        return {"ok": True, "estado": "autenticado", "http": 200, "modelos": escolhidos[:12], "modelo": escolhidos[0],
                "todos_modelos": len(ids),
                "mensagem": f"Autenticação aceita; {len(ids)} modelo(s) listados, {len(escolhidos)} utilizáveis.",
                "link": self.link_chaves, "duracao_ms": int((time.monotonic() - inicio) * 1000)}

    def montar_requisicao(self, modelo: str, mensagens: list[dict], max_tokens: int, temperatura: float) -> tuple[str, dict, dict]:
        """Retorna (url, cabeçalhos, corpo). Padrão: formato OpenAI chat/completions."""
        corpo = {"model": modelo, "messages": mensagens, "max_tokens": max_tokens, "temperature": temperatura, "stream": False}
        return self.url_chat, self.cabecalhos(), corpo

    def extrair_resposta(self, dados) -> tuple[str, dict]:
        """Retorna (texto, uso). Padrão OpenAI."""
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Resposta do provedor não é JSON.")
        escolhas = dados.get("choices") or []
        texto = texto_conteudo(((escolhas[0] if escolhas else {}).get("message") or {}).get("content"))
        uso = dados.get("usage") or {}
        return texto, {"entrada": uso.get("prompt_tokens"), "saida": uso.get("completion_tokens"),
                       "modelo_real": dados.get("model")}

    def conversar(self, modelo: str, mensagens: list[dict], max_tokens: int = 900, temperatura: float = 0.2,
                  cancelamento: Cancelamento | None = None, contexto: str = "") -> dict:
        """Chamada padronizada com cotas, fila, registro de uso e tratamento de erros."""
        from .. import db
        if not self.configurado():
            raise ErroProvedor("sem_chave", f"{self.nome} sem chave configurada.")
        texto_entrada = "\n".join(str(m.get("content", "")) for m in mensagens)
        tokens_est = estimar_tokens(texto_entrada) + max_tokens
        try:
            COTAS.reservar(self.id, tokens_est, cancelamento)
        except CotaExcedida as exc:
            raise ErroProvedor("limite", f"{self.nome}: {exc}")
        COTAS.adquirir_vaga(cancelamento)
        inicio = time.monotonic()
        http, erro_txt, ok = None, "", False
        try:
            if cancelamento:
                cancelamento.verificar()
            url, cab, corpo = self.montar_requisicao(modelo, mensagens, max_tokens, temperatura)
            http, dados, _ = requisitar(url, "POST", cab, corpo, timeout=TIMEOUT_CHAT)
            texto, uso = self.extrair_resposta(dados)
            if not texto:
                raise ErroProvedor("formato", "O modelo não devolveu texto utilizável.")
            ok = True
            COTAS.registrar(self.id, True)
            return {"texto": texto[:12000], "modelo": uso.get("modelo_real") or modelo, "provedor": self.id,
                    "tokens_entrada": uso.get("entrada") or estimar_tokens(texto_entrada),
                    "tokens_saida": uso.get("saida") or estimar_tokens(texto),
                    "duracao_ms": int((time.monotonic() - inicio) * 1000), "http": http}
        except ErroProvedor as exc:
            http = exc.http if exc.http is not None else http
            erro_txt = str(exc)
            COTAS.registrar(self.id, False, exc.http, exc.retry_after, erro=erro_txt)
            raise
        finally:
            COTAS.liberar_vaga()
            try:
                db.registrar_uso(self.id, modelo, ok, http, int((time.monotonic() - inicio) * 1000),
                                 estimar_tokens(texto_entrada), 0 if not ok else max_tokens, contexto, erro_txt)
            except Exception:
                pass

    def descricao(self) -> dict:
        return {"id": self.id, "nome": self.nome, "variaveis": list(self.variaveis), "link": self.link_chaves,
                "nota_gratuita": self.nota_gratuita, "assentos_maximos": self.assentos_maximos}
