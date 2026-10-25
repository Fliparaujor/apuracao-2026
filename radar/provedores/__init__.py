"""Registro dos provedores e visão consolidada de status (sem segredos)."""
from __future__ import annotations

import concurrent.futures
import time

from .. import config, db
from ..cotas import COTAS
from .base import Provedor, ErroProvedor
from .groq import Groq
from .gemini import Gemini
from .mistral import Mistral
from .openrouter import OpenRouter
from .cohere import Cohere
from .cloudflare import Cloudflare
from .huggingface import HuggingFace

PROVEDORES: dict[str, Provedor] = {p.id: p for p in (Groq(), Gemini(), Mistral(), OpenRouter(), Cohere(), Cloudflare(), HuggingFace())}
ORDEM = ["groq", "gemini", "mistral", "openrouter", "cohere", "cloudflare", "huggingface"]
_cache_auth: dict[str, tuple[float, dict]] = {}
TTL_AUTH = 10 * 60


def obter(ident: str) -> Provedor:
    if ident not in PROVEDORES:
        raise ValueError("Provedor desconhecido.")
    return PROVEDORES[ident]


def desativado_pelo_usuario(ident: str) -> bool:
    return ident in (config.carregar_config().get("provedores_desativados") or [])


def autenticar(ident: str, forcar: bool = False) -> dict:
    """Testa a chave de um provedor (com cache de 10 min) e persiste o resultado sem segredos."""
    p = obter(ident)
    agora = time.monotonic()
    hit = _cache_auth.get(ident)
    if hit and not forcar and agora - hit[0] < TTL_AUTH and hit[1].get("configurado") == p.configurado():
        return hit[1]
    resultado = p.autenticar()
    resultado["provedor"] = ident
    resultado["nome"] = p.nome
    resultado["configurado"] = p.configurado()
    resultado["origem_chave"] = config.origem_segredo(p.variaveis[0]) if p.variaveis else "ausente"
    resultado["testado_em_utc"] = db.agora_utc()
    if resultado["estado"] in ("chave_invalida", "sem_permissao"):
        COTAS.registrar(ident, False, resultado.get("http"), erro=resultado.get("mensagem", ""))
    elif resultado["estado"] == "limite":
        COTAS.registrar(ident, False, 429, erro=resultado.get("mensagem", ""))
    elif resultado["ok"]:
        COTAS.reativar(ident)
    _cache_auth[ident] = (agora, resultado)
    try:
        db.gravar_estado_provedor(ident, resultado)
    except Exception:
        pass
    return resultado


def autenticar_todos(forcar: bool = False, apenas_configurados: bool = True) -> list[dict]:
    alvos = [i for i in ORDEM if (PROVEDORES[i].configurado() or not apenas_configurados)]
    saida = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(autenticar, i, forcar): i for i in alvos}
        for f in concurrent.futures.as_completed(futs):
            try:
                saida.append(f.result())
            except Exception as exc:  # defensivo
                saida.append({"provedor": futs[f], "ok": False, "estado": "erro", "mensagem": config.mascarar(str(exc))[:160]})
    return sorted(saida, key=lambda r: ORDEM.index(r["provedor"]))


def status_consolidado(testar: bool = False) -> list[dict]:
    """Para cada provedor: configurado → autenticado → modelo disponível → pronto (cota ok)."""
    estado_cotas = COTAS.estado()["provedores"]
    saida = []
    for ident in ORDEM:
        p = PROVEDORES[ident]
        configurado = p.configurado()
        auth = None
        if configurado:
            if testar:
                auth = autenticar(ident)
            else:
                hit = _cache_auth.get(ident)
                auth = hit[1] if hit else db.ler_estado_provedor(ident)
        cota = estado_cotas.get(ident, {})
        autenticado = bool(auth and auth.get("ok"))
        modelo = auth.get("modelo") if auth else None
        bloqueado = bool(cota.get("desativado")) or cota.get("cooldown_restante_s", 0) > 0
        pronto = configurado and autenticado and bool(modelo) and not bloqueado and not desativado_pelo_usuario(ident)
        saida.append({
            "id": ident, "nome": p.nome, "link": p.link_chaves, "nota_gratuita": p.nota_gratuita,
            "variaveis": list(p.variaveis), "configurado": configurado,
            "origem_chave": config.origem_segredo(p.variaveis[0]) if p.variaveis else "ausente",
            "autenticado": autenticado, "estado_autenticacao": (auth or {}).get("estado", "nao_testado" if configurado else "sem_chave"),
            "mensagem": (auth or {}).get("mensagem", "Chave presente; ainda não testada." if configurado else "Sem chave."),
            "http": (auth or {}).get("http"), "modelo": modelo, "modelos": (auth or {}).get("modelos", []),
            "testado_em_utc": (auth or {}).get("testado_em_utc"),
            "cota": {k: cota.get(k) for k in ("hoje", "ultimo_minuto", "cooldown_restante_s", "motivo_cooldown", "desativado", "chamadas_ok", "chamadas_erro", "limites")},
            "desativado_pelo_usuario": desativado_pelo_usuario(ident), "pronto": pronto,
            "assentos_maximos": p.assentos_maximos,
        })
    return saida


def prontos() -> list[dict]:
    return [s for s in status_consolidado() if s["pronto"]]


def limpar_cache_auth(ident: str | None = None) -> None:
    if ident:
        _cache_auth.pop(ident, None)
    else:
        _cache_auth.clear()
