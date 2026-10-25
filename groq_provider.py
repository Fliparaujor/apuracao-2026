"""GroqCloud Free tier: GPT-OSS via OpenAI-compatible chat completions.
Only called on Termux localhost; API key never leaves server environment except HTTPS auth to Groq.
No billing integration is performed here.
"""
import json
import os
import urllib.error
import urllib.request

API = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
MODES = {
    "resumo": "Elabore briefing factual, com dados oficiais, mudanças observáveis e limites dos dados. No máximo 550 palavras.",
    "investigar": "Compare as UFs, a velocidade da totalização, dados do primeiro turno e diferenças regionais. Separe fatos de hipóteses e dados insuficientes. No máximo 550 palavras.",
    "cenarios": "Use apenas os cenários aritméticos CONDICIONAIS já calculados, sem chances, favoritos, probabilidades ou prognósticos. Indique as premissas. No máximo 550 palavras."
}

def compact_evidence(context: dict) -> dict:
    """Keep all distinct states but send compact data for the free TPM allowance."""
    selected = context["escopo"]
    def compact_candidate(c):
        return {
            "n": c.get("nome"), "partido": c.get("partido"),
            "votos": c.get("votos"), "pct": c.get("percentual"),
            "status_tse": c.get("status_tse")
        }
    def compact_scope(x):
        if not isinstance(x, dict) or "candidatos" not in x:
            return x
        return {
            "regiao": x.get("regiao"), "turno": x.get("turno"),
            "horario_tse": x.get("horario_tse"),
            "secoes_pct": x.get("secoes_processadas_pct"),
            "votos_validos": x.get("votos_validos"),
            "eleitorado": x.get("eleitorado"),
            "comparecimento": x.get("comparecimento"),
            "conclusao_oficial": x.get("totalizacao_encerrada_tse"),
            "candidatos": [compact_candidate(c) for c in x.get("candidatos", [])],
            "fonte": x.get("fonte")
        }
    return {
        "escopo": compact_scope(selected),
        "brasil": compact_scope(context["brasil"]) if context.get("brasil") else None,
        "primeiro_turno": compact_scope(context.get("primeiro_turno_historico_mesma_regiao", {})),
        "estados": [
            {
                "uf": s["UF"], "apurado_pct": s["apurado_pct"],
                "validos": s["validos"], "horario_tse": s["horario_tse"],
                "candidatos": [compact_candidate(c) for c in s.get("candidatos", [])]
            }
            for s in context["estados_parciais"]
        ],
        "mudanca_observada": context.get("comparacao_com_boletim_anterior_neste_termux"),
        "cenarios_matematicos_condicionais": context.get("cenarios_aritmeticos_sem_previsao"),
        "uf_sem_resposta": list(context["falhas_de_coleta"]),
        "nota": context["aviso"]
    }

def analyze(context: dict, mode: str, question: str, instructions: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Groq não configurado: defina GROQ_API_KEY apenas no Termux.")
    prompt = (
        "TIPO DE ANÁLISE: "+MODES[mode]+"\n"
        "PERGUNTA DO USUÁRIO (não é fonte factual): "+question+"\n"
        "EVIDÊNCIAS DOS ARQUIVOS OFICIAIS DO TSE: "+
        json.dumps(compact_evidence(context), ensure_ascii=False, separators=(",", ":"))
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_completion_tokens": 2600,
        "reasoning_effort": "medium",
        "include_reasoning": False,
        "stream": False
    }
    request = urllib.request.Request(
        API, method="POST",
        headers={
            "Authorization": "Bearer "+key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            data = json.load(response)
    except urllib.error.HTTPError as err:
        if err.code == 429:
            raise RuntimeError("O limite gratuito do Groq foi atingido (429). Aguarde e tente novamente.")
        if err.code in (401, 403):
            raise RuntimeError("Chave do Groq inválida, revogada ou sem acesso (401/403).")
        if err.code == 404:
            raise RuntimeError("Modelo GPT-OSS 120B indisponível na conta Groq (404).")
        if err.code == 400:
            raise RuntimeError("O Groq rejeitou os parâmetros ou o limite de tokens (400).")
        raise RuntimeError("Groq indisponível (HTTP "+str(err.code)+"). Tente novamente.")
    try:
        message = data["choices"][0]["message"]
        result = message.get("content", "")
    except (KeyError, IndexError, TypeError):
        result = ""
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("Groq não retornou análise textual utilizável.")
    return result[:15000].strip()
