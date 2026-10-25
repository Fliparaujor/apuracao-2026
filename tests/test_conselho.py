import json
import os
import unittest
from unittest.mock import patch

import conselho

class CouncilTests(unittest.TestCase):
    def make_evidence(self):
        return {
            "escopo": {"regiao": "br", "horario_tse": "25/10/2026 17:40", "secoes_apuradas_pct": 45, "votos_validos": 123,
                      "candidatos":[{"numero":"13","nome":"Teste A","votos":60,"percentual":48.8},
                                    {"numero":"22","nome":"Teste B","votos":63,"percentual":51.2}],
                      "fonte": "https://resultados.tse.jus.br/arquivo.json"},
            "brasil": None,
            "primeiro_turno_historico_mesma_regiao": {"indisponivel":"no"},
            "estados_parciais": [],
            "comparacao_com_boletim_anterior_neste_termux": None,
            "cenarios_aritmeticos_sem_previsao": [],
            "falhas_de_coleta": {},
            "aviso": "a"
        }

    def test_status_does_not_expose_secret(self):
        with patch.dict(os.environ, {"GROQ_API_KEY":"top-secret-test","GEMINI_API_KEY":"","MISTRAL_API_KEY":"","COHERE_API_KEY":"","OPENROUTER_API_KEY":""}):
            result=conselho.public_status()
            self.assertEqual(result["active_members"],2)
            self.assertEqual(result["independent_providers"],1)
            self.assertNotIn("top-secret-test",json.dumps(result))
            self.assertEqual(result["members"][0]["provider"], "Groq")

    def test_openrouter_never_falls_back_to_paid_model(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY":"test-key"}):
            with patch.object(conselho, "http_json", return_value={"model":"free/test-model","choices":[{"message":{"content":"Texto"}}]}) as call:
                seat=next(x for x in conselho.SEATS if x["provider"]=="OpenRouter")
                result=conselho.consult(seat,"S","P")
                self.assertEqual(result["text"],"Texto")
                req=call.call_args.args[1]
                self.assertEqual(req["model"],"openrouter/free")
                self.assertEqual(req["models"],["openrouter/free"])

    def test_full_session_uses_distinct_critical_rounds(self):
        fake1={"id":"groq_oss","name":"GPT OSS","provider":"Groq","model":"x","role":"Quantitativo","ok":True,"text":"Fato TSE."}
        fake2={"id":"groq_qwen","name":"Qwen","provider":"Groq","model":"y","role":"Cético","ok":True,"text":"Viés de seleção."}
        def initial(s,p):return fake1 if s["id"]=="groq_oss" else fake2
        def critique(s,items,p):
            self.assertEqual(len(items),2)
            return {"id":s["id"],"name":s["name"],"provider":s["provider"],"role":s["role"],"ok":True,"text":"Discordo."}
        with patch.dict(os.environ,{"GROQ_API_KEY":"dummy","MISTRAL_API_KEY":"","OPENROUTER_API_KEY":"","COHERE_API_KEY":"","GEMINI_API_KEY":""}):
            with patch.object(conselho, "_last_run",0),patch.object(conselho.inteligencia,"collect",return_value=self.make_evidence()),patch.object(conselho,"seat_result",side_effect=initial),patch.object(conselho,"critique_result",side_effect=critique),patch.object(conselho,"final_summary",return_value=("Há divergências.",True,"GPT OSS")):
                result=conselho.deliberate({"scope":"br","question":"?"})
                self.assertEqual(result["status"],"relatorio")
                self.assertEqual(len(result["membros"]),2)
                self.assertEqual(len(result["replicas"]),2)
                self.assertEqual(result["provedores_validos"],1)
                self.assertIn("menos independente",result["avisos"][0])

    def test_no_fake_consensus_if_only_one_model_responds(self):
        def initial(s,p):
            if s["id"]=="groq_oss":
                return {"id":"groq_oss","name":"GPT OSS","provider":"Groq","role":"Quantitativo","ok":True,"text":"Fato"}
            return {"id":"groq_qwen","name":"Qwen","provider":"Groq","role":"Cético","ok":False,"error":"rate limit"}
        with patch.dict(os.environ,{"GROQ_API_KEY":"dummy","MISTRAL_API_KEY":"","OPENROUTER_API_KEY":"","COHERE_API_KEY":"","GEMINI_API_KEY":""}):
            with patch.object(conselho,"_last_run",0),patch.object(conselho.inteligencia,"collect",return_value=self.make_evidence()),patch.object(conselho,"seat_result",side_effect=initial):
                result=conselho.deliberate({"scope":"br"})
                self.assertEqual(result["status"],"insuficiente")
                self.assertEqual(result["sintese"],"")
                self.assertEqual(result["conselheiros_validos"],1)

    def test_empty_config_and_scope_rejected(self):
        with patch.dict(os.environ,{"GROQ_API_KEY":"","MISTRAL_API_KEY":"","OPENROUTER_API_KEY":"","COHERE_API_KEY":"","GEMINI_API_KEY":""}):
            with self.assertRaises(ValueError):
                conselho.deliberate({"scope":"br"})
        with self.assertRaises(ValueError):
            conselho.deliberate({"scope":"https://evil.example"})

if __name__=="__main__":
    unittest.main()
