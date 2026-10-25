"""Camada 3 — motor matemático determinístico (funciona sem nenhuma IA).

Cada item produzido tem um `tipo`:
  fato       — valor publicado diretamente pelo TSE;
  calculo    — operação aritmética reproduzível sobre fatos;
  hipotese   — interpretação que precisa de outras evidências;
  limitacao  — o que os dados disponíveis não permitem concluir.
Nunca atribui probabilidade de vitória nem projeta resultado final.
"""
from __future__ import annotations

import re
from statistics import mean, pstdev

from . import tse


def item(tipo: str, titulo: str, texto: str, **extra) -> dict:
    d = {"tipo": tipo, "titulo": titulo, "texto": texto}
    d.update(extra)
    return d


def fmt_int(n) -> str:
    return f"{int(round(n or 0)):,}".replace(",", ".")


def fmt_pct(n, casas: int = 2) -> str:
    return f"{float(n or 0):.{casas}f}".replace(".", ",")


def _dois(snap: dict) -> tuple[dict | None, dict | None]:
    c = snap.get("candidatos") or []
    return (c[0] if len(c) > 0 else None, c[1] if len(c) > 1 else None)


def nome_cand(c: dict) -> str:
    nome = (c.get("nome") or c.get("numero") or "candidatura").strip()
    return nome.title() if nome.isupper() else nome


# ----------------------------------------------------------------- resumo

def fatos(snap: dict) -> list[dict]:
    saida = [item("fato", "Boletim oficial",
                  f"{snap.get('nome_escopo', snap.get('escopo'))}, {snap.get('cargo_nome', 'Presidente')}, "
                  f"{snap.get('turno', 2)}º turno, boletim do TSE de {snap.get('horario_tse') or 'horário não informado'}. "
                  f"Seções totalizadas: {fmt_pct(snap.get('secoes_pct'))}% ({fmt_int(snap.get('secoes_totalizadas'))} de {fmt_int(snap.get('secoes_total'))}). "
                  f"Status: {snap.get('status_oficial') or tse.status_oficial(snap)}.",
                  fonte=snap.get("fonte", ""))]
    for c in (snap.get("candidatos") or [])[:6]:
        saida.append(item("fato", nome_cand(c),
                          f"{fmt_pct(c.get('percentual'))}% dos votos válidos, {fmt_int(c.get('votos'))} votos"
                          + (f" · situação TSE: {c['situacao']}" if c.get("situacao") else "") + ".",
                          numero=c.get("numero"), votos=c.get("votos"), percentual=c.get("percentual")))
    if snap.get("votos_validos"):
        saida.append(item("fato", "Totais",
                          f"Votos válidos {fmt_int(snap.get('votos_validos'))}; brancos {fmt_int(snap.get('brancos'))} "
                          f"({fmt_pct(snap.get('brancos_pct'))}%); nulos {fmt_int(snap.get('nulos'))} ({fmt_pct(snap.get('nulos_pct'))}%); "
                          f"comparecimento {fmt_int(snap.get('comparecimento'))}; abstenção {fmt_int(snap.get('abstencao'))}"
                          + (f" ({fmt_pct(snap.get('abstencao_pct'))}%)" if snap.get("abstencao_pct") else "") + "."))
    return saida


