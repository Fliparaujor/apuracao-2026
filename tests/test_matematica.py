import unittest

from base import CasoBase
from radar import matematica as m


def snap(**kw):
    base = {"escopo": "br", "nome_escopo": "Brasil", "cargo": "presidente", "cargo_nome": "Presidente", "turno": 2, "horario_tse": "25/10/2026 19:15:33",
            "secoes_pct": 1.86, "secoes_totalizadas": 9299, "secoes_total": 499248, "votos_validos": 2315908, "brancos": 24046, "nulos": 45088,
            "brancos_pct": 1.01, "nulos_pct": 1.89, "comparecimento": 2385042, "eleitorado_secoes_totalizadas": 3194828, "abstencao": 809363,
            "candidatos": [{"numero": "13", "nome": "LULA", "votos": 1204715, "percentual": 52.02}, {"numero": "22", "nome": "FLAVIO BOLSONARO", "votos": 1111193, "percentual": 47.98}],
            "fonte": "https://resultados.tse.jus.br/x.json"}
    base.update(kw)
    return base


class Motor(CasoBase):
    def test_diferencas(self):
        itens = m.diferencas(snap())
        d = itens[0]
        self.assertEqual(d["tipo"], "calculo")
        self.assertEqual(d["diferenca_votos"], 93522)
        self.assertEqual(d["diferenca_pp"], 4.04)
        self.assertIn("93.522", d["texto"])
        self.assertTrue(any(i["tipo"] == "limitacao" for i in itens))
        self.assertEqual(m.diferencas(snap(candidatos=[], votos_validos=0))[0]["tipo"], "limitacao")

    def test_variacao_e_troca_de_lideranca(self):
        ant = snap(horario_tse="25/10/2026 19:12:31", votos_validos=2103669, secoes_pct=1.69,
                   candidatos=[{"numero": "22", "nome": "FLAVIO BOLSONARO", "votos": 1095856, "percentual": 52.09}, {"numero": "13", "nome": "LULA", "votos": 1007813, "percentual": 47.91}])
        itens = m.variacao(ant, snap())
        self.assertTrue(any(i.get("mudanca_lideranca") for i in itens))
        entre = itens[0]
        self.assertEqual(entre["delta_validos"], 212239)
        self.assertEqual(entre["delta_secoes_pp"], 0.17)
        self.assertEqual(m.variacao(None, snap())[0]["tipo"], "limitacao")

    def test_regional_e_primeiro_turno(self):
        estados = {"ce": snap(escopo="ce", secoes_pct=0.14, votos_validos=8728, candidatos=[{"numero": "13", "nome": "LULA", "votos": 5789, "percentual": 66.3}, {"numero": "22", "nome": "FLAVIO BOLSONARO", "votos": 2939, "percentual": 33.7}]),
                   "sp": snap(escopo="sp", secoes_pct=3.0, votos_validos=300000, candidatos=[{"numero": "22", "nome": "FLAVIO BOLSONARO", "votos": 170000, "percentual": 56.67}, {"numero": "13", "nome": "LULA", "votos": 130000, "percentual": 43.33}]),
                   "am": None}
        itens = m.regional(estados, snap())
        self.assertIn("Lula lidera em 1 UF(s): CE", itens[0]["texto"])
        self.assertTrue(any("atrasada" in i["titulo"] for i in itens))
        primeiro = snap(turno=1, horario_tse="04/10/2026 23:59:00", secoes_pct=100, votos_validos=118000000,
                        candidatos=[{"numero": "22", "nome": "FLAVIO BOLSONARO", "votos": 55546567, "percentual": 47.03}, {"numero": "13", "nome": "LULA", "votos": 53337932, "percentual": 45.16}, {"numero": "15", "nome": "X", "votos": 9000000, "percentual": 7.81}])
        pt = m.primeiro_turno(snap(), primeiro)
        self.assertTrue(any("7,81" in i["texto"] for i in pt))
        self.assertTrue(any(i["tipo"] == "limitacao" and "transferência" in i["texto"] for i in pt))
        self.assertEqual(m.primeiro_turno(snap(), None)[0]["tipo"], "limitacao")

    def test_cenarios_sem_probabilidade(self):
        c = m.cenarios(snap(), {"novos_votos_validos": [1000000, 50000, -5, "x"]})
        self.assertTrue(c["ok"])
        self.assertEqual(len(c["cenarios"]), 2)
        self.assertEqual(c["cenarios"][0]["pct_necessario_para_quem_esta_atras_empatar"], 54.68)
        self.assertIsNone(c["cenarios"][1]["pct_necessario_para_quem_esta_atras_empatar"])
        texto = str(c).lower()
        self.assertNotIn("probabilidade de vit", texto)
        self.assertIn("Nenhuma probabilidade", c["avisos"][0])

    def test_relatorio_completo_classifica_tudo(self):
        r = m.relatorio_completo(snap(), None, [snap()], None, snap(), None)
        self.assertEqual({i["tipo"] for i in r["itens"]} <= {"fato", "calculo", "hipotese", "limitacao"}, True)
        self.assertTrue(r["por_tipo"]["fato"])
        self.assertTrue(r["por_tipo"]["limitacao"])
        self.assertEqual(r["tipo"], "Análise descritiva automática (sem IA)")

    def test_auditoria_detecta_numeros_inventados(self):
        s = snap()
        aud = m.auditar_texto("Lula lidera com 52,02% (1.204.715 votos), diferença de 93.522 votos ou 4,04 pp; 1,86% das seções.", {"atual": s}, [s])
        self.assertEqual(aud["veredito"], "compatível")
        self.assertEqual(aud["nao_suportados"], [])
        aud2 = m.auditar_texto("Lula tem 61% e vai chegar a 9 milhões de votos; 2026 foi atípico.", {"atual": s}, [s])
        self.assertEqual(aud2["veredito"], "sem suporte")
        citados = [x["citado"] for x in aud2["nao_suportados"]]
        self.assertIn("61 %", citados)
        self.assertTrue(any("milh" in c for c in citados))
        self.assertFalse(any("2026" in c for c in citados))


if __name__ == "__main__":
    unittest.main()
