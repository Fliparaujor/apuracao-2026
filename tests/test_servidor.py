"""Testes da API local com servidor real em porta aleatória e TSE SIMULADO."""
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from base import CasoBase
import provedores_simulados as sim
import tse_simulado
from radar import coletor, servidor, provedores
from radar.provedores import base as pbase


class API(CasoBase):
    chaves_falsas = {"GROQ_API_KEY": "gsk_falsa_ok", "GEMINI_API_KEY": "AIza_falsa_ok"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.p = patch.object(pbase, "requisitar", sim.requisitar_simulado); cls.p.start()
        cls.srv = servidor.criar_servidor("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.p.stop()
        super().tearDownClass()

    def get(self, caminho, esperado=200):
        try:
            with urllib.request.urlopen(self.base + caminho, timeout=30) as r:
                return r.status, json.loads(r.read()), dict(r.headers)
        except urllib.error.HTTPError as e:
            corpo = e.read()
            try:
                return e.code, json.loads(corpo), dict(e.headers)
            except ValueError:
                return e.code, corpo, dict(e.headers)

    def post(self, caminho, corpo, tipo="application/json"):
        dados = json.dumps(corpo).encode() if isinstance(corpo, dict) else corpo
        req = urllib.request.Request(self.base + caminho, data=dados, headers={"Content-Type": tipo}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_saude_nao_confunde_chave_com_autenticacao(self):
        s, d, _ = self.get("/api/saude")
        self.assertTrue(d["ok"]); self.assertNotIn("ia_conectada", d)

    def test_estaticos_e_cabecalhos(self):
        with urllib.request.urlopen(self.base + "/") as r:
            html = r.read().decode(); h = dict(r.headers)
        self.assertIn("<title>Radar 2026", html)
        self.assertIn("Content-Security-Policy", h); self.assertEqual(h["X-Frame-Options"], "DENY")
        for rota in ("/app.js", "/app.css", "/sw.js", "/manifest.webmanifest", "/icones/icone-192.png", "/ao-vivo.html"):
            with urllib.request.urlopen(self.base + rota) as r:
                self.assertEqual(r.status, 200, rota)
        self.assertEqual(self.get("/radar/config.py")[0], 404)
        self.assertEqual(self.get("/../radar/config.py")[0], 404)
        self.assertEqual(self.get("/web/../server.py")[0], 404)

    def test_resultado_estados_governadores_historico(self):
        s, d, _ = self.get("/api/resultado?escopo=ce&cargo=presidente&agora=1")
        self.assertTrue(d["ok"]); self.assertEqual(d["nome_escopo"], "Ceará"); self.assertIn("atualidade", d); self.assertIn("variacao", d)
        s, d, _ = self.get("/api/resultado?escopo=ce13897")
        self.assertEqual(d["nome_escopo"], "Fortaleza")
        s, d, _ = self.get("/api/resultado?escopo=am&cargo=governador")
        self.assertEqual(d["cargo"], "governador")
        s, d, _ = self.get("/api/resultado?escopo=sp&cargo=governador")
        self.assertFalse(d["ok"]); self.assertIn("inventado", d["mensagem"])
        self.assertEqual(self.get("/api/resultado?escopo=../x")[0], 400)
        self.assertEqual(self.get("/api/resultado?escopo=br&cargo=senador")[0], 400)
        s, d, _ = self.get("/api/estados")
        self.assertEqual(len(d["estados"]), 27)
        s, d, _ = self.get("/api/governadores")
        self.assertIn("ufs", d)
        # boletim novo no simulado → histórico com 2 pontos
        tse_simulado.ESTADO.boletim += 1
        from radar import tse
        tse.limpar_cache()
        self.get("/api/resultado?escopo=ce&agora=1")
        s, d, _ = self.get("/api/historico?escopo=ce")
        self.assertGreaterEqual(d["boletins"], 2)
        self.assertGreaterEqual(d["contadores"][0]["boletins_novos"], 2)

    def test_analise_sem_ia_e_cenario(self):
        s, d, _ = self.get("/api/analise?escopo=br")
        self.assertEqual(d["tipo"], "Análise descritiva automática (sem IA)")
        self.assertTrue(d["por_tipo"]["fato"])
        s, d = self.post("/api/cenario", {"escopo": "br", "premissas": {"novos_votos_validos": [2000000]}})
        self.assertTrue(d["ok"]); self.assertEqual(len(d["cenarios"]), 1)

    def test_validacao_post(self):
        self.assertEqual(self.post("/api/cenario", b"x", "text/plain")[0], 415)
        self.assertEqual(self.post("/api/cenario", b"{bad", "application/json")[0], 400)
        self.assertEqual(self.post("/api/cenario", b"[]", "application/json")[0], 400)
        self.assertEqual(self.post("/api/inexistente", {})[0], 404)
        req = urllib.request.Request(self.base + "/api/cenario", data=b"{" + b"a" * 20000 + b"}", headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 413)

    def test_provedores_e_conselho_via_api(self):
        s, d, _ = self.get("/api/provedores?testar=1")
        groq = [p for p in d["provedores"] if p["id"] == "groq"][0]
        self.assertTrue(groq["autenticado"]); self.assertTrue(groq["pronto"]); self.assertEqual(groq["modelo"], "openai/gpt-oss-120b")
        self.assertNotIn("gsk_falsa", json.dumps(d))
        s, d, _ = self.get("/api/conselho/status")
        self.assertGreaterEqual(d["modelos_prontos"], 2)
        s, d = self.post("/api/conselho/reuniao", {"escopo": "br", "pergunta": "O que mudou?", "sessao": "api"})
        self.assertEqual(s, 202)
        ident = d["id"]
        for _ in range(600):
            s, j, _ = self.get("/api/conselho/reuniao/" + ident)
            if j["status"] != "em_andamento":
                break
            time.sleep(0.1)
        self.assertEqual(j["status"], "concluido", j.get("erro"))
        self.assertEqual(j["resultado"]["classificacao"], "deliberacao")
        self.assertNotIn("gsk_falsa", json.dumps(j))
        s, h, _ = self.get("/api/conselho/historico?sessao=api")
        self.assertEqual(len(h["reunioes"]), 1)
        s, c, _ = self.get("/api/conversas/" + str(h["reunioes"][0]["id"]))
        self.assertEqual(c["tipo"], "conselho")
        self.assertEqual(self.get("/api/conselho/reuniao/zzzzzzzzzzzz")[0], 404)
        s, d = self.post("/api/analista/perguntar", {"escopo": "ap", "pergunta": "x", "sessao": "api"})
        self.assertTrue(d["ia"]["ok"])

    def test_diagnostico_e_config(self):
        s, d, _ = self.get("/api/diagnostico?ia=1")
        self.assertTrue(d["tse"]["ok"]); self.assertTrue(d["banco"]["ok"])
        self.assertNotIn("gsk_falsa", json.dumps(d)); self.assertNotIn("AIza_falsa", d["texto"])
        self.assertIn("Groq: autenticado", d["texto"])
        s, d = self.post("/api/config", {"intervalo_coleta_segundos": 5, "rodadas_maximas": 3, "coleta_automatica": False, "bind": "0.0.0.0"})
        self.assertEqual(d["config"]["intervalo_coleta_segundos"], 15)
        self.assertEqual(d["config"]["bind"], "127.0.0.1")
        s, d, _ = self.get("/api/config")
        self.assertEqual(d["config"]["rodadas_maximas"], 3)
        self.post("/api/config", {"rodadas_maximas": 5})
        s, d = self.post("/api/provedores/ativar", {"provedor": "gemini", "ativo": False})
        self.assertIn("gemini", d["provedores_desativados"])
        self.post("/api/provedores/ativar", {"provedor": "gemini", "ativo": True})
        self.assertEqual(self.post("/api/provedores/ativar", {"provedor": "x"})[0], 400)

    def test_tse_indisponivel_nao_inventa(self):
        tse_simulado.ESTADO.indisponivel = True
        from radar import tse
        tse.limpar_cache()
        try:
            s, d, _ = self.get("/api/resultado?escopo=rr&agora=1")
            # rr já foi coletado via /api/estados? se sim, vem com aviso; senão, ok=False
            if d["ok"]:
                self.assertIn("aviso_coleta", d)
            else:
                self.assertIn("inventado", d["mensagem"])
            s, d, _ = self.get("/api/analise?escopo=zz")
            self.assertEqual(s, 503)
        finally:
            tse_simulado.ESTADO.indisponivel = False
            tse.limpar_cache()

    def test_coletor_um_ciclo(self):
        r = coletor.coletar_um("pe")
        self.assertTrue(r["ok"])
        self.assertFalse(coletor.coletar_um("pe")["novo"])
        e = coletor.estado()
        self.assertGreaterEqual(e["repetidos"], 1)


if __name__ == "__main__":
    unittest.main()
