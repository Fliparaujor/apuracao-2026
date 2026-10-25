"""Camada 2 — persistência local em SQLite.

Guarda snapshots oficiais (sem duplicar boletins idênticos), referências do 1º
turno, conversas com o Analista e reuniões do Conselho, consumo de IA e o
estado dos provedores. Esquema versionado com migração automática, inclusive do
banco legado `radar-history.sqlite3` do projeto anterior.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

VERSAO_ESQUEMA = 3
_lock = threading.RLock()
_caminho_atual: Path | None = None

ESQUEMA = [
    """CREATE TABLE IF NOT EXISTS esquema (versao INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        escopo TEXT NOT NULL, cargo TEXT NOT NULL, turno INTEGER NOT NULL,
        horario_tse TEXT NOT NULL, consulta_utc TEXT NOT NULL,
        secoes_totalizadas INTEGER NOT NULL DEFAULT 0, secoes_pct REAL NOT NULL DEFAULT 0,
        votos_validos INTEGER NOT NULL DEFAULT 0, assinatura TEXT NOT NULL,
        legado INTEGER NOT NULL DEFAULT 0, dados TEXT NOT NULL,
        UNIQUE(escopo, cargo, turno, assinatura))""",
    """CREATE INDEX IF NOT EXISTS idx_snapshots_escopo ON snapshots(escopo, cargo, turno, id)""",
    """CREATE TABLE IF NOT EXISTS coleta_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, quando_utc TEXT NOT NULL,
        escopo TEXT NOT NULL, cargo TEXT NOT NULL, resultado TEXT NOT NULL, detalhe TEXT)""",
    """CREATE TABLE IF NOT EXISTS coleta_contadores (
        chave TEXT PRIMARY KEY, consultas INTEGER NOT NULL DEFAULT 0,
        boletins_novos INTEGER NOT NULL DEFAULT 0, repetidos INTEGER NOT NULL DEFAULT 0,
        erros INTEGER NOT NULL DEFAULT 0, ultima_consulta_utc TEXT, ultimo_boletim_utc TEXT,
        ultimo_erro TEXT)""",
    """CREATE TABLE IF NOT EXISTS referencias (
        chave TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado_utc TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS conversas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, escopo TEXT NOT NULL,
        pergunta TEXT NOT NULL, resposta TEXT NOT NULL, status TEXT NOT NULL,
        criado_utc TEXT NOT NULL, sessao TEXT)""",
    """CREATE TABLE IF NOT EXISTS uso_ia (
        id INTEGER PRIMARY KEY AUTOINCREMENT, quando_utc TEXT NOT NULL, provedor TEXT NOT NULL,
        modelo TEXT, http INTEGER, ok INTEGER NOT NULL, duracao_ms INTEGER,
        tokens_entrada INTEGER, tokens_saida INTEGER, contexto TEXT, erro TEXT)""",
    """CREATE TABLE IF NOT EXISTS estado_provedor (
        provedor TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado_utc TEXT NOT NULL)""",
]


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conectar(caminho: Path | None = None) -> sqlite3.Connection:
    caminho = caminho or config.caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(caminho), timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def inicializar(caminho: Path | None = None) -> dict:
    """Cria/migra o esquema. Idempotente. Retorna informações da migração."""
    global _caminho_atual
    with _lock:
        caminho = caminho or config.caminho_banco()
        _caminho_atual = caminho
        con = _conectar(caminho)
        try:
            for sql in ESQUEMA:
                con.execute(sql)
            linha = con.execute("SELECT versao FROM esquema LIMIT 1").fetchone()
            anterior = linha["versao"] if linha else 0
            if linha is None:
                con.execute("INSERT INTO esquema(versao) VALUES (?)", (VERSAO_ESQUEMA,))
            elif anterior < VERSAO_ESQUEMA:
                _migrar(con, anterior)
                con.execute("UPDATE esquema SET versao=?", (VERSAO_ESQUEMA,))
            con.commit()
            importados = importar_legado(con)
            return {"caminho": str(caminho), "versao": VERSAO_ESQUEMA, "versao_anterior": anterior,
                    "legado_importado": importados}
        finally:
            con.close()


def _migrar(con: sqlite3.Connection, anterior: int) -> None:
    colunas = {r["name"] for r in con.execute("PRAGMA table_info(snapshots)")}
    if "legado" not in colunas:
        con.execute("ALTER TABLE snapshots ADD COLUMN legado INTEGER NOT NULL DEFAULT 0")
    colunas = {r["name"] for r in con.execute("PRAGMA table_info(conversas)")}
    if "sessao" not in colunas:
        con.execute("ALTER TABLE conversas ADD COLUMN sessao TEXT")


def importar_legado(con: sqlite3.Connection) -> int:
    """Importa o banco antigo `radar-history.sqlite3` (projeto anterior) uma única vez."""
    antigo = config.RAIZ_PROJETO / "radar-history.sqlite3"
    if not antigo.exists():
        return 0
    marca = con.execute("SELECT 1 FROM referencias WHERE chave='legado_importado'").fetchone()
    if marca:
        return 0
    importados = 0
    try:
        velho = sqlite3.connect(str(antigo), timeout=5)
        velho.row_factory = sqlite3.Row
        existe = velho.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snapshots'").fetchone()
        if existe:
            for r in velho.execute("SELECT * FROM snapshots ORDER BY id"):
                dados = {
                    "escopo": r["scope"], "cargo": "presidente", "turno": 2,
                    "horario_tse": r["source_time"], "consulta_utc": r["received_utc"],
                    "secoes_pct": float(r["counted"] or 0), "votos_validos": int(r["total_valid"] or 0),
                    "secoes_totalizadas": 0,
                    "candidatos": [{"numero": r["top_num"], "votos": int(r["top_votes"] or 0),
                                    "percentual": float(r["top_share"] or 0), "nome": "", "partido": ""}],
                    "legado": True,
                    "observacao": "Importado do banco anterior; contém apenas o líder e totais.",
                }
                if gravar_snapshot(dados, con=con, legado=True)["novo"]:
                    importados += 1
        velho.close()
    except sqlite3.DatabaseError:
        pass
    con.execute("INSERT OR REPLACE INTO referencias(chave,dados,atualizado_utc) VALUES ('legado_importado',?,?)",
                (json.dumps({"importados": importados}), agora_utc()))
    con.commit()
    return importados


def conexao() -> sqlite3.Connection:
    return _conectar(_caminho_atual)


# ----------------------------------------------------------------- snapshots

def assinatura_snapshot(snap: dict) -> str:
    """Identidade de um boletim: horário TSE + seções + válidos + votos por candidato."""
    base = {
        "h": snap.get("horario_tse"), "s": snap.get("secoes_totalizadas"), "p": snap.get("secoes_pct"),
        "v": snap.get("votos_validos"),
        "c": sorted((str(c.get("numero")), int(c.get("votos") or 0)) for c in snap.get("candidatos") or []),
        "tf": bool(snap.get("totalizacao_final")),
    }
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]


def gravar_snapshot(snap: dict, con: sqlite3.Connection | None = None, legado: bool = False) -> dict:
    """Grava um snapshot se for um boletim novo. Retorna {'novo': bool, 'id': int, 'anterior': dict|None}."""
    proprio = con is None
    con = con or conexao()
    try:
        with _lock:
            escopo, cargo, turno = snap["escopo"], snap.get("cargo", "presidente"), int(snap.get("turno", 2))
            assinatura = assinatura_snapshot(snap)
            anterior = con.execute(
                "SELECT id, assinatura, dados FROM snapshots WHERE escopo=? AND cargo=? AND turno=? ORDER BY id DESC LIMIT 1",
                (escopo, cargo, turno)).fetchone()
            if anterior and anterior["assinatura"] == assinatura:
                return {"novo": False, "id": anterior["id"], "anterior": None}
            if not (snap.get("votos_validos") or snap.get("secoes_totalizadas")) and not legado:
                # Boletim vazio (antes da totalização) só é guardado uma vez.
                if anterior and json.loads(anterior["dados"]).get("votos_validos", 0) == 0:
                    return {"novo": False, "id": anterior["id"], "anterior": None}
            cur = con.execute(
                """INSERT OR IGNORE INTO snapshots(escopo,cargo,turno,horario_tse,consulta_utc,secoes_totalizadas,
                   secoes_pct,votos_validos,assinatura,legado,dados) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (escopo, cargo, turno, snap.get("horario_tse", ""), snap.get("consulta_utc") or agora_utc(),
                 int(snap.get("secoes_totalizadas") or 0), float(snap.get("secoes_pct") or 0),
                 int(snap.get("votos_validos") or 0), assinatura, 1 if legado else 0,
                 json.dumps(snap, ensure_ascii=False)))
            if cur.rowcount == 0:
                return {"novo": False, "id": anterior["id"] if anterior else None, "anterior": None}
            # Conserva até 600 boletins por escopo.
            con.execute("""DELETE FROM snapshots WHERE escopo=? AND cargo=? AND turno=? AND id NOT IN
                           (SELECT id FROM snapshots WHERE escopo=? AND cargo=? AND turno=? ORDER BY id DESC LIMIT 600)""",
                        (escopo, cargo, turno, escopo, cargo, turno))
            con.commit()
            return {"novo": True, "id": cur.lastrowid,
                    "anterior": json.loads(anterior["dados"]) if anterior else None}
    finally:
        if proprio:
            con.close()


