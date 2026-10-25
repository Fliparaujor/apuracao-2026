"""Coleta em segundo plano: consulta o TSE a cada 30 s e guarda apenas boletins novos.

Distingue consulta repetida (TSE respondeu o mesmo boletim) de boletim novo.
Recua quando o TSE falha repetidamente e nunca derruba o servidor.
"""
from __future__ import annotations

import threading
import time

from . import config, db, tse

_lock = threading.Lock()
_estado = {
    "ativo": False, "ultimo_ciclo_utc": None, "ultimo_boletim_novo_utc": None, "ciclos": 0,
    "consultas": 0, "boletins_novos": 0, "repetidos": 0, "erros": 0, "erros_seguidos": 0,
    "ultimo_erro": "", "escopos": {}, "governador_ufs": list(tse.GOVERNADOR_2T_PADRAO),
    "governador_verificado": False, "pausado_ate": 0.0,
}
_parar = threading.Event()
_thread: threading.Thread | None = None
_atual: dict[str, dict] = {}  # chave "escopo:cargo" -> último snapshot (memória)


def chave(escopo: str, cargo: str) -> str:
    return f"{escopo}:{cargo}"


def coletar_um(escopo: str, cargo: str = "presidente") -> dict:
    """Coleta um escopo agora. Retorna {'ok','novo','snapshot'|'erro'}."""
    try:
        snap = tse.obter(escopo, cargo, 2)
    except tse.TSEIndisponivel as exc:
        db.registrar_coleta(escopo, cargo, "erro", str(exc))
        with _lock:
            _estado["consultas"] += 1
            _estado["erros"] += 1
            _estado["escopos"][chave(escopo, cargo)] = {"ok": False, "erro": str(exc), "http": exc.http, "categoria": exc.categoria,
                                                        "quando_utc": db.agora_utc()}
        return {"ok": False, "erro": str(exc), "categoria": exc.categoria, "http": exc.http}
    r = db.gravar_snapshot(snap)
    db.registrar_coleta(escopo, cargo, "novo" if r["novo"] else "repetido")
    with _lock:
        _estado["consultas"] += 1
        if r["novo"]:
            _estado["boletins_novos"] += 1
            _estado["ultimo_boletim_novo_utc"] = db.agora_utc()
        else:
            _estado["repetidos"] += 1
        _estado["escopos"][chave(escopo, cargo)] = {"ok": True, "novo": r["novo"], "horario_tse": snap["horario_tse"],
                                                    "quando_utc": db.agora_utc()}
        _atual[chave(escopo, cargo)] = snap
    return {"ok": True, "novo": r["novo"], "snapshot": snap}


def atual(escopo: str, cargo: str = "presidente", max_idade_s: float = 120) -> dict | None:
    """Último snapshot em memória se recente; senão o do banco."""
    with _lock:
        snap = _atual.get(chave(escopo, cargo))
    if snap:
        return snap
    return db.ultimo_snapshot(escopo, cargo, 2)


def _ciclo(contador: int) -> None:
    cfg = config.carregar_config()
    prioritarios = list(cfg.get("escopos_prioritarios") or ["br"])
    alvos = [(e, "presidente") for e in prioritarios]
    with _lock:
        govs = list(_estado["governador_ufs"])
    alvos += [(uf, "governador") for uf in govs]
    # Estados: a cada N ciclos (padrão 60 s) e revezados em dois grupos para suavizar a carga.
    passo = max(1, int(cfg.get("intervalo_estados_segundos", 60) // max(1, cfg.get("intervalo_coleta_segundos", 30))))
    if contador % passo == 0:
        alvos += [(uf, "presidente") for uf in tse.UFS if uf not in prioritarios]
    erros, ok = 0, 0
    for escopo, cargo in alvos:
        if _parar.is_set():
            return
        r = coletar_um(escopo, cargo)
        if r["ok"]:
            ok += 1
        elif r.get("categoria") in ("rede", "http", "recusado"):
            erros += 1
    with _lock:
        _estado["ciclos"] += 1
        _estado["ultimo_ciclo_utc"] = db.agora_utc()
        if ok == 0 and erros > 0:
            _estado["erros_seguidos"] += 1
            _estado["ultimo_erro"] = "TSE inacessível em todo o ciclo"
            if _estado["erros_seguidos"] >= 3:
                _estado["pausado_ate"] = time.monotonic() + min(300, 30 * _estado["erros_seguidos"])
        else:
            _estado["erros_seguidos"] = 0


def _verificar_governadores() -> None:
    try:
        r = tse.ufs_governador_2t(verificar=True)
    except Exception:  # noqa: BLE001
        return
    with _lock:
        if r["confirmadas"]:
            _estado["governador_ufs"] = r["confirmadas"]
        _estado["governador_verificado"] = True
        _estado["governador_sem_arquivo"] = r["sem_arquivo"]


def _loop() -> None:
    contador = 0
    _verificar_governadores()
    while not _parar.is_set():
        cfg = config.carregar_config()
        intervalo = max(15, int(cfg.get("intervalo_coleta_segundos", 30)))
        with _lock:
            pausado = _estado["pausado_ate"] > time.monotonic()
        if not pausado:
            try:
                _ciclo(contador)
            except Exception as exc:  # noqa: BLE001 — a coleta nunca derruba o servidor
                with _lock:
                    _estado["ultimo_erro"] = config.mascarar(str(exc))[:160]
        contador += 1
        if contador % 120 == 0:
            _verificar_governadores()
        _parar.wait(intervalo)
    with _lock:
        _estado["ativo"] = False


def iniciar() -> bool:
    global _thread
    if not config.carregar_config().get("coleta_automatica", True):
        return False
    if _thread and _thread.is_alive():
        return True
    _parar.clear()
    with _lock:
        _estado["ativo"] = True
    _thread = threading.Thread(target=_loop, name="coletor-tse", daemon=True)
    _thread.start()
    return True


def parar(timeout: float = 5.0) -> None:
    _parar.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout)


def estado() -> dict:
    with _lock:
        e = dict(_estado)
        e["escopos"] = dict(_estado["escopos"])
        e["pausado_s"] = max(0, int(_estado["pausado_ate"] - time.monotonic()))
    e.pop("pausado_ate", None)
    e["thread_viva"] = bool(_thread and _thread.is_alive())
    return e


def governador_ufs() -> list[str]:
    with _lock:
        return list(_estado["governador_ufs"])
