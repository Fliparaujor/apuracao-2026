"""OpenRouter — somente modelos gratuitos (`:free`, preço zero). Sem fallback pago."""
from __future__ import annotations

from . import base
from .base import Provedor, ErroProvedor, TIMEOUT_LISTA


class OpenRouter(Provedor):
    id = "openrouter"
    nome = "OpenRouter"
    variaveis = ("OPENROUTER_API_KEY",)
    link_chaves = "https://openrouter.ai/settings/keys"
    nota_gratuita = "Modelos ':free' têm limite diário baixo (dezenas de requisições) para contas sem crédito."
    assentos_maximos = 2
    url_modelos = "https://openrouter.ai/api/v1/models"
    url_chat = "https://openrouter.ai/api/v1/chat/completions"
    padroes = [r"deepseek.*:free", r"qwen.*:free", r"llama.*:free", r"gemma.*:free", r"mistral.*:free", r"nemotron.*:free",
               r"glm.*:free", r"kimi.*:free", r".*:free$"]
    excluir = [r"vision", r"vl", r"image", r"coder", r"guard", r"embed", r"tts", r"whisper"]
    _gratis: set[str] = set()

    def listar_modelos(self) -> list[str]:
        # A lista é pública; a chave é validada à parte em /auth/key.
        http, dados, _ = base.requisitar(self.url_modelos, headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict):
            raise ErroProvedor("formato", "Lista de modelos inesperada.")
        gratis = []
        for m in dados.get("data") or []:
            if not isinstance(m, dict):
                continue
            preco = m.get("pricing") or {}
            try:
                zero = float(preco.get("prompt", "1") or 0) == 0 and float(preco.get("completion", "1") or 0) == 0
            except (TypeError, ValueError):
                zero = False
            ident = str(m.get("id") or "")
            if ident.endswith(":free") and zero:
                ctx = int(m.get("context_length") or 0)
                if ctx >= 16000:
                    gratis.append(ident)
        self._gratis = set(gratis)
        self._validar_chave()
        return gratis

    def _validar_chave(self):
        http, dados, _ = base.requisitar("https://openrouter.ai/api/v1/auth/key", headers=self.cabecalhos(), timeout=TIMEOUT_LISTA)
        if not isinstance(dados, dict) or "data" not in dados:
            raise ErroProvedor("chave_invalida", "A chave OpenRouter não foi reconhecida.")

    def montar_requisicao(self, modelo, mensagens, max_tokens, temperatura):
        if not modelo.endswith(":free"):
            raise ErroProvedor("pagamento", "Recusado: o OpenRouter só é usado com modelos ':free'.")
        corpo = {"model": modelo, "messages": mensagens, "max_tokens": max_tokens, "temperature": temperatura,
                 "stream": False, "provider": {"allow_fallbacks": False, "data_collection": "deny"}}
        cab = self.cabecalhos() | {"HTTP-Referer": "https://github.com/Fliparaujor/apuracao-2026", "X-Title": "Radar 2026"}
        return self.url_chat, cab, corpo

    def extrair_resposta(self, dados):
        texto, uso = super().extrair_resposta(dados)
        real = str(uso.get("modelo_real") or "")
        if real and not real.endswith(":free") and self._gratis and real not in self._gratis:
            raise ErroProvedor("pagamento", f"O OpenRouter roteou para um modelo fora da lista gratuita ({real}); resposta descartada.")
        return texto, uso