def ultimo_snapshot(escopo: str, cargo: str = "presidente", turno: int = 2) -> dict | None:
    con = conexao()
    try:
        r = con.execute("SELECT dados FROM snapshots WHERE escopo=? AND cargo=? AND turno=? ORDER BY id DESC LIMIT 1",
                        (escopo, cargo, turno)).fetchone()
        return json.loads(r["dados"]) if r else None
    finally:
        con.close()


def historico(escopo: str, cargo: str = "presidente", turno: int = 2, limite: int = 300) -> list[dict]:
    con = conexao()
    try:
        linhas = con.execute(
            "SELECT id, dados, legado FROM snapshots WHERE escopo=? AND cargo=? AND turno=? ORDER BY id DESC LIMIT ?",
            (escopo, cargo, turno, int(limite))).fetchall()
        saida = []
        for r in reversed(linhas):
            d = json.loads(r["dados"])
            d["_id"] = r["id"]
            d["_legado"] = bool(r["legado"])
            saida.append(d)
        return saida
    finally:
        con.close()


def ultimos_por_escopo(cargo: str = "presidente", turno: int = 2) -> dict[str, dict]:
    con = conexao()
    try:
        linhas = con.execute(
            """SELECT s.escopo, s.dados FROM snapshots s JOIN (
                 SELECT escopo, MAX(id) AS mid FROM snapshots WHERE cargo=? AND turno=? GROUP BY escopo) m
               ON s.id=m.mid""", (cargo, turno)).fetchall()
        return {r["escopo"]: json.loads(r["dados"]) for r in linhas}
    finally:
        con.close()


