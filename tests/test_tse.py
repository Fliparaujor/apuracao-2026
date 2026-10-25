import unittest
from datetime import datetime

from base import CasoBase
import tse_simulado
from radar import tse


class ParserTSE(CasoBase):
    def test_urls_oficiais(self):
        self.assertEqual(tse.url_resultado("br").split("/oficial")[-1] if "/oficial" in tse.url_resultado("br") else tse.url_resultado("br").split(tse.base_url())[-1],
                         "/ele2026/6258/dados/br/br-c0001-e006258-u.json")
        self.assertTrue(tse.url_resultado("ce13897").endswith("/6258/dados/ce/ce13897-c0001-e006258-u.json"))
        self.assertTrue(tse.url_resultado("am", "governador").endswith("/6260/dados/am/am-c0003-e006260-u.json"))
        self.assertTrue(tse.url_resultado("br", "presidente", 1).endswith("/6257/dados/br/br-c0001-e006257-u.json"))
        self.assertTrue(tse.url_config_eleicoes().endswith("/comum/config/ele-c.json"))

    def test_escopos_invalidos(self):
        for ruim in ("../", "https://x", "zz12345", "xx", "br00001", "", "CE 13897", "ce1389"):
            with self.assertRaises(ValueError):
                tse.validar_escopo(ruim)
        with self.assertRaises(ValueError):
            tse.url_resultado("br", "governador")
        with self.assertRaises(ValueError):
            tse.validar_cargo("senador")

    def test_numeros_formato_tse(self):
        self.assertEqual(tse.numero("1.234.567"), 1234567)
        self.assertEqual(tse.numero("49,20"), 49.2)
        self.assertEqual(tse.numero("0.21251963"), 0.21251963)
        self.assertEqual(tse.numero(1.5), 1.5)
        self.assertEqual(tse.numero(None), 0)
        self.assertEqual(tse.numero("abc"), 0)

    def test_normalizar_campos_reais(self):
        bruto = {
            "ele": "6258", "t": "2", "cdabr": "BR", "dg": "25/10/2026", "hg": "19:15:40", "dt": "25/10/2026", "ht": "19:15:33", "tf": "n",
            "s": {"ts": "499.248", "st": "9.299", "pst": "1,86", "pstn": 1.862601352},
            "e": {"te": "158.745.502", "est": "3.194.828", "c": "2.385.042", "a": "809.363", "pc": "74,65", "pa": "25,35"},
            "v": {"vv": "2.315.908", "vb": "24.046", "pvb": "1,01", "tvn": "45.088", "ptvn": "1,89"},
            "carg": [{"cd": "1", "agr": [
                {"par": [{"sg": "PT", "cand": [{"n": "13", "nmu": "LULA", "nm": "Luiz Inácio Lula da Silva", "vap": "1.204.715", "pvap": "52,02", "st": "", "sqcand": "280001"}]}]},
                {"par": [{"sg": "PL", "cand": [{"n": "22", "nmu": "FLAVIO BOLSONARO", "vap": "1.111.193", "pvap": "47,98", "pvapn": 47.9808}]}]},
            ]}],
        }
        s = tse.normalizar(bruto, "br", "presidente", 2, "fonte")
        self.assertEqual(s["horario_tse"], "25/10/2026 19:15:33")
        self.assertEqual(s["horario_geracao_tse"], "25/10/2026 19:15:40")
        self.assertEqual(s["secoes_pct"], 1.86)
        self.assertEqual(s["secoes_totalizadas"], 9299)
        self.assertEqual(s["votos_validos"], 2315908)
        self.assertEqual(s["candidatos"][0]["numero"], "13")
        self.assertEqual(s["candidatos"][0]["votos"], 1204715)
        self.assertEqual(s["candidatos"][1]["percentual"], 47.98)
        self.assertEqual(s["comparecimento"], 2385042)
        self.assertEqual(s["abstencao"], 809363)
        self.assertEqual(s["eleitorado_secoes_totalizadas"], 3194828)
        self.assertFalse(s["totalizacao_final"])
        self.assertEqual(s["status_oficial"], "Totalização parcial em andamento")

    def test_normalizar_rejeita_formato_errado(self):
        with self.assertRaises(tse.TSEIndisponivel):
            tse.normalizar({"x": 1}, "br")
        with self.assertRaises(tse.TSEIndisponivel):
            tse.normalizar({"carg": []}, "br")

    def test_obter_do_simulado_e_turno(self):
        s = tse.obter("ce")
        self.assertEqual(s["escopo"], "ce")
        self.assertEqual(s["nome_escopo"], "Ceará")
        self.assertGreater(s["votos_validos"], 0)
        primeiro = tse.obter("ce", "presidente", 1)
        self.assertTrue(primeiro["totalizacao_final"])
        self.assertEqual(len(primeiro["candidatos"]), 3)

    def test_sem_dados_404_e_indisponivel(self):
        with self.assertRaises(tse.TSEIndisponivel) as cm:
            tse.obter("sp", "governador")
        self.assertEqual(cm.exception.categoria, "sem_dados")
        tse_simulado.ESTADO.indisponivel = True
        tse.limpar_cache()
        try:
            with self.assertRaises(tse.TSEIndisponivel) as cm:
                tse.obter("rj")
            self.assertEqual(cm.exception.http, 503)
        finally:
            tse_simulado.ESTADO.indisponivel = False

    def test_atualidade_nunca_ao_vivo_para_historico(self):
        agora = datetime(2026, 10, 25, 19, 20, tzinfo=tse.BRASILIA)
        vivo = tse.classificar_atualidade({"horario_tse": "25/10/2026 19:15:33"}, agora)
        self.assertTrue(vivo["ao_vivo"])
        velho = tse.classificar_atualidade({"horario_tse": "25/10/2026 17:00:00"}, agora)
        self.assertFalse(velho["ao_vivo"])
        self.assertEqual(velho["estado"], "estavel")
        encerrada = tse.classificar_atualidade({"horario_tse": "25/10/2026 19:19:00", "totalizacao_final": True}, agora)
        self.assertFalse(encerrada["ao_vivo"])
        historico = tse.classificar_atualidade({"horario_tse": "04/10/2026 21:00:00"}, agora)
        self.assertEqual(historico["estado"], "historica")
        self.assertFalse(tse.classificar_atualidade({"horario_tse": ""}, agora)["ao_vivo"])

    def test_descoberta_codigos_e_governadores(self):
        r = tse.descobrir_eleicoes(forcar=True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["codigos"]["presidente.turno2"], 6258)
        self.assertEqual(r["codigos"]["governador.turno2"], 6260)
        self.assertEqual(r["divergencias"], [])
        g = tse.ufs_governador_2t(verificar=True)
        self.assertEqual(g["confirmadas"], ["ac", "am", "df", "es", "rn", "to"])
        self.assertTrue(any(x["uf"] == "rj" for x in g["sem_arquivo"]))

    def test_municipios(self):
        m = tse.municipios("ce")
        self.assertTrue(any(x["escopo"] == "ce13897" for x in m))


if __name__ == "__main__":
    unittest.main()
