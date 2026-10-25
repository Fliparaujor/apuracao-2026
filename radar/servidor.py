"""Servidor HTTP local (stdlib) — interface, API e proteção dos segredos.

Bind padrão 127.0.0.1. Sem CORS aberto. Respostas JSON nunca contêm chaves.
Para HTTPS em hospedagem própria, coloque um proxy reverso na frente e mantenha
as chaves somente neste backend.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import signal
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import VERSAO, analista, coletor, config, conselho, db, diagnostico, evidencias, jobs, matematica, provedores, tse
from .cotas import COTAS

WEB = config.RAIZ_PROJETO / "web"
LIMITE_CORPO = 16 * 1024
_inicio = time.time()
_TOKEN_LAN = os.environ.get("RADAR_TOKEN", "").strip()


class ErroHTTP(Exception):
    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status


def _bool(valor, padrao=False) -> bool:
    if valor is None:
        return padrao
    return str(valor).lower() in ("1", "true", "sim", "s", "yes")


class Handler(BaseHTTPRequestHandler):
    server_version = "Radar2026/" + VERSAO
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ utilidades
    def log_message(self, fmt, *args):  # silencia caminhos; registra erros
        if self.command and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), config.mascarar(fmt % args)))

    def _cabecalhos_comuns(self, tipo: str, tamanho: int, cache: str = "no-store"):
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(tamanho))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def json(self, status: int, obj) -> None:
        dados = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self._cabecalhos_comuns("application/json; charset=utf-8", len(dados))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(dados)

    def arquivo(self, rel: str) -> None:
        caminho = (WEB / rel).resolve()
        if not str(caminho).startswith(str(WEB.resolve())) or not caminho.is_file():
            raise ErroHTTP(404, "Arquivo não encontrado.")
        dados = caminho.read_bytes()
        tipo, _ = mimetypes.guess_type(str(caminho))
        if caminho.suffix == ".webmanifest":
            tipo = "application/manifest+json"
        if caminho.suffix in (".js", ".mjs"):
            tipo = "text/javascript"
        tipo = tipo or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/json", "application/manifest+json", "image/svg+xml"):
            tipo += "; charset=utf-8"
        self.send_response(200)
        cache = "no-cache" if caminho.suffix in (".html", ".js", ".css", ".webmanifest") else "public, max-age=86400"
        self._cabecalhos_comuns(tipo, len(dados), cache)
        if caminho.suffix == ".html":
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; manifest-src 'self'; worker-src 'self'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(dados)

    def corpo_json(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho <= 0:
            return {}
        if tamanho > LIMITE_CORPO:
            raise ErroHTTP(413, "Mensagem muito grande.")
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ErroHTTP(415, "Envie application/json.")
        try:
            dados = json.loads(self.rfile.read(tamanho))
        except ValueError:
            raise ErroHTTP(400, "JSON inválido.")
        if not isinstance(dados, dict):
            raise ErroHTTP(400, "Envie um objeto JSON.")
        return dados

    def _autorizado(self) -> bool:
        """Em bind não-local, exige token simples (RADAR_TOKEN) nas rotas de IA/configuração."""
        if not _TOKEN_LAN:
            return True
        enviado = self.headers.get("X-Radar-Token") or urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("token", [""])[0]
        return enviado == _TOKEN_LAN

    # --------------------------------------------------------------- rotas
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            partes = urllib.parse.urlsplit(self.path)
            caminho, q = partes.path, {k: v[0] for k, v in urllib.parse.parse_qs(partes.query).items()}
            if caminho.startswith("/api/"):
                return self.json(*self.api_get(caminho, q))
            if caminho in ("/", "/index.html", "/ao-vivo.html", "/index"):
                return self.arquivo("index.html")
            if caminho == "/diagnostico.html":
                return self.arquivo("index.html")
            rel = caminho.lstrip("/")
            if not re.fullmatch(r"[A-Za-z0-9_\-./]{1,120}", rel) or ".." in rel:
                raise ErroHTTP(404, "Arquivo não encontrado.")
            return self.arquivo(rel)
        except ErroHTTP as exc:
            return self.json(exc.status, {"erro": str(exc)})
        except ValueError as exc:
            return self.json(400, {"erro": config.mascarar(str(exc))[:300]})
        except tse.TSEIndisponivel as exc:
            return self.json(503, {"erro": str(exc), "categoria": exc.categoria})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("Erro interno GET: %s %s\n" % (type(exc).__name__, config.mascarar(str(exc))[:200]))
            return self.json(500, {"erro": "Erro interno. Veja o diagnóstico."})

    def do_POST(self):
        try:
            caminho = urllib.parse.urlsplit(self.path).path
            if not caminho.startswith("/api/"):
                raise ErroHTTP(404, "Rota inexistente.")
            if not self._autorizado():
                raise ErroHTTP(401, "Token de acesso ausente ou inválido.")
            return self.json(*self.api_post(caminho, self.corpo_json()))
        except ErroHTTP as exc:
            return self.json(exc.status, {"erro": str(exc)})
        except ValueError as exc:
            return self.json(400, {"erro": config.mascarar(str(exc))[:300]})
        except RuntimeError as exc:
            return self.json(409, {"erro": config.mascarar(str(exc))[:300]})
        except tse.TSEIndisponivel as exc:
            return self.json(503, {"erro": str(exc), "categoria": exc.categoria})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("Erro interno POST: %s %s\n" % (type(exc).__name__, config.mascarar(str(exc))[:200]))
            return self.json(500, {"erro": "Erro interno. Veja o diagnóstico."})

    # ------------------------------------------------------------------ API
    def api_get(self, caminho: str, q: dict):
        if caminho == "/api/saude":
            return 200, {"ok": True, "nome": "Radar 2026", "versao": VERSAO, "uptime_s": int(time.time() - _inicio),
                         "coletor": coletor.estado()["ativo"], "hora_servidor_utc": db.agora_utc(),
                         "nota": "Este endpoint não indica autenticação de nenhum provedor de IA."}
        if caminho == "/api/estado":
            return 200, estado_geral()
        if caminho == "/api/resultado":
            escopo = tse.validar_escopo(q.get("escopo", "br"))
            cargo = tse.validar_cargo(q.get("cargo", "presidente"))
            return 200, resultado_escopo(escopo, cargo, _bool(q.get("agora"), False))
        if caminho == "/api/estados":
            return 200, estados()
        if caminho == "/api/governadores":
            return 200, governadores()
        if caminho == "/api/municipios":
            uf = tse.validar_escopo(q.get("uf", "ce"))
            try:
                return 200, {"uf": uf, "municipios": tse.municipios(uf)}
            except ValueError as exc:
                raise ErroHTTP(400, str(exc))
        if caminho == "/api/historico":
            escopo = tse.validar_escopo(q.get("escopo", "br"))
            cargo = tse.validar_cargo(q.get("cargo", "presidente"))
            lim = max(2, min(600, int(q.get("limite", "200") or 200)))
            hist = db.historico(escopo, cargo, 2, lim)
            return 200, {"escopo": escopo, "cargo": cargo, "boletins": len(hist), "evolucao": matematica.evolucao(hist),
                         "contadores": [c for c in db.contadores_coleta() if c["chave"] == f"{escopo}:{cargo}"]}
        if caminho == "/api/analise":
            escopo = tse.validar_escopo(q.get("escopo", "br"))
            cargo = tse.validar_cargo(q.get("cargo", "presidente"))
            try:
                p = evidencias.pacote(escopo, cargo)
            except tse.TSEIndisponivel as exc:
                return 503, {"ok": False, "erro": str(exc), "categoria": exc.categoria, "fonte": tse.url_resultado(escopo, cargo)}
            rel = p["relatorio"]
            rel["evidencia_texto"] = evidencias.compactar(p)
            return 200, rel
        if caminho == "/api/provedores":
            return 200, {"provedores": provedores.status_consolidado(testar=_bool(q.get("testar"), False)), "cotas": COTAS.estado()}
        if caminho == "/api/cotas":
            return 200, {"cotas": COTAS.estado(), "uso_24h": db.resumo_uso(24)}
        if caminho == "/api/conselho/status":
            return 200, conselho.status_publico()
        if caminho == "/api/conselho/historico":
            return 200, {"reunioes": conselho.historico(int(q.get("limite", "20") or 20), q.get("sessao"))}
        m = re.fullmatch(r"/api/conselho/reuniao/([0-9a-f]{12})", caminho)
        if m:
            job = jobs.obter(m.group(1))
            if not job:
                raise ErroHTTP(404, "Reunião não encontrada.")
            return 200, job
        m = re.fullmatch(r"/api/conversas/(\d+)", caminho)
        if m:
            c = db.obter_conversa(int(m.group(1)))
            if not c:
                raise ErroHTTP(404, "Conversa não encontrada.")
            return 200, c
        if caminho == "/api/analista/historico":
            return 200, {"conversas": analista.historico(int(q.get("limite", "20") or 20), q.get("sessao"))}
        if caminho == "/api/diagnostico":
            d = diagnostico.executar(testar_ia=_bool(q.get("ia"), True))
            d["texto"] = diagnostico.texto(d)
            return 200, d
        if caminho == "/api/config":
            cfg = config.carregar_config()
            return 200, {"config": cfg, "home": str(config.home()), "banco": str(config.caminho_banco())}
        raise ErroHTTP(404, "Endpoint inexistente.")

    def api_post(self, caminho: str, corpo: dict):
        if caminho == "/api/coletar":
            escopo = tse.validar_escopo(corpo.get("escopo", "br"))
            cargo = tse.validar_cargo(corpo.get("cargo", "presidente"))
            r = coletor.coletar_um(escopo, cargo)
            if not r["ok"]:
                return 503, {"ok": False, "erro": r["erro"], "categoria": r.get("categoria")}
            return 200, {"ok": True, "novo": r["novo"], "resultado": decorar(r["snapshot"])}
        if caminho == "/api/cenario":
            escopo = tse.validar_escopo(corpo.get("escopo", "br"))
            cargo = tse.validar_cargo(corpo.get("cargo", "presidente"))
            snap = evidencias.snapshot_atual(escopo, cargo)
            premissas = corpo.get("premissas") if isinstance(corpo.get("premissas"), dict) else {}
            return 200, matematica.cenarios(snap, premissas) | {"horario_tse": snap.get("horario_tse"), "fonte": snap.get("fonte")}
        if caminho == "/api/provedores/testar":
            ident = corpo.get("provedor")
            if ident:
                return 200, {"resultado": provedores.autenticar(str(ident), forcar=True)}
            return 200, {"resultados": provedores.autenticar_todos(forcar=True)}
        if caminho == "/api/provedores/reativar":
            ident = str(corpo.get("provedor", ""))
            provedores.obter(ident)
            COTAS.reativar(ident)
            provedores.limpar_cache_auth(ident)
            return 200, {"ok": True}
        if caminho == "/api/provedores/ativar":
            ident = str(corpo.get("provedor", ""))
            provedores.obter(ident)
            lista = set(config.carregar_config().get("provedores_desativados") or [])
            if _bool(corpo.get("ativo"), True):
                lista.discard(ident)
            else:
                lista.add(ident)
            config.gravar_config({"provedores_desativados": sorted(lista)})
            return 200, {"ok": True, "provedores_desativados": sorted(lista)}
        if caminho == "/api/analista/perguntar":
            escopo = tse.validar_escopo(corpo.get("escopo", "br"))
            cargo = tse.validar_cargo(corpo.get("cargo", "presidente"))
            return 200, analista.perguntar(escopo, str(corpo.get("pergunta", ""))[:600], cargo, str(corpo.get("sessao", ""))[:64],
                                           corpo.get("provedor") or None, _bool(corpo.get("sem_ia"), False))
        if caminho == "/api/conselho/reuniao":
            escopo = tse.validar_escopo(corpo.get("escopo", "br"))
            cargo = tse.validar_cargo(corpo.get("cargo", "presidente"))
            rodadas = corpo.get("rodadas")
            rodadas = int(rodadas) if isinstance(rodadas, (int, float, str)) and str(rodadas).isdigit() else None
            ident = conselho.iniciar_reuniao(escopo, str(corpo.get("pergunta", ""))[:600], cargo, str(corpo.get("sessao", ""))[:64], rodadas)
            return 202, {"id": ident, "status": "em_andamento"}
        if caminho == "/api/conselho/cancelar":
            return 200, {"cancelado": jobs.cancelar(str(corpo.get("id", "")))}
        if caminho == "/api/config":
            permitidas = {"coleta_automatica", "intervalo_coleta_segundos", "analise_automatica", "limites_sessao", "papeis_personalizados",
                          "modelos_preferidos", "rodadas_maximas", "escopos_prioritarios"}
            alteracoes = {k: v for k, v in corpo.items() if k in permitidas}
            if "intervalo_coleta_segundos" in alteracoes:
                alteracoes["intervalo_coleta_segundos"] = max(15, min(600, int(alteracoes["intervalo_coleta_segundos"])))
            if "escopos_prioritarios" in alteracoes:
                alteracoes["escopos_prioritarios"] = [tse.validar_escopo(e) for e in alteracoes["escopos_prioritarios"]][:12]
            cfg = config.gravar_config(alteracoes)
            if cfg.get("coleta_automatica"):
                coletor.iniciar()
            return 200, {"ok": True, "config": cfg}
        if caminho == "/api/cotas/reiniciar":
            COTAS.reiniciar_sessao()
            return 200, {"ok": True}
        raise ErroHTTP(404, "Endpoint inexistente.")


# ------------------------------------------------------------- montagens API

def decorar(snap: dict) -> dict:
    s = dict(snap)
    s["atualidade"] = tse.classificar_atualidade(snap)
    s["status_oficial"] = snap.get("status_oficial") or tse.status_oficial(snap)
    c = snap.get("candidatos") or []
    if len(c) >= 2 and snap.get("votos_validos"):
        s["diferenca_votos"] = int(c[0]["votos"]) - int(c[1]["votos"])
        s["diferenca_pp"] = round(float(c[0]["percentual"]) - float(c[1]["percentual"]), 2)
    return s


def resultado_escopo(escopo: str, cargo: str, agora: bool) -> dict:
    erro = None
    snap = None
    if agora:
        r = coletor.coletar_um(escopo, cargo)
        if r["ok"]:
            snap = r["snapshot"]
        else:
            erro = r
    if snap is None:
        snap = coletor.atual(escopo, cargo)
    if snap is None:
        if not agora:
            r = coletor.coletar_um(escopo, cargo)
            if r["ok"]:
                snap = r["snapshot"]
            else:
                erro = r
    if snap is None:
        return {"ok": False, "escopo": escopo, "cargo": cargo, "nome_escopo": tse.nome_escopo(escopo),
                "erro": (erro or {}).get("erro", "Sem dados."), "categoria": (erro or {}).get("categoria"),
                "fonte": tse.url_resultado(escopo, cargo), "mensagem": "O TSE ainda não publicou ou não respondeu; nenhum número é inventado."}
    anterior = evidencias.boletim_anterior(escopo, cargo, snap)
    d = decorar(snap)
    d["ok"] = True
    d["anterior"] = {"horario_tse": anterior.get("horario_tse"), "secoes_pct": anterior.get("secoes_pct"), "votos_validos": anterior.get("votos_validos"),
                     "candidatos": [{"numero": c.get("numero"), "percentual": c.get("percentual"), "votos": c.get("votos")} for c in anterior.get("candidatos") or []]} if anterior else None
    d["variacao"] = matematica.variacao(anterior, snap)
    d["diferencas"] = matematica.diferencas(snap)
    if erro:
        d["aviso_coleta"] = erro.get("erro")
    return d


def estados() -> dict:
    todos = coletor_ou_banco_estados()
    saida = []
    for uf in tse.UFS:
        s = todos.get(uf)
        if s:
            saida.append(decorar(s) | {"ok": True})
        else:
            saida.append({"ok": False, "escopo": uf, "nome_escopo": tse.NOMES_UF[uf], "candidatos": [], "votos_validos": 0, "secoes_pct": 0})
    nacional = coletor.atual("br")
    return {"estados": saida, "brasil": decorar(nacional) if nacional else None,
            "regional": matematica.regional({k: v for k, v in todos.items() if k in tse.UFS}, nacional) if todos else []}


def coletor_ou_banco_estados() -> dict[str, dict]:
    base = evidencias.estados_atuais("presidente")
    for uf in tse.UFS:
        s = coletor.atual(uf)
        if s:
            base[uf] = s
    return base


def governadores() -> dict:
    ufs = coletor.governador_ufs()
    saida = []
    for uf in ufs:
        s = coletor.atual(uf, "governador")
        if s:
            saida.append(decorar(s) | {"ok": True})
        else:
            saida.append({"ok": False, "escopo": uf, "nome_escopo": tse.NOMES_UF[uf], "cargo": "governador", "candidatos": [],
                          "mensagem": "Arquivo do TSE ainda não lido para esta UF."})
    est = coletor.estado()
    return {"ufs": ufs, "verificado_no_tse": est.get("governador_verificado", False),
            "sem_arquivo": est.get("governador_sem_arquivo", []), "incertas": list(tse.GOVERNADOR_2T_INCERTO), "disputas": saida}


def estado_geral() -> dict:
    br = coletor.atual("br")
    col = coletor.estado()
    return {"versao": VERSAO, "hora_servidor_utc": db.agora_utc(), "hora_brasilia": tse.agora_brasilia().isoformat(timespec="seconds"),
            "data_segundo_turno": tse.DATA_SEGUNDO_TURNO,
            "brasil": decorar(br) if br else None, "atualidade": tse.classificar_atualidade(br) if br else {"estado": "sem_dados", "rotulo": "Sem dados do TSE", "ao_vivo": False},
            "coletor": {k: col.get(k) for k in ("ativo", "ciclos", "consultas", "boletins_novos", "repetidos", "erros", "ultimo_ciclo_utc", "ultimo_boletim_novo_utc", "ultimo_erro", "pausado_s")},
            "eleicoes": {c: {"turno1": v["turno1"], "turno2": v["turno2"]} for c, v in tse.ELEICOES.items()},
            "escopos_prioritarios": config.carregar_config().get("escopos_prioritarios"),
            "municipios_padrao": tse.MUNICIPIOS_PADRAO, "ufs": tse.NOMES_UF,
            "ia": {"prontos": sum(1 for s in provedores.status_consolidado() if s["pronto"]),
                   "configurados": sum(1 for s in provedores.status_consolidado() if s["configurado"])},
            "cotas_sessao": {"chamadas": COTAS.estado()["chamadas_sessao"], "limite": COTAS.estado()["limite_sessao"]}}


# ------------------------------------------------------------------ servidor

class Servidor(ThreadingHTTPServer):
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # sem rastros de pilha no console do Termux
        import traceback
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, TimeoutError)):
            return
        sys.stderr.write("Erro de conexão: %s\n" % config.mascarar(traceback.format_exc().splitlines()[-1])[:200])


def criar_servidor(bind: str | None = None, porta: int | None = None) -> ThreadingHTTPServer:
    cfg = config.carregar_config()
    bind = bind or cfg["bind"]
    porta = int(porta if porta is not None else cfg["porta"])
    servidor = Servidor((bind, porta), Handler)
    servidor.daemon_threads = True
    return servidor


def preparar(iniciar_coleta: bool = True) -> dict:
    info = db.inicializar()
    try:
        tse.descobrir_eleicoes()
    except Exception:  # noqa: BLE001
        pass
    if iniciar_coleta:
        coletor.iniciar()
    return info


def main(argv: list[str] | None = None) -> int:
    cfg = config.carregar_config()
    bind, porta = cfg["bind"], int(cfg["porta"])
    info = preparar(iniciar_coleta=cfg.get("coleta_automatica", True))
    try:
        servidor = criar_servidor(bind, porta)
    except OSError as exc:
        print(f"Não foi possível abrir {bind}:{porta}: {exc}. Outro servidor já está rodando? Use PORT=8081.")
        return 2
    url = f"http://{'127.0.0.1' if bind in ('0.0.0.0', '::') else bind}:{porta}/"
    print(f"Radar 2026 v{VERSAO} — abra no Chrome: {url}")
    print(f"Banco: {info['caminho']} · segredos: {config.caminho_segredos()}")
    if bind not in ("127.0.0.1", "localhost") and not _TOKEN_LAN:
        print("AVISO: bind fora do localhost sem RADAR_TOKEN; qualquer aparelho na rede poderá acionar as IAs.")
    prontos = sum(1 for s in provedores.status_consolidado() if s["configurado"])
    print(f"Provedores com chave: {prontos} (a autenticação real aparece em Sistema → Testar tudo)")
    print("Mantenha o Termux aberto (termux-wake-lock ajuda). Para encerrar: CTRL+C")

    def encerrar(*_):
        print("\nEncerrando… histórico preservado em", info["caminho"])
        coletor.parar()
        threading.Thread(target=servidor.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, encerrar)
    signal.signal(signal.SIGTERM, encerrar)
    try:
        servidor.serve_forever(poll_interval=0.5)
    finally:
        servidor.server_close()
    return 0