def contar_snapshots() -> dict:
    con = conexao()
    try:
        total = con.execute("SELECT COUNT(*) AS n FROM snapshots").fetchone()["n"]
        por = con.execute("SELECT escopo, cargo, COUNT(*) AS n, MAX(horario_tse) AS h FROM snapshots GROUP BY escopo, cargo").fetchall()
        return {"total": total, "por_escopo": [{"escopo": r["escopo"], "cargo": r["cargo"], "n": r["n"], "ultimo": r["h"]} for r in por]}
    finally:
        con.close()


# -------------------------------------------------------------- coleta / log

def registrar_coleta(escopo: str, cargo: str, resultado: str, detalhe: str = "") -> None:
    """resultado: 'novo' | 'repetido' | 'erro'. Distingue consulta repetida de boletim novo."""
    con = conexao()
    try:
        with _lock:
            chave = f"{escopo}:{cargo}"
            agora = agora_utc()
            con.execute("INSERT OR IGNORE INTO coleta_contadores(chave) VALUES (?)", (chave,))
            if resultado == "novo":
                con.execute("UPDATE coleta_contadores SET consultas=consultas+1, boletins_novos=boletins_novos+1, ultima_consulta_utc=?, ultimo_boletim_utc=? WHERE chave=?", (agora, agora, chave))
            elif resultado == "repetido":
                con.execute("UPDATE coleta_contadores SET consultas=consultas+1, repetidos=repetidos+1, ultima_consulta_utc=? WHERE chave=?", (agora, chave))
            else:
                con.execute("UPDATE coleta_contadores SET consultas=consultas+1, erros=erros+1, ultima_consulta_utc=?, ultimo_erro=? WHERE chave=?", (agora, detalhe[:200], chave))
            con.execute("INSERT INTO coleta_log(quando_utc,escopo,cargo,resultado,detalhe) VALUES (?,?,?,?,?)",
                        (agora, escopo, cargo, resultado, detalhe[:200]))
            con.execute("DELETE FROM coleta_log WHERE id NOT IN (SELECT id FROM coleta_log ORDER BY id DESC LIMIT 500)")
            con.commit()
    finally:
        con.close()


