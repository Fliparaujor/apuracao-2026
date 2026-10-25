"""Segurança: segredos nunca saem do servidor; frontend e repositório sem chaves."""
import json
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from base import CasoBase, RAIZ
import provedores_simulados as sim
from radar import config, diagnostico, provedores, conselho, db
from radar.provedores import base as pbase

PADROES = re.compile(r"gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|sk-or-v1-[0-9a-f]{20,}|hf_[A-Za-z0-9]{30,}")


class Seguranca(CasoBase):
    chaves_falsas = {"GROQ_API_KEY": "gsk_segredo_de_teste_1234567890ABC", "OPENROUTER_API_KEY": "sk-or-v1-ab12cd34ef56ab12cd34ef56ab12cd34"}

    def setUp(self):
        self.p = patch.object(pbase, "requisitar", sim.requisitar_simulado); self.p.start(); provedores.limpar_cache_auth()

    def tearDown(self):
        self.p.stop()

    def test_diagnostico_e_status_sem_segredos(self):
        d = diagnostico.executar(testar_ia=True)
        bruto = json.dumps(d, default=str) + diagnostico.texto(d)
        self.assertNotIn("gsk_segredo", bruto); self.assertNotIn("sk-or-v1-ab12", bruto)
        self.assertNotIn("gsk_segredo", json.dumps(provedores.status_consolidado()))
        self.assertNotIn("gsk_segredo", json.dumps(conselho.status_publico()))

    def test_erros_sao_mascarados(self):
        self.assertEqual(config.mascarar("Authorization: Bearer gsk_segredo_de_teste_1234567890ABC falhou"), "Authorization: Bearer [segredo] falhou")
        db.registrar_uso("groq", "m", False, 401, 1, 1, 0, "t", "token gsk_segredo_de_teste_1234567890ABC inválido")
        linha = db.conexao().execute("SELECT erro FROM uso_ia ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertNotIn("gsk_segredo", linha)

    def test_repositorio_sem_chaves_reais(self):
        for caminho in RAIZ.rglob("*"):
            if caminho.is_dir() or ".git" in caminho.parts or caminho.suffix in (".png", ".sqlite3") or "node_modules" in caminho.parts:
                continue
            try:
                texto = caminho.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in PADROES.finditer(texto):
                self.assertTrue("teste" in m.group(0).lower() or "falsa" in m.group(0).lower() or "ab12cd34" in m.group(0),
                                f"possível chave real em {caminho}: {m.group(0)[:8]}…")
        gitignore = (RAIZ / ".gitignore").read_text()
        self.assertIn("segredos.env", gitignore); self.assertIn(".env", gitignore)

    def test_frontend_nao_contem_chaves_nem_chamadas_externas(self):
        js = (RAIZ / "web" / "app.js").read_text()
        self.assertNotIn("api.groq.com", js); self.assertNotIn("googleapis", js); self.assertNotIn("resultados.tse.jus.br/oficial", js)
        self.assertTrue(all(linha.startswith("/api/") or not linha for linha in re.findall(r'fetch\(\s*"([^"]*)', js)))
        sw = (RAIZ / "web" / "sw.js").read_text()
        self.assertIn('startsWith("/api/")', sw)


if __name__ == "__main__":
    unittest.main()