def diferencas(snap: dict) -> list[dict]:
    a, b = _dois(snap)
    if not a or not b or not snap.get("votos_validos"):
        return [item("limitacao", "Sem comparação possível",
                     "O TSE ainda não publicou votos para duas candidaturas nesta abrangência.")]
    dif = int(a["votos"]) - int(b["votos"])
    pp = float(a["percentual"]) - float(b["percentual"])
    vv = int(snap["votos_validos"])
    saida = [item("calculo", "Diferença na parcial",
                  f"{nome_cand(a)} está à frente de {nome_cand(b)} por {fmt_int(abs(dif))} votos "
                  f"({fmt_pct(abs(pp))} pontos percentuais). Cálculo: {fmt_int(a['votos'])} − {fmt_int(b['votos'])}.",
                  diferenca_votos=dif, diferenca_pp=round(pp, 2))]
    if vv:
        saida.append(item("calculo", "Participação sobre válidos",
                          f"A diferença equivale a {fmt_pct(100 * abs(dif) / vv)}% dos {fmt_int(vv)} votos válidos já totalizados.",
                          diferenca_sobre_validos_pct=round(100 * abs(dif) / vv, 2)))
    soma = sum(int(c.get("votos") or 0) for c in snap.get("candidatos") or [])
    if soma and abs(soma - vv) > 0:
        saida.append(item("calculo", "Consistência interna",
                          f"A soma dos votos nominais ({fmt_int(soma)}) difere dos votos válidos informados ({fmt_int(vv)}) em {fmt_int(abs(soma - vv))}; "
                          "o TSE pode contar votos anulados sub judice separadamente."))
    if snap.get("comparecimento") and snap.get("eleitorado_secoes_totalizadas"):
        saida.append(item("calculo", "Comparecimento nas seções totalizadas",
                          f"{fmt_pct(100 * snap['comparecimento'] / snap['eleitorado_secoes_totalizadas'])}% dos "
                          f"{fmt_int(snap['eleitorado_secoes_totalizadas'])} eleitores das seções já totalizadas compareceram."))
    if float(snap.get("secoes_pct") or 0) < 100 and not snap.get("totalizacao_final"):
        saida.append(item("limitacao", "Totalização parcial",
                          f"Somente {fmt_pct(snap.get('secoes_pct'))}% das seções foram totalizadas. O percentual de seções não equivale "
                          "ao percentual de votos restantes e a ordem geográfica de chegada dos boletins altera a parcial."))
    return saida


def variacao(anterior: dict | None, atual: dict) -> list[dict]:
    if not anterior or anterior.get("horario_tse") == atual.get("horario_tse") and anterior.get("votos_validos") == atual.get("votos_validos"):
        return [item("limitacao", "Sem boletim anterior distinto",
                     "Ainda não há dois boletins diferentes guardados neste aparelho para medir variação.")]
    saida = []
    d_sec = float(atual.get("secoes_pct") or 0) - float(anterior.get("secoes_pct") or 0)
    d_vv = int(atual.get("votos_validos") or 0) - int(anterior.get("votos_validos") or 0)
    saida.append(item("calculo", "Entre boletins",
                      f"De {anterior.get('horario_tse')} para {atual.get('horario_tse')}: seções totalizadas variaram "
                      f"{'+' if d_sec >= 0 else ''}{fmt_pct(d_sec)} ponto(s); votos válidos variaram {'+' if d_vv >= 0 else ''}{fmt_int(d_vv)}.",
                      delta_secoes_pp=round(d_sec, 2), delta_validos=d_vv,
                      boletim_anterior=anterior.get("horario_tse"), boletim_atual=atual.get("horario_tse")))
    ant = {str(c.get("numero")): c for c in anterior.get("candidatos") or []}
    for c in atual.get("candidatos") or []:
        p = ant.get(str(c.get("numero")))
        if not p:
            continue
        dp = float(c.get("percentual") or 0) - float(p.get("percentual") or 0)
        dv = int(c.get("votos") or 0) - int(p.get("votos") or 0)
        saida.append(item("calculo", f"Variação de {nome_cand(c)}",
                          f"{'+' if dp >= 0 else ''}{fmt_pct(dp)} ponto(s) percentuais e {'+' if dv >= 0 else ''}{fmt_int(dv)} votos desde o boletim anterior.",
                          numero=c.get("numero"), delta_pp=round(dp, 2), delta_votos=dv))
        if d_vv > 0 and dv >= 0:
            saida.append(item("calculo", f"Fatia dos novos votos — {nome_cand(c)}",
                              f"Dos {fmt_int(d_vv)} votos válidos acrescentados, {fmt_pct(100 * dv / d_vv)}% foram para {nome_cand(c)}.",
                              fatia_novos_pct=round(100 * dv / d_vv, 2)))
    a_ant, _ = _dois(anterior)
    a_atu, _ = _dois(atual)
    if a_ant and a_atu and a_ant.get("numero") != a_atu.get("numero"):
        saida.append(item("fato", "Mudança de liderança parcial",
                          f"A liderança passou de {nome_cand(a_ant)} para {nome_cand(a_atu)} entre os dois boletins.",
                          mudanca_lideranca=True))
    saida.append(item("hipotese", "Leitura da variação",
                      "Variações entre boletins refletem quais seções entraram na totalização nesse intervalo, não necessariamente uma tendência; "
                      "para testar tendência seriam precisos vários boletins consecutivos com a composição regional das seções novas."))
    return saida


