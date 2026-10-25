"""Cohere — chave de avaliação (trial), sem cartão, uso não comercial."""
from __future__ import annotations

from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA, texto_conteudo


class Cohere(Provedor):
    id = "cohere"
    nome = "Cohere"
    variaveis = ("COHERE_API_KEY",)
    link_chaves = "https://dashboard.cohere.com/api-keys"
    nota_gratuita = "Chave trial: ~20 req/min e 1.000 chamadas/mês somando todos os endpoints; uso não comercial."
    url_modelos = "https://api.cohere.com/v1/models?endpoint=chat&page_size=100"
    url_chat = "https://api.cohere.com/v2/chat"
    preferencias = ["command-a-03-2025", "command-r-plus-08-2024", "command-r-08-2024", "command-r7b-12-2024"]
    padroes = [r"^command-a-\d", r"^command-r-plus", r"^command-r(?!7b)", r"^command-r7b", r"^command-a", r"^command"]
    excluir = [r"embed", r"rerank", r"vision", r"translate", r"nightly", r"light"]

    def listar_modelos(self) -> list[str]:
        http, dados, _ = base.requisitar(self.url_modelos, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Lista de modelos inesperada.")
        return [str(m.get("name")) for m in dados.get("models") or [] if isinstance(m, dict)]

    def montar_requisicao(self, modelo, mensagens, max_tokens, temperatura):
        corpo = {"model": modelo, "messages": mensagens, "max_tokens": max_tokens, "temperature": temperatura, "stream": False}
        return self.url_chat, self.cabecalhos(), corpo

    def extrair_resposta(self, dados):
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Resposta inesperada da Cohere.")
        texto = texto_conteudo((dados.get("message") or {}).get("content"))
        uso = ((dados.get("usage") or {}).get("tokens") or {})
        return texto, {"entrada": uso.get("input_tokens"), "saida": uso.get("output_tokens"), "modelo_real": None}