def contadores_coleta() -> list[dict]:
    con = conexao()
    try:
        return [dict(r) for r in con.execute("SELECT * FROM coleta_contadores ORDER BY chave")]
    finally:
        con.close()


# -------------------------------------------------------------- referências

def gravar_referencia(chave: str, dados) -> None:
    con = conexao()
    try:
        with _lock:
            con.execute("INSERT OR REPLACE INTO referencias(chave,dados,atualizado_utc) VALUES (?,?,?)",
                        (chave, json.dumps(dados, ensure_ascii=False), agora_utc()))
            con.commit()
    finally:
        con.close()


def ler_referencia(chave: str):
    con = conexao()
    try:
        r = con.execute("SELECT dados, atualizado_utc FROM referencias WHERE chave=?", (chave,)).fetchone()
        if not r:
            return None
        return {"dados": json.loads(r["dados"]), "atualizado_utc": r["atualizado_utc"]}
    finally:
        con.close()


# ---------------------------------------------------------------- conversas

def gravar_conversa(tipo: str, escopo: str, pergunta: str, resposta: dict, status: str, sessao: str = "") -> int:
    con = conexao()
    try:
        with _lock:
            cur = con.execute(
                "INSERT INTO conversas(tipo,escopo,pergunta,resposta,status,criado_utc,sessao) VALUES (?,?,?,?,?,?,?)",
                (tipo, escopo, pergunta[:2000], json.dumps(resposta, ensure_ascii=False), status, agora_utc(), sessao[:64]))
            con.execute("DELETE FROM conversas WHERE id NOT IN (SELECT id FROM conversas ORDER BY id DESC LIMIT 400)")
            con.commit()
            return cur.lastrowid
    finally:
        con.close()


def atualizar_conversa(ident: int, resposta: dict, status: str) -> None:
    con = conexao()
    try:
        with _lock:
            con.execute("UPDATE conversas SET resposta=?, status=? WHERE id=?",
                        (json.dumps(resposta, ensure_ascii=False), status, ident))
            con.commit()
    finally:
        con.close()


def listar_conversas(tipo: str | None = None, limite: int = 30, sessao: str | None = None) -> list[dict]:
    con = conexao()
    try:
        sql = "SELECT id,tipo,escopo,pergunta,resposta,status,criado_utc,sessao FROM conversas"
        cond, args = [], []
        if tipo:
            cond.append("tipo=?"); args.append(tipo)
        if sessao:
            cond.append("sessao=?"); args.append(sessao)
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(int(limite))
        saida = []
        for r in con.execute(sql, args):
            d = dict(r)
            try:
                d["resposta"] = json.loads(d["resposta"])
            except ValueError:
                d["resposta"] = {}
            saida.append(d)
        return saida
    finally:
        con.close()


