"""Pacote de evidências: tudo o que Analista e Conselho podem usar.

Reúne snapshot atual, boletim anterior, histórico, Brasil, UFs, 1º turno e os
cálculos determinísticos, com uma versão compacta em texto para caber nas
cotas gratuitas (ex.: ~8 mil tokens/min no Groq).
"""
from __future__ import annotations

import concurrent.futures

from . import db, matematica, tse


def snapshot_atual(escopo: str, cargo: str = "presidente", gravar: bool = True) -> dict:
    """Snapshot mais recente: consulta o TSE agora; se falhar, usa o último guardado (marcado)."""
    escopo = tse.validar_escopo(escopo)
    cargo = tse.validar_cargo(cargo)
    try:
        snap = tse.obter(escopo, cargo, 2)
        resultado = {"novo": False}
        if gravar:
            resultado = db.gravar_snapshot(snap)
            db.registrar_coleta(escopo, cargo, "novo" if resultado["novo"] else "repetido")
        snap["origem"] = "tse_agora"
        snap["boletim_novo"] = bool(resultado.get("novo"))
        return snap
    except tse.TSEIndisponivel as exc:
        if gravar:
            db.registrar_coleta(escopo, cargo, "erro", str(exc))
        ultimo = db.ultimo_snapshot(escopo, cargo, 2)
        if ultimo:
            ultimo["origem"] = "banco_local"
            ultimo["desatualizado"] = True
            ultimo["erro_tse"] = str(exc)
            return ultimo
        raise


def boletim_anterior(escopo: str, cargo: str, atual: dict) -> dict | None:
    hist = db.historico(escopo, cargo, 2, limite=5)
    for s in reversed(hist):
        if s.get("horario_tse") != atual.get("horario_tse") or s.get("votos_validos") != atual.get("votos_validos"):
            return s
    return None


def primeiro_turno(escopo: str, cargo: str = "presidente") -> dict | None:
    if cargo == "governador" and not tse.ELEICOES["governador"].get("turno1_verificado"):
        return None
    chave = f"primeiro_turno:{cargo}:{escopo}"
    ref = db.ler_referencia(chave)
    if ref and ref["dados"].get("totalizacao_final"):
        return ref["dados"]
    try:
        snap = tse.obter(escopo, cargo, 1)
    except (tse.TSEIndisponivel, ValueError):
        return ref["dados"] if ref else None
    db.gravar_referencia(chave, snap)
    return snap


def estados_atuais(cargo: str = "presidente") -> dict[str, dict]:
    todos = db.ultimos_por_escopo(cargo, 2)
    return {uf: s for uf, s in todos.items() if uf in tse.UFS}


def pacote(escopo: str, cargo: str = "presidente", incluir_estados: bool = True) -> dict:
    """Pacote completo (dicionários) usado pela API e para auditoria."""
    atual = snapshot_atual(escopo, cargo)
    anterior = boletim_anterior(escopo, cargo, atual)
    hist = db.historico(escopo, cargo, 2, limite=60)
    brasil = None
    if escopo != "br" and cargo == "presidente":
        try:
            brasil = snapshot_atual("br", cargo)
        except tse.TSEIndisponivel:
            brasil = None
    elif escopo == "br":
        brasil = atual
    estados = estados_atuais(cargo) if incluir_estados and cargo == "presidente" else {}
    primeiro = primeiro_turno(escopo, cargo)
    relatorio = matematica.relatorio_completo(atual, anterior, hist, estados or None, brasil, primeiro)
    return {"atual": atual, "anterior": anterior, "historico_n": len(hist), "brasil": brasil,
            "estados": estados, "primeiro_turno": primeiro, "relatorio": relatorio,
            "fonte": atual.get("fonte"), "horario_tse": atual.get("horario_tse"),
            "atualidade": tse.classificar_atualidade(atual)}


def _linha_cand(c: dict) -> str:
    return f"{matematica.nome_cand(c)} ({c.get('numero')}) {matematica.fmt_pct(c.get('percentual'))}% = {matematica.fmt_int(c.get('votos'))} votos"


