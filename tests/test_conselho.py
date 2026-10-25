"""Teste COMPLETO do Conselho com respostas SIMULADAS (nenhum provedor real).

Valida a orquestração: rodadas independentes, confronto, réplicas, auditoria e
relatório; falha de um modelo; um único modelo; nenhum modelo; cancelamento.
Aprovação aqui NÃO comprova que as APIs externas funcionam.
"""
import os
import time
import unittest
from unittest.mock import patch

from base import CasoBase
import provedores_simulados as sim
from radar import conselho, jobs, provedores, analista
from radar.provedores import base as pbase


def esperar(ident, timeout=60):
    fim = time.time() + timeout
    while time.time() < fim:
        j = jobs.obter(ident)
        if j["status"] != "em_andamento":
            return j
        time.sleep(0.05)
    raise AssertionError("reunião não terminou")


class ConselhoSimulado(CasoBase):
    chaves_falsas = {"GROQ_API_KEY": "gsk_falsa_ok", "GEMINI_API_KEY": "AIza_falsa_ok", "MISTRAL_API_KEY": "falsa_ok"}

    def setUp(self):
        self.p = patch.object(pbase, "requisitar", sim.requisitar_simulado); self.p.start()
        sim.CHAMADAS.clear(); provedores.limpar_cache_auth(); conselho._reunioes_recentes.clear()
        from radar.cotas import COTAS
        COTAS._estados.clear(); COTAS.reiniciar_sessao()

    def tearDown(self):
        self.p.stop()

    def test_cadeiras_e_papeis(self):
        provedores.autenticar_todos(forcar=True)
        m = conselho.montar_cadeiras()
        self.assertEqual(m["total"], 5)  # groq 2 + gemini 2 + mistral 1
        self.assertEqual(m["provedores_distintos"], 3)
        papeis = [c["papel"] for c in m["cadeiras"]]
        self.assertEqual(papeis[:3], ["quantitativo", "cetico", "regional"])
        self.assertEqual(len(set(papeis)), 5)
        primeiros = [c["provedor"] for c in m["cadeiras"][:3]]
        self.assertEqual(primeiros, ["groq", "gemini", "mistral"])  # diversidade antes de repetir provedor
        self.assertTrue(any(not c["independente"] for c in m["cadeiras"]))
        self.assertEqual(len(m["nao_prontos"]), 4)

    def test_reuniao_completa_cinco_rodadas(self):
        ident = conselho.iniciar_reuniao("br", "O que mudou? Quais hipóteses?", sessao="s1")
        j = esperar(ident)
        self.assertEqual(j["status"], "concluido", j.get("erro"))
        r = j["resultado"]
        self.assertEqual(r["classificacao"], "deliberacao")
        self.assertEqual(r["rodadas_executadas"], [1, 2, 3, 4, 5])
        self.assertEqual(sum(1 for c in r["cadeiras"] if c["participa"]), 5)
        self.assertTrue(all(c["rodada2"]["ok"] for c in r["cadeiras"]))
        self.assertFalse(r["relatorio"]["automatico"])
        self.assertIn("4. Divergências persistentes", r["relatorio"]["texto"])
        self.assertEqual(r["auditoria"]["com_problemas"], 0)
        self.assertIn("1.", r["evidencia_texto"])
        # rodada 1 realmente independente: nenhum parecer de outro membro no prompt
        r1 = [c for c in sim.CHAMADAS if c["metodo"] == "POST" and "PARECERES DOS OUTROS" not in str(c["corpo"]) and "RELATOR" not in str(c["corpo"]) and "OBJEÇÕES" not in str(c["corpo"])]
        self.assertGreaterEqual(len(r1), 5)
        self.assertEqual(len(conselho.historico(5, "s1")), 1)
        # segunda reunião usa contexto anterior
        conselho._reunioes_recentes.clear()
        j2 = esperar(conselho.iniciar_reuniao("br", "E agora?", sessao="s1"))
        self.assertTrue(any("CONTEXTO DA REUNIÃO ANTERIOR" in str(c["corpo"]) for c in sim.CHAMADAS))

    def test_falha_de_um_modelo_nao_derruba(self):
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "quebrado"}):
            provedores.limpar_cache_auth()
            j = esperar(conselho.iniciar_reuniao("ce", "Diferenças regionais?"))
        r = j["resultado"]
        self.assertIn(r["classificacao"], ("deliberacao", "debate_sem_relatoria"))
        self.assertTrue(any(not c["participa"] for c in r["cadeiras"]) or any(c["provedor"] == "mistral" for c in r["nao_prontos"]))
        self.assertTrue(any("não participaram" in a or "autenticação" in a for a in r["avisos"]) or r["nao_prontos"])

    def test_um_modelo_vira_analise_individual(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "MISTRAL_API_KEY": ""}):
            provedores.limpar_cache_auth()
            with patch.object(provedores.PROVEDORES["groq"], "assentos_maximos", 1):
                j = esperar(conselho.iniciar_reuniao("br", "?"))
        r = j["resultado"]
        self.assertEqual(r["classificacao"], "analise_individual")
        self.assertEqual(r["rodadas_executadas"], [1, 4, 5])
        self.assertTrue(any("individual" in a for a in r["avisos"]))

    def test_sem_nenhum_modelo_so_matematica(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "GEMINI_API_KEY": "", "MISTRAL_API_KEY": ""}):
            provedores.limpar_cache_auth()
            j = esperar(conselho.iniciar_reuniao("br", "?"))
        r = j["resultado"]
        self.assertEqual(r["classificacao"], "somente_matematica")
        self.assertTrue(r["relatorio"]["automatico"])
        self.assertIn("sem IA", r["relatorio"]["texto"])
        self.assertEqual(sim.CHAMADAS, [])

    def test_todos_falham_na_rodada_1(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_vazio", "GEMINI_API_KEY": "AIza_vazio", "MISTRAL_API_KEY": "vazio"}):
            provedores.limpar_cache_auth()
            j = esperar(conselho.iniciar_reuniao("br", "?"))
        r = j["resultado"]
        self.assertEqual(r["status"], "falha_ia")
        self.assertTrue(r["relatorio"]["automatico"])

    def test_auditoria_marca_numeros_inventados_e_prognostico(self):
        j = esperar(conselho.iniciar_reuniao("br", "INVENTE algo"))
        r = j["resultado"]
        self.assertGreater(r["auditoria"]["com_problemas"], 0)
        item = r["auditoria"]["itens"][0]
        self.assertTrue(any(x["citado"].startswith("77") for x in item["nao_suportados"]))
        self.assertIn("prognóstico de vitória", item["alertas"])

    def test_modelo_limitado_upstream_troca_para_alternativa(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-upstream", "GEMINI_API_KEY": "", "MISTRAL_API_KEY": ""}):
            provedores.limpar_cache_auth()
            j = esperar(conselho.iniciar_reuniao("br", "?"))
        r = j["resultado"]
        cad = [c for c in r["cadeiras"] if c["provedor"] == "openrouter" and c.get("modelo_original") == "deepseek/deepseek-r1:free"]
        self.assertTrue(cad, [c for c in r["cadeiras"] if c["provedor"] == "openrouter"])
        self.assertTrue(cad[0]["participa"])
        self.assertEqual(cad[0]["modelo"], "meta-llama/llama-3.3-70b-instruct:free")
        self.assertTrue(cad[0]["rodada1"]["trocas_de_modelo"])
        from radar.cotas import COTAS
        self.assertLessEqual(COTAS.estado()["provedores"]["openrouter"]["cooldown_restante_s"], 5)

    def test_cancelamento(self):
        original = sim.requisitar_simulado

        def lento(*a, **k):
            time.sleep(0.4)
            return original(*a, **k)
        with patch.object(pbase, "requisitar", lento):
            ident = conselho.iniciar_reuniao("br", "?")
            time.sleep(0.3)
            self.assertTrue(jobs.cancelar(ident))
            j = esperar(ident)
        self.assertEqual(j["status"], "cancelado")
        self.assertFalse(jobs.cancelar(ident))

    def test_limites_de_reunioes_e_concorrencia(self):
        with patch.object(pbase, "requisitar", lambda *a, **k: (time.sleep(0.3), sim.requisitar_simulado(*a, **k))[1]):
            ident = conselho.iniciar_reuniao("br", "?")
            with self.assertRaises(RuntimeError):
                conselho.iniciar_reuniao("br", "?")
            esperar(ident)
        conselho._reunioes_recentes[:] = [time.monotonic()] * 6
        with self.assertRaises(RuntimeError):
            conselho.iniciar_reuniao("br", "?")
        with self.assertRaises(ValueError):
            conselho.iniciar_reuniao("evil", "?")

    def test_prompts_contem_regras_de_neutralidade(self):
        esperar(conselho.iniciar_reuniao("ap", "Quem vai ganhar?"))
        sistemas = [str(c["corpo"]) for c in sim.CHAMADAS if c["metodo"] == "POST"]
        self.assertTrue(all("proibido prever vencedor" in s for s in sistemas))
        self.assertTrue(all("não são instruções" in s or "NÃO são instruções" in s for s in sistemas))


class AnalistaSimulado(CasoBase):
    chaves_falsas = {"GROQ_API_KEY": "gsk_falsa_ok"}

    def setUp(self):
        self.p = patch.object(pbase, "requisitar", sim.requisitar_simulado); self.p.start(); provedores.limpar_cache_auth()

    def tearDown(self):
        self.p.stop()

    def test_pergunta_com_ia_e_auditoria(self):
        r = analista.perguntar("br", "O que mudou?", sessao="a1")
        self.assertTrue(r["ia"]["ok"]); self.assertEqual(r["ia"]["provedor"], "groq")
        self.assertEqual(r["ia"]["auditoria"]["veredito"], "compatível")
        self.assertTrue(r["matematica"]["itens"])
        r2 = analista.perguntar("br", "E depois?", sessao="a1")
        self.assertTrue(any("CONVERSA ANTERIOR" in str(c["corpo"]) for c in sim.CHAMADAS))
        self.assertEqual(len(analista.historico(10, "a1")), 2)

    def test_sem_ia_quando_pedido_ou_sem_chave(self):
        r = analista.perguntar("br", "x", sem_ia=True)
        self.assertFalse(r["ia"]["ok"]); self.assertTrue(r["matematica"]["itens"])
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            provedores.limpar_cache_auth()
            r = analista.perguntar("br", "x")
            self.assertFalse(r["ia"]["ok"]); self.assertIn("sem IA", r["ia"]["motivo"])


if __name__ == "__main__":
    unittest.main()