def obter_conversa(ident: int) -> dict | None:
    con = conexao()
    try:
        r = con.execute("SELECT id,tipo,escopo,pergunta,resposta,status,criado_utc,sessao FROM conversas WHERE id=?", (ident,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["resposta"] = json.loads(d["resposta"])
        return d
    finally:
        con.close()


# ------------------------------------------------------------------ uso IA

def registrar_uso(provedor: str, modelo: str, ok: bool, http: int | None, duracao_ms: int,
                  tokens_entrada: int, tokens_saida: int, contexto: str, erro: str = "") -> None:
    con = conexao()
    try:
        with _lock:
            con.execute(
                """INSERT INTO uso_ia(quando_utc,provedor,modelo,http,ok,duracao_ms,tokens_entrada,tokens_saida,contexto,erro)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (agora_utc(), provedor, modelo, http, 1 if ok else 0, duracao_ms, tokens_entrada, tokens_saida,
                 contexto[:60], config.mascarar(erro)[:200]))
            con.execute("DELETE FROM uso_ia WHERE id NOT IN (SELECT id FROM uso_ia ORDER BY id DESC LIMIT 5000)")
            con.commit()
    finally:
        con.close()


def resumo_uso(horas: int = 24) -> list[dict]:
    con = conexao()
    try:
        limite = datetime.now(timezone.utc).timestamp() - horas * 3600
        linhas = con.execute("SELECT * FROM uso_ia ORDER BY id DESC LIMIT 5000").fetchall()
        agregado: dict[str, dict] = {}
        for r in linhas:
            try:
                ts = datetime.fromisoformat(r["quando_utc"]).timestamp()
            except ValueError:
                continue
            if ts < limite:
                continue
            a = agregado.setdefault(r["provedor"], {"provedor": r["provedor"], "chamadas": 0, "falhas": 0,
                                                     "tokens_entrada": 0, "tokens_saida": 0, "ultima": None})
            a["chamadas"] += 1
            a["falhas"] += 0 if r["ok"] else 1
            a["tokens_entrada"] += r["tokens_entrada"] or 0
            a["tokens_saida"] += r["tokens_saida"] or 0
            a["ultima"] = a["ultima"] or r["quando_utc"]
        return sorted(agregado.values(), key=lambda x: x["provedor"])
    finally:
        con.close()


# ------------------------------------------------------- estado dos provedores

def gravar_estado_provedor(provedor: str, dados: dict) -> None:
    con = conexao()
    try:
        with _lock:
            con.execute("INSERT OR REPLACE INTO estado_provedor(provedor,dados,atualizado_utc) VALUES (?,?,?)",
                        (provedor, json.dumps(dados, ensure_ascii=False), agora_utc()))
            con.commit()
    finally:
        con.close()


def ler_estado_provedor(provedor: str) -> dict | None:
    con = conexao()
    try:
        r = con.execute("SELECT dados FROM estado_provedor WHERE provedor=?", (provedor,)).fetchone()
        return json.loads(r["dados"]) if r else None
    finally:
        con.close()


def verificar() -> dict:
    """Teste rápido de leitura/escrita usado pelo diagnóstico."""
    try:
        con = conexao()
        try:
            con.execute("CREATE TABLE IF NOT EXISTS _ping (t TEXT)")
            con.execute("DELETE FROM _ping")
            con.execute("INSERT INTO _ping VALUES (?)", (agora_utc(),))
            con.commit()
            n = con.execute("SELECT COUNT(*) AS n FROM snapshots").fetchone()["n"]
            return {"ok": True, "snapshots": n, "caminho": str(_caminho_atual or config.caminho_banco())}
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return {"ok": False, "erro": str(exc)[:160]}
