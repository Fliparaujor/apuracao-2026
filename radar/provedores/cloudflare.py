"""Cloudflare Workers AI — plano Workers Free (10 mil Neurons/dia; excesso é negado, não cobrado)."""
from __future__ import annotations

import re

from .. import config
from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA


class Cloudflare(Provedor):
    id = "cloudflare"
    nome = "Cloudflare Workers AI"
    variaveis = ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
    link_chaves = "https://dash.cloudflare.com/?to=/:account/ai/workers-ai"
    nota_gratuita = "Workers Free: 10.000 Neurons/dia; mantenha a conta no plano Free para que o excesso seja negado em vez de cobrado."
    preferencias = ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/openai/gpt-oss-120b", "@cf/meta/llama-4-scout-17b-16e-instruct",
                    "@cf/qwen/qwen3-30b-a3b-fp8", "@cf/meta/llama-3.1-8b-instruct-fast", "@cf/meta/llama-3.1-8b-instruct"]
    padroes = [r"^@cf/meta/llama-3\.3", r"^@cf/openai/gpt-oss", r"^@cf/meta/llama-4", r"^@cf/qwen/qwen3", r"^@cf/meta/llama-3\.1.*instruct",
               r"^@cf/mistral", r"^@cf/.*instruct"]
    excluir = [r"guard", r"embed", r"whisper", r"vision", r"coder", r"-sft", r"awq$", r"@hf/", r"bge", r"m2m100", r"tts", r"aura"]

    def _conta(self) -> str:
        conta = config.segredo("CLOUDFLARE_ACCOUNT_ID")
        if not re.fullmatch(r"[0-9a-fA-F]{32}", conta or ""):
            raise ErroProvedor("formato", "CLOUDFLARE_ACCOUNT_ID inválido: deve ter 32 caracteres hexadecimais.")
        return conta

    def listar_modelos(self) -> list[str]:
        conta = self._conta()
        http, verif, _ = base.requisitar("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not (isinstance(verif, dict) and verif.get("success")):
            raise ErroProvedor("chave_invalida", "Token Cloudflare não verificado.")
        url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/models/search?task=Text%20Generation&per_page=100"
        http, dados, _ = base.requisitar(url, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict) or not dados.get("success"):
            raise ErroProvedor("sem_permissao", "O token não tem permissão Workers AI (Account.Workers AI: Read/Edit).")
        return [str(m.get("name")) for m in dados.get("result") or [] if isinstance(m, dict) and str(m.get("name", "")).startswith("@cf/")]

    def montar_requisicao(self, modelo, mensagens, max_tokens, temperatura):
        if not modelo.startswith("@cf/"):
            raise ErroProvedor("pagamento", "Somente modelos '@cf/' hospedados no Workers AI são usados.")
        url = f"https://api.cloudflare.com/client/v4/accounts/{self._conta()}/ai/v1/chat/completions"
        corpo = {"model": modelo, "messages": mensagens, "max_tokens": max_tokens, "temperature": temperatura, "stream": False}
        return url, self.cabecalhos(), corpo
