"""Mistral AI La Plateforme — plano gratuito (Experiment/Free), com verificação por telefone."""
from __future__ import annotations

from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA


class Mistral(Provedor):
    id = "mistral"
    nome = "Mistral"
    variaveis = ("MISTRAL_API_KEY",)
    link_chaves = "https://console.mistral.ai/api-keys"
    nota_gratuita = "Plano gratuito com ~1 req/s; exige conta verificada. Os limites atuais aparecem no console da Mistral."
    url_modelos = "https://api.mistral.ai/v1/models"
    url_chat = "https://api.mistral.ai/v1/chat/completions"
    preferencias = ["mistral-small-latest", "mistral-medium-latest", "open-mistral-nemo", "ministral-8b-latest",
                    "magistral-small-latest", "mistral-large-latest"]
    padroes = [r"^mistral-small", r"^mistral-medium", r"nemo", r"^ministral", r"^magistral", r"^mistral-large", r"^open-mixtral"]
    excluir = [r"embed", r"ocr", r"moderation", r"codestral", r"pixtral", r"voxtral", r"devstral", r"transcribe"]

    def listar_modelos(self) -> list[str]:
        http, dados, _ = base.requisitar(self.url_modelos, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Lista de modelos inesperada.")
        ids = []
        for m in dados.get("data") or []:
            if not isinstance(m, dict):
                continue
            caps = m.get("capabilities") or {}
            if caps and caps.get("completion_chat") is False:
                continue
            ids.append(str(m.get("id")))
        return ids
