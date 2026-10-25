import unittest
from unittest.mock import patch

import relatorio_local

class KeylessReportTests(unittest.TestCase):
    def fake(self, region="br"):
        return {
            "regiao":region,"horario_tse":"25/10/2026 17:10:00",
            "secoes_processadas_pct":25.5,
            "totalizacao_encerrada_tse":False,
            "votos_validos":200,
            "candidatos":[
                {"nome":"Pessoa 1","votos":110,"percentual":55.0},
                {"nome":"Pessoa 2","votos":90,"percentual":45.0}
            ],
            "fonte":"https://resultados.tse.jus.br/arquivo.json"
        }

    def test_build_without_any_ai_key(self):
        with patch.object(relatorio_local.inteligencia,"get_official",side_effect=lambda k,t:self.fake(k)):
            with patch.object(relatorio_local.inteligencia,"write_and_diff",return_value=None):
                data=relatorio_local.build("br")
        self.assertTrue(data["ok"])
        self.assertEqual(data["tipo"],"Análise descritiva automática (sem IA)")
        self.assertTrue(any("FATO DO TSE" in p for p in data["paragrafos"]))
        self.assertTrue(any("CÁLCULO" in p for p in data["paragrafos"]))
        self.assertTrue(any("LIMITE DOS DADOS" in p for p in data["paragrafos"]))
        self.assertIn("20", "\n".join(data["paragrafos"]))
        self.assertFalse(any("provavelmente vencer" in p for p in data["paragrafos"]))

    def test_missing_source_is_not_fake_report(self):
        def source(code,turn):
            raise RuntimeError("TSE sem conexão")
        with patch.object(relatorio_local.inteligencia,"get_official",side_effect=source):
            data=relatorio_local.build("br")
        self.assertFalse(data["ok"])
        self.assertFalse(data["paragrafos"])
        self.assertEqual(len(data["falhas"]),3)

    def test_scope_guard(self):
        with self.assertRaises(ValueError):
            relatorio_local.build("evil")

    def test_compare_preceding_local_snapshot(self):
        previous={"boletim_anterior":"25/10/2026 17:09:00",
                  "apuracao_anterior_pct":25.0,"validos_anterior":180,
                  "lider_anterior_numero":"22","lider_anterior_votos":100,
                  "lider_anterior_pct":55,
                  "mudanca_de_lideranca":True}
        with patch.object(relatorio_local.inteligencia,"get_official",side_effect=lambda k,t:self.fake(k)):
            with patch.object(relatorio_local.inteligencia,"write_and_diff",return_value=previous):
                data=relatorio_local.build("br")
        paragraph=next(p for p in data["paragrafos"] if p.startswith("MUDANÇA VERIFICADA"))
        self.assertIn("20",paragraph)
        self.assertIn("troca de liderança",paragraph)

if __name__ == "__main__":
    unittest.main()