def evolucao(hist: list[dict]) -> dict:
    """Série temporal de seções totalizadas e percentuais por candidato, com trocas de liderança."""
    serie, trocas, lider_anterior = [], [], None
    for s in hist:
        ponto = {"horario_tse": s.get("horario_tse"), "secoes_pct": s.get("secoes_pct"),
                 "votos_validos": s.get("votos_validos"), "consulta_utc": s.get("consulta_utc"),
                 "candidatos": [{"numero": c.get("numero"), "nome": nome_cand(c), "percentual": c.get("percentual"),
                                 "votos": c.get("votos")} for c in s.get("candidatos") or []]}
        serie.append(ponto)
        a, _ = _dois(s)
        if a:
            if lider_anterior and lider_anterior != a.get("numero"):
                trocas.append({"horario_tse": s.get("horario_tse"), "de": lider_anterior, "para": a.get("numero")})
            lider_anterior = a.get("numero")
    return {"pontos": serie, "trocas_de_lideranca": trocas, "boletins": len(serie)}


def regional(estados: dict[str, dict], nacional: dict | None = None) -> list[dict]:
    """Variações entre UFs; `estados` mapeia uf -> snapshot presidente."""
    validos = {uf: s for uf, s in estados.items() if s and s.get("votos_validos") and len(s.get("candidatos") or []) >= 2}
    if not validos:
        return [item("limitacao", "Sem recortes estaduais", "Nenhuma UF com votos publicados nesta consulta.")]
    saida = []
    lideres: dict[str, list[str]] = {}
    for uf, s in validos.items():
        a, _ = _dois(s)
        lideres.setdefault(nome_cand(a), []).append(uf.upper())
    resumo = "; ".join(f"{nome} lidera em {len(ufs)} UF(s): {', '.join(sorted(ufs))}" for nome, ufs in sorted(lideres.items()))
    saida.append(item("fato", f"Liderança parcial por UF ({len(validos)} de 27 com votos)", resumo + "."))
    taxas = [float(s.get("secoes_pct") or 0) for s in validos.values()]
    saida.append(item("calculo", "Dispersão da totalização",
                      f"Seções totalizadas variam de {fmt_pct(min(taxas))}% a {fmt_pct(max(taxas))}% entre as UFs "
                      f"(média {fmt_pct(mean(taxas))}%, desvio {fmt_pct(pstdev(taxas) if len(taxas) > 1 else 0)}).",
                      minimo=min(taxas), maximo=max(taxas)))
    margens = sorted(((abs(float(s['candidatos'][0]['percentual']) - float(s['candidatos'][1]['percentual'])), uf) for uf, s in validos.items()))
    estreitas = [f"{uf.upper()} ({fmt_pct(m)} pp)" for m, uf in margens[:3]]
    largas = [f"{uf.upper()} ({fmt_pct(m)} pp)" for m, uf in margens[-3:]]
    saida.append(item("calculo", "Margens mais estreitas e mais largas",
                      f"Estreitas: {', '.join(estreitas)}. Largas: {', '.join(reversed(largas))}."))
    atrasadas = [uf.upper() for uf, s in validos.items() if float(s.get("secoes_pct") or 0) < 0.5 * mean(taxas)]
    if atrasadas:
        saida.append(item("limitacao", "UFs com totalização atrasada",
                          f"{', '.join(sorted(atrasadas))} têm menos da metade da taxa média de seções totalizadas; "
                          "seus percentuais podem mudar bem mais que os das demais."))
    if nacional and nacional.get("votos_validos"):
        soma_uf = sum(int(s.get("votos_validos") or 0) for s in validos.values())
        saida.append(item("calculo", "Cobertura dos recortes",
                          f"As UFs com votos somam {fmt_int(soma_uf)} válidos ante {fmt_int(nacional['votos_validos'])} no total nacional "
                          f"({fmt_pct(100 * soma_uf / nacional['votos_validos'])}%); a diferença inclui exterior e UFs ainda sem publicação."))
    saida.append(item("limitacao", "Comparação entre UFs",
                      "UFs com taxas de totalização muito diferentes não devem ser comparadas diretamente; o peso de cada UF no total "
                      "nacional depende do eleitorado, não do número de UFs em que cada candidatura lidera."))
    return saida


