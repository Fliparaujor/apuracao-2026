import threading
import unittest

from base import CasoBase
from radar.cotas import Cotas, CotaExcedida, Cancelamento, Cancelado, estimar_tokens


class Cota(CasoBase):
    def novo(self):
        return Cotas({"x": {"rpm": 2, "rpd": 3, "tpm": 1000, "max_tokens_por_chamada": 800}})

    def test_rpm_rpd_tpm(self):
        q = self.novo()
        q.reservar("x", 100); q.reservar("x", 100)
        d = q.disponibilidade("x", 100)
        self.assertFalse(d["ok"]); self.assertIn("minuto", d["motivo"])
        with self.assertRaises(CotaExcedida):
            q.reservar("x", 100, espera_maxima=0.1)
        self.assertFalse(q.disponibilidade("x", 900)["ok"])
        q2 = self.novo()
        self.assertFalse(q2.disponibilidade("x", 801)["ok"])

    def test_cooldown_429_e_desativacao(self):
        q = self.novo()
        q.registrar("x", False, 429, retry_after=30)
        self.assertIn("pausa", q.disponibilidade("x", 1)["motivo"].lower())
        q.registrar("x", False, 429, retry_after=7200)
        self.assertIn("desativado", q.disponibilidade("x", 1)["motivo"].lower())
        q.reativar("x")
        self.assertTrue(q.disponibilidade("x", 1)["ok"])
        q.registrar("x", False, 401)
        self.assertIn("credencial", q.disponibilidade("x", 1)["motivo"])
        q.reativar("x")
        q.registrar("x", False, 402)
        self.assertIn("pagamento", q.disponibilidade("x", 1)["motivo"])

    def test_falhas_seguidas_pausam(self):
        q = self.novo()
        for _ in range(3):
            q.registrar("x", False, 500)
        self.assertIn("pausa", q.disponibilidade("x", 1)["motivo"].lower())
        q.registrar("x", True)
        self.assertEqual(q.estado()["provedores"]["x"]["falhas_seguidas"], 0)

    def test_limite_sessao(self):
        q = Cotas({"x": {"rpm": 1000, "rpd": 1000, "tpm": 100000, "max_tokens_por_chamada": 8000}})
        q.limite_sessao = lambda: 2
        q.reservar("x", 1); q.reservar("x", 1)
        self.assertIn("sessão", q.disponibilidade("x", 1)["motivo"])
        q.reiniciar_sessao()
        self.assertTrue(q.disponibilidade("x", 1)["ok"])

    def test_cancelamento_e_fila(self):
        q = self.novo()
        q.reservar("x", 1); q.reservar("x", 1)
        c = Cancelamento()
        threading.Timer(0.2, c.cancelar).start()
        with self.assertRaises(Cancelado):
            q.reservar("x", 1, cancelamento=c, espera_maxima=70)
        q.adquirir_vaga(); q.adquirir_vaga(); q.adquirir_vaga()
        c2 = Cancelamento(); c2.cancelar()
        with self.assertRaises(Cancelado):
            q.adquirir_vaga(cancelamento=c2)
        q.liberar_vaga(); q.liberar_vaga(); q.liberar_vaga(); q.liberar_vaga()

    def test_estimativa(self):
        self.assertGreater(estimar_tokens("a" * 330), 90)


if __name__ == "__main__":
    unittest.main()
