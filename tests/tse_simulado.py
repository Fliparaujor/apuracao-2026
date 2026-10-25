"""Servidor TSE SIMULADO para testes (claramente rotulado como simulação).

Reproduz o formato EA20 (`-u.json`) com os nomes de campo observados nos
arquivos oficiais de 2026 (carg/agr/par/cand, vap/pvap/pvapn, s.pst/pstn/st/ts,
v.vv/vb/tvn, e.te/c/a/est, dt/ht, dg/hg, tf, cdabr). Os números são fictícios
e derivados de um gerador determinístico — nunca devem ser exibidos como reais.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UFS = ("ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
       "rs", "ro", "rr", "sc", "sp", "se", "to")


def fmt_int(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def fmt_pct(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def arquivo_presidente(abr: str, ele: int, boletim: int = 0, final: bool = False, vazio: bool = False) -> dict:
    """Gera um arquivo EA20 fictício. `boletim` avança a totalização."""
    semente = sum(ord(c) for c in abr) % 17
    ts = 499248 if abr == "br" else 23765 if abr == "ce" else 1500 if abr == "ap" else 8000 + semente * 900
    if abr.startswith(("ce", "ap")) and len(abr) > 2:
        ts = 6000 if abr.startswith("ce") else 700
    frac = 1.0 if final else min(0.999, 0.0025 * (boletim + 1) * (1 + semente / 10))
    st = int(ts * frac)
    if vazio:
        st = 0
    eleitorado = ts * 310
    est = int(eleitorado * frac)
    comparecimento = int(est * 0.79)
    brancos = int(comparecimento * 0.012)
    nulos = int(comparecimento * 0.022)
    vv = comparecimento - brancos - nulos
    p13 = 0.52 + (semente - 8) * 0.012 + (boletim % 3) * 0.002
    if ele == 6257:
        v13, v22 = int(vv * 0.4516), int(vv * 0.4703)
        outros = vv - v13 - v22
        cands = [("22", "FLAVIO BOLSONARO", "PL", v22), ("13", "LULA", "PT", v13), ("15", "TERCEIRA VIA", "MDB", outros)]
    else:
        v13 = int(vv * p13)
        cands = [("13", "LULA", "PT", v13), ("22", "FLAVIO BOLSONARO", "PL", vv - v13)]
    hora = f"{17 + (boletim // 10) % 6:02d}:{(boletim * 3) % 60:02d}:{(boletim * 7) % 60:02d}"
    data = "04/10/2026" if ele == 6257 else "25/10/2026"
    partidos = []
    for n, nome, sg, votos in cands:
        pct = 100 * votos / vv if vv else 0
        partidos.append({"sg": sg, "cand": [{"n": n, "nm": nome.title(), "nmu": nome, "vap": fmt_int(votos) if vv else "0",
                                            "pvap": fmt_pct(pct), "pvapn": round(pct, 4), "st": "Eleito" if final and votos == max(c[3] for c in cands) else "",
                                            "e": "s" if final and votos == max(c[3] for c in cands) else "n", "sqcand": "28000" + n, "dvt": "Válido"}]})
    return {
        "ele": str(ele), "t": "1" if ele == 6257 else "2", "cdabr": abr.upper(), "tpabr": "MU" if len(abr) > 2 else "UF" if abr != "br" else "BR",
        "dg": data, "hg": hora, "dt": data, "ht": hora, "tf": "s" if final else "n", "md": "s" if final else "n",
        "f": "SIMULADO", "simulacao": "DADOS FICTÍCIOS PARA TESTE",
        "s": {"ts": fmt_int(ts), "st": fmt_int(st), "snt": fmt_int(ts - st), "pst": fmt_pct(100 * st / ts), "pstn": round(100 * st / ts, 6)},
        "e": {"te": fmt_int(eleitorado), "est": fmt_int(est), "c": fmt_int(comparecimento), "pc": fmt_pct(100 * comparecimento / est if est else 0),
              "a": fmt_int(est - comparecimento), "pa": fmt_pct(100 * (est - comparecimento) / est if est else 0)},
        "v": {"vv": fmt_int(vv), "pvv": fmt_pct(100 * vv / comparecimento if comparecimento else 0), "vb": fmt_int(brancos),
              "pvb": fmt_pct(100 * brancos / comparecimento if comparecimento else 0), "tvn": fmt_int(nulos),
              "ptvn": fmt_pct(100 * nulos / comparecimento if comparecimento else 0), "tv": fmt_int(comparecimento)},
        "carg": [{"cd": "1", "ds": "Presidente", "agr": [{"par": [p]} for p in partidos]}],
    }


def arquivo_governador(uf: str, boletim: int = 0) -> dict:
    base = arquivo_presidente(uf, 6260, boletim)
    base["ele"] = "6260"
    base["carg"][0]["cd"], base["carg"][0]["ds"] = "3", "Governador"
    base["carg"][0]["agr"][0]["par"][0]["cand"][0].update({"n": "40", "nm": "Candidata A", "nmu": "CANDIDATA A"})
    base["carg"][0]["agr"][1]["par"][0]["cand"][0].update({"n": "55", "nm": "Candidato B", "nmu": "CANDIDATO B"})
    return base


class EstadoSimulado:
    def __init__(self):
        self.boletim = 3
        self.final = False
        self.vazio = False
        self.indisponivel = False
        self.governadores = {"ac", "am", "df", "es", "rn", "to"}
        self.lock = threading.Lock()
        self.requisicoes = 0


ESTADO = EstadoSimulado()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        import re
        with ESTADO.lock:
            ESTADO.requisicoes += 1
            if ESTADO.indisponivel:
                return self._envia(503, {"erro": "simulado indisponível"})
            m = re.fullmatch(r"/ele2026/(\d+)/dados/([a-z]{2})/([a-z]{2})(\d{5})?-c(\d{4})-e(\d{6})-u\.json", self.path)
            if self.path == "/comum/config/ele-c.json":
                return self._envia(200, {"c": "ele2026", "pl": [
                    {"cd": "3220", "dt": "04/10/2026", "e": [{"cd": "6257", "cdt2": "6258", "nm": "Eleição Ordinária Federal - 2026 1º Turno", "t": "1"},
                                                            {"cd": "6259", "cdt2": "6260", "nm": "Eleições Gerais Estaduais 2026 - 1º Turno", "t": "1"}]},
                    {"cd": "3221", "dt": "25/10/2026", "e": [{"cd": "6258", "nm": "Eleição Ordinária Federal - 2026 2º Turno", "t": "2"},
                                                            {"cd": "6260", "nm": "Eleições Gerais Estaduais 2026 - 2º Turno", "t": "2"}]}]})
            if re.fullmatch(r"/ele2026/\d+/config/mun-e\d{6}-cm\.json", self.path):
                return self._envia(200, {"abr": [{"cd": "CE", "mu": [{"cd": "13897", "nm": "FORTALEZA"}, {"cd": "13030", "nm": "CAUCAIA"}]},
                                                 {"cd": "AP", "mu": [{"cd": "06050", "nm": "MACAPÁ"}]}]})
            if not m:
                return self._envia(404, {"erro": "não encontrado"})
            ele, uf, uf2, mun, cargo, ele6 = m.groups()
            if uf != uf2 or int(ele) != int(ele6):
                return self._envia(404, {"erro": "não encontrado"})
            abr = uf + (mun or "")
            if cargo == "0003":
                if int(ele) != 6260 or uf not in ESTADO.governadores:
                    return self._envia(404, {"erro": "sem segundo turno"})
                return self._envia(200, arquivo_governador(uf, ESTADO.boletim))
            if int(ele) == 6257:
                return self._envia(200, arquivo_presidente(abr, 6257, 400, final=True))
            if int(ele) != 6258:
                return self._envia(404, {"erro": "eleição desconhecida"})
            return self._envia(200, arquivo_presidente(abr, 6258, ESTADO.boletim, ESTADO.final, ESTADO.vazio))

    def _envia(self, status: int, obj: dict):
        dados = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


def iniciar(porta: int = 0) -> tuple[ThreadingHTTPServer, str]:
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{servidor.server_address[1]}"


if __name__ == "__main__":
    import sys
    s, url = iniciar(int(sys.argv[1]) if len(sys.argv) > 1 else 9090)
    print("TSE SIMULADO (dados fictícios) em", url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
