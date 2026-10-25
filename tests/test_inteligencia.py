import os
import unittest
from unittest.mock import patch
import inteligencia


class RadarAnalystTests(unittest.TestCase):
    def sample(self):
        return {
            "dg": "25/10/2026", "hg": "17:20:00", "tf": "n",
            "carg": [{"agr": [
                {"par": [{"sg": "PT", "cand": [{"n": "13", "nmu": "Lula", "vap": "1.234.567", "pvap": "49,20"}]}]},
                {"par": [{"sg": "PL", "cand": [{"n": "22", "nmu": "Flávio", "vap": "1.274.700", "pvap": "50,80"}]}]},
            ]}],
            "s": {"pst": "42,55", "st": "212445", "ts": "499248"},
            "v": {"vv": "2.509.267", "vb": "50", "tvn": "25"},
            "e": {"te": "158745502", "c": "3.000.000"},
        }

    def test_official_url_round_two(self):
        self.assertEqual(
            inteligencia.url_for("br", 2),
            "https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json"
        )
        self.assertIn("ce13897-c0001-e006258", inteligencia.url_for("ce13897", 2))
        self.assertIn("6257", inteligencia.url_for("ap", 1))

    def test_disallow_untrusted_scopes(self):
        for value in ("../", "https://evil", "zz", "ce12345", ""):
            with self.assertRaises(ValueError):
                inteligencia.url_for(value, 2)

    def test_normalize_votes_and_progress(self):
        x = inteligencia.normalize(self.sample(), "br", 2)
        self.assertEqual(x["secoes_processadas_pct"], 42.55)
        self.assertEqual(x["candidatos"][0]["numero"], "22")
        self.assertEqual(x["candidatos"][0]["votos"], 1274700)
        self.assertEqual(x["votos_validos"], 2509267)
        self.assertEqual(x["comparecimento"], 3000000)

    def test_conditional_math_is_explicitly_hypothetical(self):
        x = inteligencia.normalize(self.sample(), "br", 2)
        scenarios = inteligencia.conditional_math(x)
        self.assertEqual(len(scenarios), 4)
        self.assertEqual(scenarios[0]["novos_votos_validos_HIPOTETICOS"], 2000000)
        self.assertGreater(scenarios[0]["candidato_que_esta_atras_precisaria_mais_de_pct_desses_votos"], 50)

    def test_requires_private_api_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(RuntimeError):
                inteligencia.run({"scope": "br", "mode": "resumo"})

if __name__ == "__main__":
    unittest.main()
