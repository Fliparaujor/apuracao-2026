"""Infraestrutura comum dos testes: TSE SIMULADO + pasta temporária isolada.

Tudo aqui é simulação. Nenhum teste chama provedores reais nem o TSE real.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import tse_simulado  # noqa: E402

_SIM = None


def tse_simulado_url() -> str:
    global _SIM
    if _SIM is None:
        _SIM = tse_simulado.iniciar(0)
    return _SIM[1]


class CasoBase(unittest.TestCase):
    """Cada classe de teste ganha RADAR_HOME próprio e caches limpos."""
    chaves_falsas: dict[str, str] = {}

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="radar-test-")
        cls._env_antigo = dict(os.environ)
        for v in ("GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "COHERE_API_KEY",
                  "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "HF_TOKEN", "PORT", "RADAR_BIND", "RADAR_TOKEN"):
            os.environ.pop(v, None)
        os.environ["RADAR_HOME"] = cls._tmp.name
        os.environ["RADAR_TSE_BASE"] = tse_simulado_url()
        os.environ["RADAR_SEM_COLETA"] = "1"
        os.environ.update(cls.chaves_falsas)
        from radar import db, tse, provedores
        from radar.cotas import COTAS
        tse.limpar_cache()
        tse._config_eleicoes = None
        provedores.limpar_cache_auth()
        COTAS._estados.clear()
        COTAS.reiniciar_sessao()
        tse_simulado.ESTADO.boletim = 3
        tse_simulado.ESTADO.final = False
        tse_simulado.ESTADO.vazio = False
        tse_simulado.ESTADO.indisponivel = False
        db.inicializar(Path(cls._tmp.name) / "radar.sqlite3")
        from radar import config
        folga = {"rpm": 500, "rpd": 5000, "tpm": 900000, "max_tokens_por_chamada": 50000}
        config.gravar_config({"limites_cotas": {p: dict(folga) for p in ("groq", "gemini", "mistral", "openrouter", "cohere", "cloudflare", "huggingface")}})

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._env_antigo)
        cls._tmp.cleanup()