def primeiro_turno(atual: dict, primeiro: dict | None) -> list[dict]:
    if not primeiro or not primeiro.get("votos_validos"):
        return [item("limitacao", "1º turno indisponível", "A referência do 1º turno não foi obtida; a comparação histórica fica suspensa.")]
    saida = [item("fato", "1º turno (referência)",
                  f"Boletim {primeiro.get('horario_tse')}, {fmt_pct(primeiro.get('secoes_pct'))}% das seções, {fmt_int(primeiro.get('votos_validos'))} válidos. "
                  + "; ".join(f"{nome_cand(c)} {fmt_pct(c.get('percentual'))}%" for c in (primeiro.get("candidatos") or [])[:6]) + ".",
                  fonte=primeiro.get("fonte", ""))]
    ant = {str(c.get("numero")): c for c in primeiro.get("candidatos") or []}
    for c in atual.get("candidatos") or []:
        p = ant.get(str(c.get("numero")))
        if p:
            dp = float(c.get("percentual") or 0) - float(p.get("percentual") or 0)
            saida.append(item("calculo", f"{nome_cand(c)}: 1º → 2º turno",
                              f"De {fmt_pct(p.get('percentual'))}% para {fmt_pct(c.get('percentual'))}% dos válidos "
                              f"({'+' if dp >= 0 else ''}{fmt_pct(dp)} pp), comparando um resultado final com uma parcial.",
                              numero=c.get("numero"), delta_pp=round(dp, 2)))
    outros = sum(float(c.get("percentual") or 0) for n, c in ant.items() if n not in {str(x.get("numero")) for x in atual.get("candidatos") or []})
    if outros:
        saida.append(item("calculo", "Votos de outras candidaturas no 1º turno",
                          f"{fmt_pct(outros)}% dos válidos do 1º turno foram para candidaturas fora do 2º turno."))
    if atual.get("comparecimento") and primeiro.get("comparecimento") and float(atual.get("secoes_pct") or 0) >= 99.9:
        dc = int(atual["comparecimento"]) - int(primeiro["comparecimento"])
        saida.append(item("calculo", "Comparecimento entre turnos",
                          f"Comparecimento variou {'+' if dc >= 0 else ''}{fmt_int(dc)} eleitores com a totalização praticamente completa."))
    saida.append(item("limitacao", "Comparabilidade",
                      "O 1º turno é outra eleição, com mais candidaturas, 100% das seções e outro universo de votos válidos. Percentuais da parcial "
                      "atual não são comparáveis um a um, e a soma dos votos de terceiros não permite deduzir transferência individual de votos."))
    return saida


