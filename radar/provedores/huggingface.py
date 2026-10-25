"""Hugging Face Inference Providers — crédito mensal gratuito minúsculo; para em HTTP 402."""
from __future__ import annotations

from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA


class HuggingFace(Provedor):
    id = "huggingface"
    nome = "Hugging Face"
    variaveis = ("HF_TOKEN",)
    link_chaves = "https://huggingface.co/settings/tokens"
    nota_gratuita = "Conta gratuita recebe crédito mensal muito pequeno (≈ US$ 0,10); ao esgotar, o roteador devolve 402 e o app para de usar."
    url_modelos = "https://router.huggingface.co/v1/models"
    url_chat = "https://router.huggingface.co/v1/chat/completions"
    preferencias = ["Qwen/Qwen3-32B", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct",
                    "deepseek-ai/DeepSeek-V3", "mistralai/Mistral-Small-24B-Instruct-2501", "meta-llama/Llama-3.1-8B-Instruct"]
    padroes = [r"^Qwen/Qwen3-\d+B$", r"Llama-3\.3-70B-Instruct", r"Qwen2\.5-72B-Instruct", r"DeepSeek-V3", r"Mistral.*Instruct",
               r"Llama-3\.1-8B-Instruct", r"Instruct"]
    excluir = [r"VL", r"Vision", r"Coder", r"Guard", r"embed", r"Embedding", r"whisper", r"GGUF", r"FP8", r"AWQ", r"Omni", r"Audio"]

    def listar_modelos(self) -> list[str]:
        http, quem, _ = base.requisitar("https://huggingface.co/api/whoami-v2", headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(quem, dict) or not quem.get("name"):
            raise ErroProvedor("chave_invalida", "Token Hugging Face não reconhecido.")
        http, dados, _ = base.requisitar(self.url_modelos, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Lista de modelos inesperada.")
        return [str(m.get("id")) for m in dados.get("data") or [] if isinstance(m, dict)]
