"""GroqCloud — nível gratuito (sem cartão). Chat OpenAI-compatível."""
from __future__ import annotations

from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA


class Groq(Provedor):
    id = "groq"
    nome = "Groq"
    variaveis = ("GROQ_API_KEY",)
    link_chaves = "https://console.groq.com/keys"
    nota_gratuita = "Nível Free: ~30 req/min e cota diária limitada por organização; o catálogo gratuito muda com frequência."
    assentos_maximos = 2
    url_modelos = "https://api.groq.com/openai/v1/models"
    url_chat = "https://api.groq.com/openai/v1/chat/completions"
    preferencias = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b", "llama-3.3-70b-versatile",
                    "meta-llama/llama-4-scout-17b-16e-instruct", "moonshotai/kimi-k2-instruct", "llama-3.1-8b-instant"]
    padroes = [r"gpt-oss", r"^qwen/", r"llama.*versatile", r"llama-4", r"kimi", r"deepseek", r"llama.*instant", r"llama", r"mixtral", r"gemma"]
    excluir = [r"whisper", r"tts", r"guard", r"compound", r"embed", r"orpheus", r"allam", r"saba", r"playai"]

    def listar_modelos(self) -> list[str]:
        http, dados, _ = base.requisitar(self.url_modelos, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Lista de modelos inesperada.")
        return [str(m.get("id")) for m in dados.get("data") or [] if isinstance(m, dict) and m.get("active", True)]

    def montar_requisicao(self, modelo, mensagens, max_tokens, temperatura):
        corpo = {"model": modelo, "messages": mensagens, "max_completion_tokens": max_tokens,
                 "temperature": temperatura, "stream": False}
        if "gpt-oss" in modelo:
            corpo["reasoning_effort"] = "low"
        return self.url_chat, self.cabecalhos(), corpo
