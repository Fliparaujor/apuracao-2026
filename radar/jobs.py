"""Trabalhos assíncronos (reuniões do Conselho) com progresso e cancelamento."""
from __future__ import annotations

import threading
import time
import uuid

from .cotas import Cancelamento

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
MAX_JOBS = 40


def criar(tipo: str, alvo, *args, **kwargs) -> str:
    ident = uuid.uuid4().hex[:12]
    canc = Cancelamento()
    job = {"id": ident, "tipo": tipo, "status": "em_andamento", "progresso": [], "resultado": None,
           "erro": None, "inicio": time.time(), "fim": None, "_cancelamento": canc, "parcial": {}}
    with _lock:
        _jobs[ident] = job
        if len(_jobs) > MAX_JOBS:
            for antigo in sorted(_jobs.values(), key=lambda j: j["inicio"])[: len(_jobs) - MAX_JOBS]:
                if antigo["status"] != "em_andamento":
                    _jobs.pop(antigo["id"], None)

    def correr():
        try:
            resultado = alvo(job, canc, *args, **kwargs)
            job["resultado"] = resultado
            job["status"] = "cancelado" if canc.cancelado else "concluido"
        except Exception as exc:  # noqa: BLE001 — reportamos ao cliente sem rastros internos
            from . import config
            job["erro"] = config.mascarar(str(exc))[:300]
            job["status"] = "cancelado" if canc.cancelado else "falha"
        finally:
            job["fim"] = time.time()

    threading.Thread(target=correr, name=f"job-{tipo}-{ident}", daemon=True).start()
    return ident


def progresso(job: dict, mensagem: str, **extra) -> None:
    job["progresso"].append({"t": time.time(), "mensagem": mensagem, **extra})
    job["progresso"] = job["progresso"][-60:]


def obter(ident: str) -> dict | None:
    with _lock:
        job = _jobs.get(ident)
    if not job:
        return None
    return {k: v for k, v in job.items() if not k.startswith("_")}


def cancelar(ident: str) -> bool:
    with _lock:
        job = _jobs.get(ident)
    if not job or job["status"] != "em_andamento":
        return False
    job["_cancelamento"].cancelar()
    return True


def em_andamento(tipo: str | None = None) -> list[dict]:
    with _lock:
        return [{k: v for k, v in j.items() if not k.startswith("_")} for j in _jobs.values()
                if j["status"] == "em_andamento" and (tipo is None or j["tipo"] == tipo)]
