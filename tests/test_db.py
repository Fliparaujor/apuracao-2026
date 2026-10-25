import sqlite3
import unittest
from pathlib import Path

from base import CasoBase
from radar import config, db, tse


class Banco(CasoBase):
    def snap(self, h="25/10/2026 19:15:33", vv=2315908, v13=1204715, v22=1111193):
        return {"escopo": "br", "cargo": "presidente", "turno": 2, "horario_tse": h, "secoes_totalizadas": 9299, "secoes_pct": 1.86,
                "votos_validos": vv, "candidatos": [{"numero": "13", "nome": "LULA", "votos": v13, "percentual": 52.02},
                                                    {"numero": "22", "nome": "FLAVIO BOLSONARO", "votos": v22, "percentual": 47.98}]}

    def test_dedupe_de_snapshots_identicos(self):
        self.assertTrue(db.gravar_snapshot(self.snap())["novo"])
        self.assertFalse(db.gravar_snapshot(self.snap())["novo"])
        self.assertFalse(db.gravar_snapshot(self.snap())["novo"])
        r = db.gravar_snapshot(self.snap("25/10/2026 19:16:00", 2400000, 1250000, 1150000))
        self.assertTrue(r["novo"])
        self.assertEqual(r["anterior"]["horario_tse"], "25/10/2026 19:15:33")
        self.assertEqual(len(db.historico("br")), 2)
        # mesmo horário, votos diferentes = boletim novo (o TSE pode regerar)
        self.assertTrue(db.gravar_snapshot(self.snap("25/10/2026 19:16:00", 2400001, 1250001, 1150000))["novo"])

    def test_boletim_vazio_nao_duplica(self):
        vazio = self.snap(vv=0, v13=0, v22=0) | {"secoes_totalizadas": 0, "escopo": "ap"}
        self.assertTrue(db.gravar_snapshot(vazio)["novo"])
        self.assertFalse(db.gravar_snapshot(vazio | {"horario_tse": "25/10/2026 16:59:00"})["novo"])

    def test_contadores_distinguem_repetido_de_novo(self):
        db.registrar_coleta("ce", "presidente", "novo")
        db.registrar_coleta("ce", "presidente", "repetido")
        db.registrar_coleta("ce", "presidente", "erro", "timeout")
        c = [x for x in db.contadores_coleta() if x["chave"] == "ce:presidente"][0]
        self.assertEqual((c["consultas"], c["boletins_novos"], c["repetidos"], c["erros"]), (3, 1, 1, 1))

    def test_migracao_de_esquema_antigo_e_legado(self):
        caminho = Path(self._tmp.name) / "antigo.sqlite3"
        con = sqlite3.connect(caminho)
        con.executescript("""CREATE TABLE esquema (versao INTEGER NOT NULL); INSERT INTO esquema VALUES (1);
            CREATE TABLE snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, escopo TEXT NOT NULL, cargo TEXT NOT NULL, turno INTEGER NOT NULL,
            horario_tse TEXT NOT NULL, consulta_utc TEXT NOT NULL, secoes_totalizadas INTEGER NOT NULL DEFAULT 0, secoes_pct REAL NOT NULL DEFAULT 0,
            votos_validos INTEGER NOT NULL DEFAULT 0, assinatura TEXT NOT NULL, dados TEXT NOT NULL, UNIQUE(escopo, cargo, turno, assinatura));
            CREATE TABLE conversas (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, escopo TEXT NOT NULL, pergunta TEXT NOT NULL,
            resposta TEXT NOT NULL, status TEXT NOT NULL, criado_utc TEXT NOT NULL);""")
        con.commit(); con.close()
        legado = config.RAIZ_PROJETO / "radar-history.sqlite3"
        criou = False
        if not legado.exists():
            criou = True
            lc = sqlite3.connect(legado)
            lc.executescript("""CREATE TABLE snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, source_time TEXT NOT NULL,
                received_utc TEXT NOT NULL, counted REAL NOT NULL, total_valid INTEGER NOT NULL, top_num TEXT NOT NULL, top_votes INTEGER NOT NULL, top_share REAL NOT NULL);
                INSERT INTO snapshots(scope,source_time,received_utc,counted,total_valid,top_num,top_votes,top_share) VALUES ('ce','25/10/2026 17:40:00','2026-10-25T20:40:00+00:00',10.5,1000,'13',600,60.0);""")
            lc.commit(); lc.close()
        try:
            info = db.inicializar(caminho)
            self.assertEqual(info["versao_anterior"], 1)
            self.assertEqual(info["versao"], db.VERSAO_ESQUEMA)
            self.assertEqual(info["legado_importado"], 1)
            self.assertEqual(db.inicializar(caminho)["legado_importado"], 0)
            h = db.historico("ce")
            self.assertEqual(len(h), 1)
            self.assertTrue(h[0]["_legado"])
            cols = {r[1] for r in db.conexao().execute("PRAGMA table_info(conversas)")}
            self.assertIn("sessao", cols)
        finally:
            if criou:
                legado.unlink()
            db.inicializar(Path(self._tmp.name) / "radar.sqlite3")

    def test_conversas_e_uso(self):
        i = db.gravar_conversa("analista", "br", "pergunta", {"a": 1}, "ok", "sessao1")
        db.atualizar_conversa(i, {"a": 2}, "ok")
        self.assertEqual(db.obter_conversa(i)["resposta"], {"a": 2})
        self.assertEqual(len(db.listar_conversas("analista", 10, "sessao1")), 1)
        self.assertEqual(db.listar_conversas("conselho"), [])
        db.registrar_uso("groq", "m", True, 200, 500, 100, 50, "teste", "")
        db.registrar_uso("groq", "m", False, 429, 50, 100, 0, "teste", "Bearer gsk_teste_abcdefghijklmnopq 429")
        uso = db.resumo_uso(24)[0]
        self.assertEqual((uso["chamadas"], uso["falhas"]), (2, 1))
        erro = db.conexao().execute("SELECT erro FROM uso_ia WHERE ok=0").fetchone()[0]
        self.assertNotIn("gsk_abc", erro)

    def test_verificar(self):
        self.assertTrue(db.verificar()["ok"])


if __name__ == "__main__":
    unittest.main()