def cenarios(snap: dict, premissas: dict | None = None) -> dict:
    """Cenários aritméticos com premissas explícitas, sem probabilidade."""
    premissas = premissas or {}
    a, b = _dois(snap)
    if not a or not b or not snap.get("votos_validos"):
        return {"ok": False, "motivo": "Sem duas candidaturas com votos.", "cenarios": [], "premissas": premissas}
    dif = int(a["votos"]) - int(b["votos"])
    vv = int(snap["votos_validos"])
    pct = float(snap.get("secoes_pct") or 0)
    lista_n = premissas.get("novos_votos_validos")
    if not isinstance(lista_n, list) or not lista_n:
        lista_n = [1_000_000, 5_000_000, 10_000_000, 20_000_000] if snap.get("escopo") == "br" else [50_000, 200_000, 500_000, 1_000_000]
    cen = []
    for n in lista_n[:8]:
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        p = 50 + 50 * dif / n
        cen.append({"novos_votos_validos_hipoteticos": n,
                    "pct_necessario_para_quem_esta_atras_empatar": round(p, 2) if p <= 100 else None,
                    "possivel_apenas_neste_cenario": p < 100,
                    "premissa": f"Hipótese: {fmt_int(n)} novos votos válidos. Não é previsão de quantos votos faltam."})
    saida = {"ok": True, "lider": nome_cand(a), "segundo": nome_cand(b), "diferenca_votos": dif,
             "cenarios": cen, "premissas": premissas,
             "avisos": ["Nenhuma probabilidade é atribuída.",
                        "O número de votos restantes não é conhecido: o TSE publica seções totalizadas, não votos faltantes."]}
    if pct > 0 and snap.get("votos_validos"):
        extrap = vv * (100 / pct) - vv
        saida["referencia_bruta"] = {
            "descricao": "Extrapolação linear ingênua de votos válidos ainda não totalizados (válidos ÷ fração de seções); "
                         "seções têm tamanhos diferentes, logo isso é só uma ordem de grandeza, não uma estimativa.",
            "votos_validos_restantes_ordem_de_grandeza": int(extrap),
            "pct_necessario_nessa_hipotese": round(50 + 50 * dif / extrap, 2) if extrap > 0 and 50 + 50 * dif / extrap <= 100 else None,
        }
    return saida


def relatorio_completo(atual: dict, anterior: dict | None = None, hist: list[dict] | None = None,
                       estados: dict | None = None, nacional: dict | None = None,
                       primeiro: dict | None = None) -> dict:
    itens = fatos(atual) + diferencas(atual) + variacao(anterior, atual)
    if estados:
        itens += regional(estados, nacional)
    if primeiro is not None or atual.get("cargo") == "presidente":
        itens += primeiro_turno(atual, primeiro)
    ev = evolucao(hist or [])
    if ev["trocas_de_lideranca"]:
        itens.append(item("fato", "Trocas de liderança registradas",
                          f"{len(ev['trocas_de_lideranca'])} troca(s) de liderança nos {ev['boletins']} boletins guardados: "
                          + "; ".join(f"{t['horario_tse']}: {t['de']}→{t['para']}" for t in ev['trocas_de_lideranca'][-5:]) + "."))
    itens.append(item("limitacao", "Método",
                      "Leitura calculada diretamente dos arquivos oficiais do TSE, sem modelo de linguagem. Causas políticas, pesquisas e "
                      "comportamento de eleitores exigem outras fontes e não são inferidos aqui."))
    atualidade = tse.classificar_atualidade(atual)
    return {"ok": True, "tipo": "Análise descritiva automática (sem IA)", "escopo": atual.get("escopo"),
            "nome_escopo": atual.get("nome_escopo"), "cargo": atual.get("cargo"), "horario_tse": atual.get("horario_tse"),
            "atualidade": atualidade, "fonte": atual.get("fonte"), "itens": itens,
            "por_tipo": {t: [i for i in itens if i["tipo"] == t] for t in ("fato", "calculo", "hipotese", "limitacao")},
            "evolucao": ev, "cenarios": cenarios(atual)}


