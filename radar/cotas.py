"""Camada 9 — controle de cotas gratuitas.

Rate limiting por provedor (minuto/dia/tokens), cooldown após HTTP 429,
desativação automática após erros persistentes, limites por sessão, fila com
concorrência limitada e cancelamento. Nenhuma função aqui habilita cobrança.
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from datetime import datetime, timezone

from . import config

LIMITES_PADRAO = {
    # Valores conservadores; o provedor pode ser mais generoso. HTTP 429 ajusta na prática.
    "groq":        {"rpm": 25, "rpd": 900, "tpm": 7000, "max_tokens_por_chamada": 6000},
    "gemini":      {"rpm": 5, "rpd": 150, "tpm": 60000, "max_tokens_por_chamada": 20000},
    "mistral":     {"rpm": 20, "rpd": 500, "tpm": 200000, "max_tokens_por_chamada": 20000},
    "openrouter":  {"rpm": 10, "rpd": 45, "tpm": 60000, "max_tokens_por_chamada": 20000},
    "cohere":      {"rpm": 15, "rpd": 40, "tpm": 60000, "max_tokens_por_chamada": 20000},
    "cloudflare":  {"rpm": 20, "rpd": 120, "tpm": 60000, "max_tokens_por_chamada": 12000},
    "huggingface": {"rpm": 8, "rpd": 25, "tpm": 40000, "max_tokens_por_chamada": 12000},
}
FALHAS_PARA_DESATIVAR = 3
CONCORRENCIA_GLOBAL = 3


class CotaExcedida(RuntimeError):
    def __init__(self, mensagem: str, espera: float = 0.0):
        super().__init__(mensagem)
        self.espera = espera


class Cancelado(RuntimeError):
    pass


class Cancelamento:
    def __init__(self):
        self._ev = threading.Event()

    def cancelar(self):
        self._ev.set()

    @property
    def cancelado(self) -> bool:
        return self._ev.is_set()

    def verificar(self):
        if self._ev.is_set():
            raise Cancelado("Operação cancelada pelo usuário.")


def estimar_tokens(texto: str) -> int:
    return max(1, int(len(texto or "") / 3.3))


class _Estado:
    def __init__(self, limites: dict):
        self.limites = dict(limites)
        self.minuto: deque[float] = deque()
        self.tokens_minuto: deque[tuple[float, int]] = deque()
        self.dia = 0
        self.dia_ref = datetime.now(timezone.utc).date()
        self.cooldown_ate = 0.0
        self.motivo_cooldown = ""
        self.falhas_seguidas = 0
        self.desativado = ""
        self.ultimo_erro = ""
        self.chamadas_ok = 0
        self.chamadas_erro = 0


class Cotas:
    def __init__(self, limites: dict | None = None):
        self._lock = threading.RLock()
        self._estados: dict[str, _Estado] = {}
        self._limites = limites or LIMITES_PADRAO
        self._sessao_chamadas = 0
        self._semaforo = threading.BoundedSemaphore(CONCORRENCIA_GLOBAL)

    def _estado(self, provedor: str) -> _Estado:
        if provedor not in self._estados:
            limites = dict(self._limites.get(provedor, {"rpm": 10, "rpd": 100, "tpm": 30000, "max_tokens_por_chamada": 8000}))
            try:
                personalizados = config.carregar_config().get("limites_cotas", {}).get(provedor) or {}
                limites.update({k: int(v) for k, v in personalizados.items() if k in limites and int(v) > 0})
            except (TypeError, ValueError, AttributeError):
                pass
            self._estados[provedor] = _Estado(limites)
        return self._estados[provedor]

    def _rolar(self, e: _Estado, agora: float):
        while e.minuto and agora - e.minuto[0] > 60:
            e.minuto.popleft()
        while e.tokens_minuto and agora - e.tokens_minuto[0][0] > 60:
            e.tokens_minuto.popleft()
        hoje = datetime.now(timezone.utc).date()
        if hoje != e.dia_ref:
            e.dia, e.dia_ref = 0, hoje
            if e.desativado.startswith("cota diária"):
                e.desativado = ""

    def limite_sessao(self) -> int:
        try:
            return int(config.carregar_config()["limites_sessao"]["chamadas_ia_por_sessao"])
        except (KeyError, TypeError, ValueError):
            return 120

    def disponibilidade(self, provedor: str, tokens: int = 0) -> dict:
        """Verifica, sem reservar, se uma chamada caberia agora."""
        with self._lock:
            e = self._estado(provedor)
            agora = time.monotonic()
            self._rolar(e, agora)
            if e.desativado:
                return {"ok": False, "motivo": "Provedor desativado automaticamente: " + e.desativado, "espera": None}
            if agora < e.cooldown_ate:
                return {"ok": False, "motivo": f"Em pausa ({e.motivo_cooldown}); aguarde {int(e.cooldown_ate - agora)} s.", "espera": e.cooldown_ate - agora}
            if self._sessao_chamadas >= self.limite_sessao():
                return {"ok": False, "motivo": "Limite de chamadas de IA desta sessão atingido (ajuste em Sistema).", "espera": None}
            if e.dia >= e.limites["rpd"]:
                return {"ok": False, "motivo": "Cota diária estimada atingida para este provedor.", "espera": None}
            if len(e.minuto) >= e.limites["rpm"]:
                return {"ok": False, "motivo": "Limite de requisições por minuto.", "espera": 60 - (agora - e.minuto[0]) + 0.5}
            usados = sum(t for _, t in e.tokens_minuto)
            if tokens and usados + tokens > e.limites["tpm"]:
                espera = 60 - (agora - e.tokens_minuto[0][0]) + 0.5 if e.tokens_minuto else 5
                return {"ok": False, "motivo": "Limite de tokens por minuto.", "espera": espera}
            if tokens and tokens > e.limites.get("max_tokens_por_chamada", 8000):
                return {"ok": False, "motivo": "Pedido grande demais para a cota gratuita; reduza o contexto.", "espera": None}
            return {"ok": True, "motivo": "", "espera": 0}

    def reservar(self, provedor: str, tokens: int, cancelamento: Cancelamento | None = None, espera_maxima: float = 75.0) -> None:
        """Bloqueia até caber na janela (ou lança CotaExcedida/Cancelado)."""
        inicio = time.monotonic()
        while True:
            if cancelamento:
                cancelamento.verificar()
            d = self.disponibilidade(provedor, tokens)
            if d["ok"]:
                with self._lock:
                    e = self._estado(provedor)
                    agora = time.monotonic()
                    e.minuto.append(agora)
                    e.tokens_minuto.append((agora, tokens))
                    e.dia += 1
                    self._sessao_chamadas += 1
                return
            espera = d["espera"]
            if espera is None or time.monotonic() - inicio + espera > espera_maxima:
                raise CotaExcedida(d["motivo"], espera or 0)
            time.sleep(min(espera, 5.0))

    def adquirir_vaga(self, cancelamento: Cancelamento | None = None, timeout: float = 120.0):
        """Fila global: no máximo CONCORRENCIA_GLOBAL chamadas simultâneas."""
        fim = time.monotonic() + timeout
        while True:
            if cancelamento:
                cancelamento.verificar()
            if self._semaforo.acquire(timeout=1.0):
                return
            if time.monotonic() > fim:
                raise CotaExcedida("Fila de requisições cheia por tempo demais.")

    def liberar_vaga(self):
        try:
            self._semaforo.release()
        except ValueError:
            pass

    def registrar(self, provedor: str, ok: bool, http: int | None = None, retry_after: float | None = None,
                  tokens_reais: int | None = None, erro: str = "") -> None:
        with self._lock:
            e = self._estado(provedor)
            if ok:
                e.falhas_seguidas = 0
                e.chamadas_ok += 1
                e.ultimo_erro = ""
                return
            e.chamadas_erro += 1
            e.ultimo_erro = config.mascarar(erro)[:160]
            if http == 429:
                pausa = float(retry_after) if retry_after and retry_after > 0 else 60.0
                pausa = min(pausa, 15 * 60)
                if re.search(r"upstream|temporarily rate-limited|model is overloaded|try another model", erro or "", re.IGNORECASE):
                    pausa = min(pausa, 5.0)  # limite de um modelo específico, não da chave: não trava o provedor
                e.cooldown_ate = time.monotonic() + pausa
                e.motivo_cooldown = "limite de cota HTTP 429"
                if retry_after and retry_after >= 3600:
                    e.desativado = "cota diária esgotada (HTTP 429 com espera longa)"
                return
            if http in (401, 403):
                e.falhas_seguidas += 1
                e.desativado = f"credencial rejeitada (HTTP {http}); corrija a chave em Sistema"
                return
            if http == 402:
                e.desativado = "o provedor exigiu crédito/pagamento (HTTP 402); uso interrompido para não gerar custo"
                return
            e.falhas_seguidas += 1
            if e.falhas_seguidas >= FALHAS_PARA_DESATIVAR:
                e.cooldown_ate = time.monotonic() + 10 * 60
                e.motivo_cooldown = f"{e.falhas_seguidas} falhas seguidas"

    def reativar(self, provedor: str) -> None:
        with self._lock:
            e = self._estado(provedor)
            e.desativado = ""
            e.cooldown_ate = 0.0
            e.falhas_seguidas = 0

    def reiniciar_sessao(self) -> None:
        with self._lock:
            self._sessao_chamadas = 0

    def estado(self) -> dict:
        with self._lock:
            agora = time.monotonic()
            saida = {}
            for nome, e in self._estados.items():
                self._rolar(e, agora)
                saida[nome] = {
                    "limites": e.limites, "ultimo_minuto": len(e.minuto), "hoje": e.dia,
                    "tokens_ultimo_minuto": sum(t for _, t in e.tokens_minuto),
                    "cooldown_restante_s": max(0, int(e.cooldown_ate - agora)), "motivo_cooldown": e.motivo_cooldown if agora < e.cooldown_ate else "",
                    "desativado": e.desativado, "falhas_seguidas": e.falhas_seguidas, "ultimo_erro": e.ultimo_erro,
                    "chamadas_ok": e.chamadas_ok, "chamadas_erro": e.chamadas_erro,
                }
            return {"provedores": saida, "chamadas_sessao": self._sessao_chamadas, "limite_sessao": self.limite_sessao(),
                    "concorrencia": CONCORRENCIA_GLOBAL}


COTAS = Cotas()
