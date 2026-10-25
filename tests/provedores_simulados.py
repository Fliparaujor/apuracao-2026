"""Roteador HTTPS SIMULADO para os provedores de IA (nenhuma chamada real).

Substitui `radar.provedores.base.requisitar`. Comportamento por chave falsa:
  - chave que contém 'invalida' → 401; 'limite' → 429; 'quebrado' → 500; 'vazio' → sem texto.
As respostas de chat ecoam números da evidência (para a auditoria) e, quando a
pergunta contém 'INVENTE', incluem um número fabricado e um prognóstico.
"""
from __future__ import annotations

import json
import re

from radar.provedores.base import ErroProvedor, classificar_http

CHAMADAS: list[dict] = []


def _token(headers: dict) -> str:
    for k, v in (headers or {}).items():
        if k.lower() in ("authorization", "x-goog-api-key"):
            return str(v).replace("Bearer ", "")
    return ""


def _texto_resposta(corpo: dict, provedor: str) -> str:
    bruto = json.dumps(corpo, ensure_ascii=False)
    numeros = re.findall(r"\d{1,3}(?:\.\d{3})+|\d+,\d+%", bruto)
    cita = ", ".join(dict.fromkeys(numeros[:4])) or "sem números"
    if "RELATOR" in bruto or "RELATÓRIO FINAL" in bruto:
        return ("1. Fatos oficiais confirmados\n[FATO TSE] Boletim com " + cita + ".\n2. Cálculos relevantes\n[CÁLCULO] Diferença registrada na evidência.\n"
                "3. Concordâncias entre conselheiros\nDois conselheiros concordam sobre a liderança parcial.\n4. Divergências persistentes\nO Cético contesta a leitura regional.\n"
                "5. Hipóteses que ainda precisam de verificação\n[HIPÓTESE] Ordem de totalização.\n6. Limitações dos dados\n[LIMITAÇÃO] Totalização parcial.\n7. Fontes e horários utilizados\nTSE, boletim citado.")
    if "REVISOR" in bruto:
        return "[CÁLCULO] Concordo com o Quantitativo sobre " + cita + ". Divergência: o Regional extrapolou. Dados necessários: boletins por UF."
    if "OBJEÇÕES RECEBIDAS" in bruto:
        return "Mantenho o parecer: os números " + cita + " estão na evidência. Corrijo a ênfase regional."
    if "INVENTE" in bruto:
        return "[FATO TSE] Parcial com " + cita + ". O líder tem 77% em Roraima e vai vencer com 90% de chance."
    return f"[FATO TSE] Simulação {provedor}: parcial com {cita}. [CÁLCULO] Diferença conforme a evidência. [LIMITAÇÃO] Totalização parcial."


def requisitar_simulado(url: str, metodo: str = "GET", headers: dict | None = None, corpo: dict | None = None, timeout: int = 0, tentativas: int = 2):
    CHAMADAS.append({"url": url, "metodo": metodo, "corpo": corpo})
    tok = _token(headers or {})
    if "invalida" in tok:
        raise classificar_http(401, '{"error":"invalid api key"}')
    if "limite" in tok:
        raise classificar_http(429, '{"error":"rate limit, please try again in 2m"}', {"Retry-After": "120"})
    if "quebrado" in tok:
        raise classificar_http(500, "boom")
    if "semrede" in tok:
        raise ErroProvedor("rede", "Falha de rede simulada.")
    # ---- listagens
    if "api.groq.com/openai/v1/models" in url:
        return 200, {"data": [{"id": "openai/gpt-oss-120b", "active": True}, {"id": "whisper-large-v3"}, {"id": "qwen/qwen3-32b"}, {"id": "llama-3.1-8b-instant"}]}, {}
    if "generativelanguage.googleapis.com/v1beta/models?" in url:
        return 200, {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                                {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                                {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]}]}, {}
    if "api.mistral.ai/v1/models" in url:
        return 200, {"data": [{"id": "mistral-small-latest", "capabilities": {"completion_chat": True}}, {"id": "codestral-latest"}, {"id": "mistral-embed", "capabilities": {"completion_chat": False}}]}, {}
    if "openrouter.ai/api/v1/models" in url:
        return 200, {"data": [{"id": "deepseek/deepseek-r1:free", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 64000},
                              {"id": "openai/gpt-4o", "pricing": {"prompt": "0.0025", "completion": "0.01"}, "context_length": 128000},
                              {"id": "meta-llama/llama-3.3-70b-instruct:free", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 65536}]}, {}
    if "openrouter.ai/api/v1/auth/key" in url:
        return 200, {"data": {"label": "x", "limit": None}}, {}
    if "api.cohere.com/v1/models" in url:
        return 200, {"models": [{"name": "command-a-03-2025"}, {"name": "embed-english-v3.0"}, {"name": "command-r7b-12-2024"}]}, {}
    if "user/tokens/verify" in url:
        return 200, {"success": True, "result": {"status": "active"}}, {}
    if "/ai/models/search" in url:
        return 200, {"success": True, "result": [{"name": "@cf/meta/llama-3.3-70b-instruct-fp8-fast"}, {"name": "@cf/meta/llama-guard-3-8b"}, {"name": "@hf/thebloke/x"}]}, {}
    if "huggingface.co/api/whoami-v2" in url:
        return 200, {"name": "usuario"}, {}
    if "router.huggingface.co/v1/models" in url:
        return 200, {"data": [{"id": "Qwen/Qwen3-32B"}, {"id": "Qwen/Qwen2.5-VL-7B-Instruct"}]}, {}
    # ---- chat
    if metodo == "POST" and corpo is not None:
        if "vazio" in tok:
            return 200, {"choices": [{"message": {"content": ""}}], "candidates": [], "message": {"content": []}}, {}
        if "generateContent" in url:
            texto = _texto_resposta(corpo, "gemini")
            return 200, {"candidates": [{"content": {"parts": [{"text": texto}]}}], "usageMetadata": {"promptTokenCount": 500, "candidatesTokenCount": 80}, "modelVersion": "gemini-2.5-flash"}, {}
        if "api.cohere.com/v2/chat" in url:
            return 200, {"message": {"content": [{"type": "text", "text": _texto_resposta(corpo, "cohere")}]}, "usage": {"tokens": {"input_tokens": 400, "output_tokens": 60}}}, {}
        prov = "groq" if "groq" in url else "openrouter" if "openrouter" in url else "mistral" if "mistral" in url else "cloudflare" if "cloudflare" in url else "huggingface"
        modelo = corpo.get("model")
        if prov == "openrouter" and "pago" in tok:
            modelo = "openai/gpt-4o"
        return 200, {"model": modelo, "choices": [{"message": {"content": _texto_resposta(corpo, prov)}}], "usage": {"prompt_tokens": 450, "completion_tokens": 70}}, {}
    raise ErroProvedor("formato", "URL simulada desconhecida: " + url)