# -------------------------------------------------------------- auditoria

_NUM = re.compile(r"(?<![\w,.])(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s*(milh(?:ão|ões|oes|ao)|mil\b|%|pontos?|pp|votos)?", re.IGNORECASE)
_ESCALA = {"mil": 1_000, "milhao": 1_000_000, "milhão": 1_000_000, "milhoes": 1_000_000, "milhões": 1_000_000}


def numeros_da_evidencia(evidencia) -> set[float]:
    """Todos os números presentes (recursivamente) em um pacote de evidências, com derivados simples."""
    nums: set[float] = set()

    def coletar(obj):
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            nums.add(round(float(obj), 2))
        elif isinstance(obj, str):
            for m in _NUM.finditer(obj):
                try:
                    nums.add(round(tse.numero(m.group(1) + ("," + m.group(2) if m.group(2) else "")), 2))
                except ValueError:
                    pass
        elif isinstance(obj, dict):
            for v in obj.values():
                coletar(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                coletar(v)

    coletar(evidencia)
    return nums


def derivados(snap: dict) -> set[float]:
    """Números que decorrem de operações simples e legítimas sobre um snapshot."""
    d: set[float] = set()
    c = snap.get("candidatos") or []
    if len(c) >= 2:
        d.add(abs(int(c[0]["votos"]) - int(c[1]["votos"])))
        d.add(round(abs(float(c[0]["percentual"]) - float(c[1]["percentual"])), 2))
        d.add(round(abs(float(c[0]["percentual"]) - float(c[1]["percentual"])), 1))
    for x in (snap.get("secoes_pct"), snap.get("votos_validos"), snap.get("comparecimento")):
        if x:
            d.add(round(float(x), 2)); d.add(round(float(x), 1)); d.add(round(float(x)))
    if snap.get("brancos") is not None and snap.get("nulos") is not None:
        d.add(int(snap["brancos"]) + int(snap["nulos"]))
    if snap.get("secoes_total") and snap.get("secoes_totalizadas"):
        d.add(int(snap["secoes_total"]) - int(snap["secoes_totalizadas"]))
    return d


def auditar_texto(texto: str, evidencia, snapshots: list[dict] | None = None, tolerancia_pct: float = 0.6) -> dict:
    """Confere os números citados em um texto contra a evidência oficial.

    Números pequenos (≤ 10, contagens, anos) são ignorados. Percentuais aceitam
    arredondamento de até `tolerancia_pct` pontos; contagens aceitam 0,5%.
    """
    base = numeros_da_evidencia(evidencia)
    for s in snapshots or []:
        base |= derivados(s)
    confirmados, nao_suportados = [], []
    for m in _NUM.finditer(texto or ""):
        bruto = m.group(1) + ("," + m.group(2) if m.group(2) else "")
        valor = tse.numero(bruto)
        unidade = (m.group(3) or "").lower()
        rotulo = unidade
        if unidade in _ESCALA:
            valor *= _ESCALA[unidade]
            unidade = "votos"
        if valor <= 10 and not unidade:
            continue
        if 1900 <= valor <= 2100 and not m.group(2) and not unidade:
            continue
        if unidade.startswith("%") or unidade.startswith("p"):
            ok = any(abs(valor - b) <= tolerancia_pct for b in base if b <= 100)
        else:
            ok = any(abs(valor - b) <= max(1.0, 0.005 * abs(b)) for b in base)
        registro = {"citado": bruto + (" " + rotulo if rotulo else ""), "valor": valor}
        (confirmados if ok else nao_suportados).append(registro)
    return {"total": len(confirmados) + len(nao_suportados), "confirmados": len(confirmados),
            "nao_suportados": nao_suportados[:25],
            "veredito": "compatível" if not nao_suportados else ("parcialmente compatível" if confirmados else "sem suporte")}
