import json
import os
import stat
import unittest
from unittest.mock import patch

from base import CasoBase
import provedores_simulados as sim
from radar import config, provedores
from radar.provedores import base as pbase
from radar.provedores.base import ErroProvedor, classificar_http


class Segredos(CasoBase):
    def test_arquivo_600_e_mascaramento(self):
        config.gravar_segredo("GROQ_API_KEY", "gsk_teste1234567890abcdefghij")
        caminho = config.caminho_segredos()
        self.assertEqual(stat.S_IMODE(caminho.stat().st_mode) & 0o077, 0)
        self.assertTrue(config.permissoes_segredos_ok())
        self.assertEqual(config.segredo("GROQ_API_KEY"), "gsk_teste1234567890abcdefghij")
        self.assertEqual(config.origem_segredo("GROQ_API_KEY"), "arquivo")
        self.assertEqual(config.mascarar("erro: Bearer gsk_teste1234567890abcdefghij e AIzaTesteABCDEFGHIJKLMNOPQRSTUVWXYZ01"), "erro: Bearer [segredo] e [segredo]")
        config.remover_segredo("GROQ_API_KEY")
        self.assertEqual(config.segredo("GROQ_API_KEY"), "")
        with self.assertRaises(ValueError):
            config.gravar_segredo("OUTRA", "x")
        with self.assertRaises(ValueError):
            config.gravar_segredo("GROQ_API_KEY", "a\nb")

    def test_ambiente_tem_precedencia(self):
        config.gravar_segredo("MISTRAL_API_KEY", "arquivo")
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "ambiente"}):
            self.assertEqual(config.segredo("MISTRAL_API_KEY"), "ambiente")
            self.assertEqual(config.origem_segredo("MISTRAL_API_KEY"), "ambiente")
        config.remover_segredo("MISTRAL_API_KEY")


class ClassificacaoHTTP(CasoBase):
    def test_categorias(self):
        self.assertEqual(classificar_http(401, "").categoria, "chave_invalida")
        self.assertEqual(classificar_http(403, "").categoria, "sem_permissao")
        self.assertEqual(classificar_http(404, "").categoria, "modelo_indisponivel")
        self.assertEqual(classificar_http(402, "").categoria, "pagamento")
        e = classificar_http(429, "Please try again in 1.5s")
        self.assertEqual(e.categoria, "limite"); self.assertAlmostEqual(e.retry_after, 1.5)
        self.assertEqual(classificar_http(503, "").categoria, "servidor")
        self.assertEqual(classificar_http(400, "x").categoria, "formato")

    def test_somente_https(self):
        with self.assertRaises(ErroProvedor):
            pbase.requisitar("http://api.groq.com/x")


