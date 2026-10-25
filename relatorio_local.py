"""Relatorio deterministico do Radar baseado somente nos JSON oficiais do TSE.

Sem LLM, sem chaves e sem previsoes. O metodo conta votos, taxa de
totalizacao e diferencas observadas (nao extrapola vencendor).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import inteligencia

REGIONS = {"br": "Brasil", "ce": "Ceará", "ap": "Amapá", "ce13897": "Fortaleza", "ap06050": "Macapá"}

def fmt(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")

def percent(n) -> str:
    return f"{float(n or 0):.2f}".replace(".", ",")

def build(scope: str) -> dict:
    if scope not in inteligencia.PERMITTED:
        raise ValueError("Região inválida.")
    wanted = list(dict.fromkeys((scope, "br", "ce", "ap")))
    data, failures = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(inteligencia.get_official, k, 2): k for k in wanted}
        for future in as_completed(future_map):
            k = future_map[future]
            try:
                data[k] = future.result()
            except Exception:
                failures[k] = "Não foi possível consultar o TSE para esta região."

    selected = data.get(scope)
    if not selected:
        return {"ok": False, "regiao":scope, "erro":"Sem dados verificáveis do TSE nesta consulta.",
                "fonte": inteligencia.url_for(scope, 2), "paragrafos": [],
                "falhas": failures, "tipo":"Leitura automática de dados; não é IA."}

    history = inteligencia.write_and_diff(scope, selected)
    c = selected.get("candidatos") or []
    counted = selected.get("secoes_processadas_pct") or 0
    paragraphs = []
    title = REGIONS.get(scope, scope.upper())
    time = selected.get("horario_tse") or "não informado"
    if not selected.get("votos_validos") or len(c) < 2:
        paragraphs.append("O TSE ainda não disponibilizou votos suficientes para comparar as duas candidaturas nesta abrangência.")
    else:
        a,b = c[0],c[1]
        gap=int(a["votos"])-int(b["votos"])
        pp=float(a["percentual"])-float(b["percentual"])
        paragraphs.append(
            f"FATO DO TSE — {title}, boletim {time}. {a['nome']} lidera a parcial: "
            f"{percent(a['percentual'])}% ({fmt(a['votos'])} votos), ante "
            f"{percent(b['percentual'])}% ({fmt(b['votos'])} votos) para {b['nome']}. "
            f"Totalização: {percent(counted)}% das seções."
        )
        paragraphs.append(
            f"CÁLCULO — A diferença nesta parcial é de {fmt(abs(gap))} votos "
            f"e {percent(abs(pp))} pontos percentuais. São diferenças já observadas, "
            "não uma previsão do resultado final."
        )
        if history:
            new_leader = "Houve troca de liderança entre boletins armazenados." if history["mudanca_de_lideranca"] else "A liderança não mudou entre os dois boletins armazenados."
            delta_counted=float(counted)-float(history["apuracao_anterior_pct"])
            delta_votes=int(selected["votos_validos"])-int(history["validos_anterior"])
            paragraphs.append(
                f"MUDANÇA VERIFICADA — Desde o boletim {history['boletim_anterior']}, "
                f"o número de votos válidos totalizados variou em {fmt(delta_votes)} e "
                f"as seções totalizadas variaram {percent(delta_counted)} ponto(s). {new_leader} "
                "A ordem regional de chegada dos boletins pode explicar oscilações."
            )
        else:
            paragraphs.append(
                "HISTÓRICO — Não há um boletim anterior diferente guardado neste Termux "
                "para calcular uma variação verificável. A comparação surgirá quando o TSE divulgar outra parcial."
            )

        if counted < 100 and not selected.get("totalizacao_encerrada_tse"):
            paragraphs.append(
                "LIMITE DOS DADOS — Trata-se de totalização parcial. "
                "O percentual de seções não equivale exatamente à proporção de votos ainda não contados; "
                "a distribuição geográfica pode mudar à medida que novas seções forem totalizadas."
            )
        else:
            paragraphs.append(
                "STATUS — O indicador de seções totalizadas alcançou o valor apresentado acima. "
                "Confirme a situação oficial da eleição no TSE antes de considerar um resultado definitivo."
            )

    if scope=="br":
        for k in ("ce","ap"):
            x=data.get(k)
            if x and x.get("votos_validos") and len(x.get("candidatos") or [])>=2:
                winner=x["candidatos"][0]
                paragraphs.append(
                    f"RECORTE REGIONAL — {REGIONS[k]}: {winner['nome']} lidera a parcial local "
                    f"com {percent(winner['percentual'])}% dos votos válidos divulgados, "
                    f"com {percent(x['secoes_processadas_pct'])}% das seções totalizadas no boletim "
                    f"{x['horario_tse']}. Esses recortes não representam o país inteiro."
                )
    elif "br" in data and data["br"].get("votos_validos"):
        national=data["br"]
        paragraphs.append(
            f"CONTEXTO — No Brasil, {percent(national['secoes_processadas_pct'])}% das seções "
            f"constam como totalizadas no boletim {national['horario_tse']}. "
            "Os percentuais de Brasil e de uma UF devem ser comparados levando em conta diferenças de atualização."
        )
    paragraphs.append(
        "MÉTODO — Esta leitura foi calculada diretamente dos JSON do TSE, sem modelo de linguagem "
        "e sem análise de opinião. Hipóteses sobre causas políticas exigem outras evidências."
    )
    return {
        "ok": True, "tipo": "Análise descritiva automática (sem IA)",
        "regiao": scope, "nome":title,
        "horario_tse": time,
        "consulta_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte":selected.get("fonte", inteligencia.url_for(scope,2)),
        "paragrafos": paragraphs,
        "falhas":failures
    }
