"""Google Gemini API — nível gratuito (AI Studio, sem faturamento)."""
from __future__ import annotations

import re

from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA

BASE = "https://generativelanguage.googleapis.com/v1beta"


class Gemini(Provedor):
    id = "gemini"
    nome = "Gemini"
    variaveis = ("GEMINI_API_KEY",)
    link_chaves = "https://aistudio.google.com/api-keys"
    nota_gratuita = "Free tier do AI Studio: cotas baixas por minuto e por dia; modelos Pro podem não estar disponíveis sem faturamento."
    assentos_maximos = 2
    url_modelos = BASE + "/models?pageSize=200"
    padroes = [r"^gemini-\d+(\.\d+)?-flash$", r"^gemini-\d+(\.\d+)?-flash-lite$", r"^gemini-.*flash(?!.*(image|tts|audio|live))",
               r"^gemma-\d"]
    excluir = [r"image", r"tts", r"audio", r"live", r"embedding", r"aqa", r"imagen", r"veo", r"robotics", r"computer-use",
               r"-pro", r"learnlm", r"thinking-exp", r"vision"]

    def cabecalhos(self) -> dict:
        return {"x-goog-api-key": self.segredo()}

    def listar_modelos(self) -> list[str]:
        http, dados, _ = base.requisitar(self.url_modelos, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Lista de modelos inesperada.")
        ids = []
        for m in dados.get("models") or []:
            nome = str(m.get("name") or "").replace("models/", "")
            metodos = m.get("supportedGenerationMethods") or []
            if nome and (not metodos or "generateContent" in metodos):
                ids.append(nome)
        return ids

    def filtrar_modelos(self, ids):
        escolhidos = super().filtrar_modelos(ids)

        def versao(nome):
            m = re.search(r"gemini-(\d+)(?:\.(\d+))?", nome)
            return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
        # Entre os "flash" estáveis, prefira a versão mais nova; mantenha a ordem relativa dos demais.
        flash = [m for m in escolhidos if re.fullmatch(r"gemini-\d+(\.\d+)?-flash", m)]
        lite = [m for m in escolhidos if re.fullmatch(r"gemini-\d+(\.\d+)?-flash-lite", m)]
        resto = [m for m in escolhidos if m not in flash and m not in lite]
        return sorted(flash, key=versao, reverse=True) + sorted(lite, key=versao, reverse=True) + resto

    def montar_requisicao(self, modelo, mensagens, max_tokens, temperatura):
        if not re.fullmatch(r"[a-z0-9.\-]{3,80}", modelo):
            raise ErroProvedor("formato", "Nome de modelo Gemini inválido.")
        sistema = "\n".join(m["content"] for m in mensagens if m.get("role") == "system")
        conteudos = [{"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": str(m.get("content", ""))}]}
                     for m in mensagens if m.get("role") != "system"]
        corpo = {"contents": conteudos, "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperatura}}
        if sistema:
            corpo["systemInstruction"] = {"parts": [{"text": sistema}]}
        return f"{BASE}/models/{modelo}:generateContent", self.cabecalhos(), corpo

    def extrair_resposta(self, dados):
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Resposta inesperada do Gemini.")
        partes = []
        for cand in dados.get("candidates") or []:
            for p in (cand.get("content") or {}).get("parts") or []:
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    partes.append(p["text"])
        uso = dados.get("usageMetadata") or {}
        return "\n".join(partes).strip(), {"entrada": uso.get("promptTokenCount"), "saida": uso.get("candidatesTokenCount"),
                                           "modelo_real": dados.get("modelVersion")}