def _bloco_snapshot(s: dict, titulo: str) -> str:
    linhas = [f"[{titulo}] {s.get('nome_escopo')} · {s.get('cargo_nome', 'Presidente')} · {s.get('turno')}º turno · boletim TSE {s.get('horario_tse')}",
              f"  seções totalizadas {matematica.fmt_pct(s.get('secoes_pct'))}% ({matematica.fmt_int(s.get('secoes_totalizadas'))}/{matematica.fmt_int(s.get('secoes_total'))}) · válidos {matematica.fmt_int(s.get('votos_validos'))} · brancos {matematica.fmt_int(s.get('brancos'))} · nulos {matematica.fmt_int(s.get('nulos'))} · comparecimento {matematica.fmt_int(s.get('comparecimento'))} · abstenção {matematica.fmt_int(s.get('abstencao'))}",
              f"  status: {s.get('status_oficial') or tse.status_oficial(s)}"]
    for c in (s.get("candidatos") or [])[:6]:
        linhas.append("  - " + _linha_cand(c))
    if s.get("desatualizado"):
        linhas.append("  ATENÇÃO: o TSE não respondeu agora; este é o último boletim guardado localmente.")
    return "\n".join(linhas)


def compactar(p: dict, max_estados: int = 27, incluir_calculos: int = 14) -> str:
    """Versão em texto, curta, para enviar aos modelos."""
    partes = [_bloco_snapshot(p["atual"], "ESCOPO")]
    if p.get("brasil") and p["brasil"] is not p["atual"] and p["brasil"].get("escopo") != p["atual"].get("escopo"):
        partes.append(_bloco_snapshot(p["brasil"], "BRASIL"))
    if p.get("anterior"):
        a = p["anterior"]
        partes.append(f"[BOLETIM ANTERIOR] {a.get('horario_tse')} · seções {matematica.fmt_pct(a.get('secoes_pct'))}% · válidos {matematica.fmt_int(a.get('votos_validos'))} · "
                      + " · ".join(_linha_cand(c) for c in (a.get("candidatos") or [])[:2]))
    if p.get("primeiro_turno"):
        f = p["primeiro_turno"]
        partes.append(f"[1º TURNO, {f.get('horario_tse')}, {matematica.fmt_pct(f.get('secoes_pct'))}% das seções, {matematica.fmt_int(f.get('votos_validos'))} válidos] "
                      + " · ".join(_linha_cand(c) for c in (f.get("candidatos") or [])[:6]))
    estados = p.get("estados") or {}
    if estados:
        linhas = []
        for uf in sorted(estados, key=lambda u: -(estados[u].get("eleitorado") or 0))[:max_estados]:
            s = estados[uf]
            cs = s.get("candidatos") or []
            if not s.get("votos_validos") or len(cs) < 2:
                continue
            linhas.append(f"{uf.upper()} seções {matematica.fmt_pct(s.get('secoes_pct'), 1)}% | " + " | ".join(f"{c.get('numero')}:{matematica.fmt_pct(c.get('percentual'), 1)}%" for c in cs[:2]))
        if linhas:
            partes.append("[UFs com votos — nº do candidato: % dos válidos]\n" + "\n".join(linhas))
    itens = [i for i in p["relatorio"]["itens"] if i["tipo"] in ("calculo", "limitacao")][:incluir_calculos]
    if itens:
        partes.append("[CÁLCULOS DETERMINÍSTICOS JÁ FEITOS]\n" + "\n".join(f"- ({i['tipo'].upper()}) {i['titulo']}: {i['texto']}" for i in itens))
    partes.append(f"[FONTE] {p.get('fonte')} · consulta {p['atual'].get('consulta_utc')} UTC · {p['atualidade']['rotulo']}")
    return "\n".join(partes)


def pacote_e_texto(escopo: str, cargo: str = "presidente") -> tuple[dict, str]:
    p = pacote(escopo, cargo)
    return p, compactar(p)


def numeros_para_auditoria(p: dict) -> tuple[dict, list[dict]]:
    """(evidência serializável, snapshots) para matematica.auditar_texto."""
    snaps = [s for s in (p.get("atual"), p.get("anterior"), p.get("brasil"), p.get("primeiro_turno")) if s]
    snaps += list((p.get("estados") or {}).values())
    evid = {"atual": p.get("atual"), "anterior": p.get("anterior"), "brasil": p.get("brasil"),
            "primeiro_turno": p.get("primeiro_turno"), "estados": p.get("estados"),
            "calculos": [i.get("texto") for i in p["relatorio"]["itens"]], "cenarios": p["relatorio"].get("cenarios")}
    return evid, snaps
