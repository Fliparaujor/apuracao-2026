"""Camada 7 — diagnóstico automático e recuperação, sem expor credenciais."""
from __future__ import annotations

import platform
import sys
import time

from . import VERSAO, coletor, config, conselho, db, provedores, tse
from .cotas import COTAS


def _tse() -> dict:
    inicio = time.monotonic()
    try:
        snap = tse.obter("br", "presidente", 2, ttl=5)
        atual = tse.classificar_atualidade(snap)
        return {"ok": True, "estado": "acessivel", "horario_tse": snap["horario_tse"], "secoes_pct": snap["secoes_pct"],
                "votos_validos": snap["votos_validos"], "atualidade": atual, "fonte": snap["fonte"],
                "mensagem": "TSE acessível e boletim interpretado." if snap["votos_validos"] else "TSE acessível, mas ainda sem votos totalizados.",
                "duracao_ms": int((time.monotonic() - inicio) * 1000)}
    except tse.TSEIndisponivel as exc:
        estado = {"sem_dados": "sem_dados", "formato": "resposta_invalida"}.get(exc.categoria, "inacessivel")
        return {"ok": False, "estado": estado, "http": exc.http, "mensagem": str(exc), "fonte": tse.url_resultado("br"),
                "duracao_ms": int((time.monotonic() - inicio) * 1000)}


def executar(testar_ia: bool = True) -> dict:
    """'Testar tudo'. Nunca inclui o valor de nenhuma chave."""
    banco = db.verificar()
    try:
        contagem = db.contar_snapshots()
    except Exception as exc:  # noqa: BLE001
        contagem = {"total": 0, "erro": str(exc)[:120]}
    provs = provedores.autenticar_todos(forcar=True) if testar_ia else []
    status = provedores.status_consolidado()
    cadeiras = conselho.montar_cadeiras(status)
    tse_info = _tse()
    cfg_eleicoes = tse.descobrir_eleicoes()
    col = coletor.estado()
    ultimo_br = db.ultimo_snapshot("br")
    return {
        "versao": VERSAO, "gerado_utc": db.agora_utc(),
        "servidor": {"ok": True, "estado": "ativo", "python": sys.version.split()[0], "plataforma": platform.platform(),
                     "termux": "com.termux" in (sys.prefix or ""), "bind": config.carregar_config()["bind"],
                     "porta": config.carregar_config()["porta"]},
        "tse": tse_info,
        "eleicoes": {"codigos": {c: {"turno1": v["turno1"], "turno2": v["turno2"]} for c, v in tse.ELEICOES.items()},
                     "verificacao": cfg_eleicoes},
        "banco": banco | {"snapshots": contagem.get("total", 0), "por_escopo": contagem.get("por_escopo", [])[:40]},
        "segredos": {"arquivo": str(config.caminho_segredos()), "permissoes_ok": config.permissoes_segredos_ok(),
                     "configurados": [v for v in config.VARIAVEIS_SEGREDO if config.segredo_presente(v)]},
        "provedores": [{k: s[k] for k in ("id", "nome", "configurado", "origem_chave", "autenticado", "estado_autenticacao", "mensagem", "http", "modelo", "pronto", "cota")} for s in status],
        "conselho": {"modelos_prontos": cadeiras["total"], "provedores_distintos": cadeiras["provedores_distintos"],
                     "cadeiras": [{"papel_nome": c["papel_nome"], "provedor_nome": c["provedor_nome"], "modelo": c["modelo"]} for c in cadeiras["cadeiras"]],
                     "nao_prontos": cadeiras["nao_prontos"]},
        "coletor": {k: col.get(k) for k in ("ativo", "thread_viva", "ciclos", "consultas", "boletins_novos", "repetidos", "erros", "ultimo_ciclo_utc", "ultimo_boletim_novo_utc", "ultimo_erro", "governador_ufs", "governador_verificado", "pausado_s")},
        "ultima_atualizacao": {"horario_tse_br": ultimo_br.get("horario_tse") if ultimo_br else None,
                               "atualidade": tse.classificar_atualidade(ultimo_br) if ultimo_br else None},
        "cotas": COTAS.estado(),
    }


def texto(d: dict) -> str:
    """Versão copiável do diagnóstico, mascarada por segurança."""
    linhas = [f"Radar 2026 v{d['versao']} — diagnóstico {d['gerado_utc']}",
              f"Servidor: ativo · Python {d['servidor']['python']} · {'Termux' if d['servidor']['termux'] else d['servidor']['plataforma'][:40]} · {d['servidor']['bind']}:{d['servidor']['porta']}",
              f"TSE: {d['tse']['estado']} · {d['tse'].get('mensagem', '')}" + (f" · boletim {d['tse'].get('horario_tse')} · {d['tse'].get('secoes_pct')}% seções" if d['tse'].get('ok') else f" · HTTP {d['tse'].get('http')}"),
              f"Códigos de eleição: {d['eleicoes']['codigos']} · {d['eleicoes']['verificacao'].get('mensagem', '')}",
              f"Banco: {'funcional' if d['banco'].get('ok') else 'ERRO ' + str(d['banco'].get('erro'))} · {d['banco'].get('snapshots', 0)} snapshots",
              f"Segredos: arquivo {'com permissões corretas' if d['segredos']['permissoes_ok'] else 'COM PERMISSÕES ABERTAS'} · variáveis presentes: {', '.join(d['segredos']['configurados']) or 'nenhuma'}"]
    for p in d["provedores"]:
        estado = ("sem chave" if not p["configurado"] else p["estado_autenticacao"])
        linhas.append(f"- {p['nome']}: {estado}" + (f" · HTTP {p['http']}" if p.get("http") else "") + (f" · modelo {p['modelo']}" if p.get("modelo") else "")
                      + (" · PRONTO" if p["pronto"] else "") + (f" · {p['mensagem']}" if not p["pronto"] and p["configurado"] else ""))
    linhas.append(f"Conselho: {d['conselho']['modelos_prontos']} modelo(s) pronto(s) de {d['conselho']['provedores_distintos']} provedor(es)")
    c = d["coletor"]
    linhas.append(f"Coletor: {'ativo' if c.get('ativo') else 'parado'} · consultas {c.get('consultas')} · boletins novos {c.get('boletins_novos')} · repetidos {c.get('repetidos')} · erros {c.get('erros')}")
    u = d["ultima_atualizacao"]
    linhas.append(f"Última atualização (BR): {u.get('horario_tse_br') or '—'} · {(u.get('atualidade') or {}).get('rotulo', '')}")
    return config.mascarar("\n".join(linhas))