class Adaptadores(CasoBase):
    chaves_falsas = {"GROQ_API_KEY": "gsk_falsa_ok", "GEMINI_API_KEY": "AIza_falsa_ok", "MISTRAL_API_KEY": "falsa_ok",
                     "OPENROUTER_API_KEY": "sk-or-v1-falsa", "COHERE_API_KEY": "falsa", "CLOUDFLARE_API_TOKEN": "falsa",
                     "CLOUDFLARE_ACCOUNT_ID": "0123456789abcdef0123456789abcdef", "HF_TOKEN": "hf_falsa"}

    def setUp(self):
        self.p = patch.object(pbase, "requisitar", sim.requisitar_simulado); self.p.start()
        sim.CHAMADAS.clear(); provedores.limpar_cache_auth()

    def tearDown(self):
        self.p.stop()

    def test_autentica_e_descobre_modelos_em_todos(self):
        esperados = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-2.5-flash", "mistral": "mistral-small-latest",
                     "openrouter": "deepseek/deepseek-r1:free", "cohere": "command-a-03-2025",
                     "cloudflare": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "huggingface": "Qwen/Qwen3-32B"}
        for ident, modelo in esperados.items():
            r = provedores.autenticar(ident, forcar=True)
            self.assertTrue(r["ok"], f"{ident}: {r}")
            self.assertEqual(r["modelo"], modelo, ident)
            self.assertNotIn("falsa", json.dumps(r))
        status = provedores.status_consolidado()
        self.assertEqual(sum(1 for s in status if s["pronto"]), 7)
        self.assertTrue(all(s["autenticado"] for s in status))

    def test_chat_padronizado_em_todos(self):
        for ident in provedores.ORDEM:
            p = provedores.obter(ident)
            auth = provedores.autenticar(ident, forcar=True)
            r = p.conversar(auth["modelo"], [{"role": "system", "content": "regras"}, {"role": "user", "content": "parcial 1.204.715 votos 52,02%"}], max_tokens=200, contexto="teste")
            self.assertIn("1.204.715", r["texto"], ident)
            self.assertEqual(r["provedor"], ident)
            self.assertGreater(r["tokens_entrada"], 0)

    def test_groq_envia_parametros_certos(self):
        p = provedores.obter("groq")
        url, cab, corpo = p.montar_requisicao("openai/gpt-oss-120b", [{"role": "user", "content": "x"}], 300, 0.2)
        self.assertIn("max_completion_tokens", corpo); self.assertEqual(corpo["reasoning_effort"], "low")
        self.assertNotIn("cf-aig-gateway-id", cab)

    def test_openrouter_recusa_modelo_pago(self):
        p = provedores.obter("openrouter")
        with self.assertRaises(ErroProvedor) as cm:
            p.montar_requisicao("openai/gpt-4o", [], 10, 0)
        self.assertEqual(cm.exception.categoria, "pagamento")
        provedores.autenticar("openrouter", forcar=True)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-pago"}):
            with self.assertRaises(ErroProvedor) as cm:
                p.conversar("deepseek/deepseek-r1:free", [{"role": "user", "content": "x"}], 10)
            self.assertEqual(cm.exception.categoria, "pagamento")
        corpo = [c for c in sim.CHAMADAS if "chat/completions" in c["url"] and "openrouter" in c["url"]][-1]["corpo"]
        self.assertFalse(corpo["provider"]["allow_fallbacks"])

    def test_cloudflare_valida_conta_e_prefixo(self):
        p = provedores.obter("cloudflare")
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "curto"}):
            with self.assertRaises(ErroProvedor):
                p.listar_modelos()
        with self.assertRaises(ErroProvedor):
            p.montar_requisicao("@hf/x", [], 10, 0)

    def test_gemini_formato(self):
        p = provedores.obter("gemini")
        url, cab, corpo = p.montar_requisicao("gemini-2.5-flash", [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], 100, 0.1)
        self.assertTrue(url.endswith("/models/gemini-2.5-flash:generateContent"))
        self.assertIn("x-goog-api-key", cab); self.assertEqual(corpo["systemInstruction"]["parts"][0]["text"], "S")
        with self.assertRaises(ErroProvedor):
            p.montar_requisicao("../evil", [], 1, 0)

    def test_erros_http_viram_estados(self):
        casos = {"invalida": "chave_invalida", "limite": "limite", "quebrado": "erro", "semrede": "rede"}
        for marca, estado in casos.items():
            with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_" + marca}):
                provedores.limpar_cache_auth("groq")
                r = provedores.autenticar("groq", forcar=True)
                self.assertFalse(r["ok"]); self.assertEqual(r["estado"], estado, marca)
                self.assertNotIn(marca, r.get("mensagem", "") if marca != "limite" else "")
        from radar.cotas import COTAS
        COTAS.reativar("groq")
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_vazio"}):
            with self.assertRaises(ErroProvedor) as cm:
                provedores.obter("groq").conversar("openai/gpt-oss-120b", [{"role": "user", "content": "x"}], 10)
            self.assertEqual(cm.exception.categoria, "formato")

    def test_sem_chave_nao_e_autenticado(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            provedores.limpar_cache_auth("groq")
            r = provedores.autenticar("groq", forcar=True)
            self.assertEqual(r["estado"], "sem_chave")
            s = [x for x in provedores.status_consolidado() if x["id"] == "groq"][0]
            self.assertFalse(s["configurado"]); self.assertFalse(s["pronto"])
            with self.assertRaises(ErroProvedor):
                provedores.obter("groq").conversar("m", [], 1)

    def test_401_desativa_e_cotas_bloqueiam(self):
        from radar.cotas import COTAS
        with patch.dict(os.environ, {"COHERE_API_KEY": "invalida"}):
            provedores.limpar_cache_auth("cohere")
            provedores.autenticar("cohere", forcar=True)
            s = [x for x in provedores.status_consolidado() if x["id"] == "cohere"][0]
            self.assertFalse(s["pronto"]); self.assertIn("credencial", s["cota"]["desativado"])
        COTAS.reativar("cohere")


if __name__ == "__main__":
    unittest.main()
