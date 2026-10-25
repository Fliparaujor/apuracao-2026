#!/usr/bin/env python3
"""Radar 2026 - servidor localhost para Android (Termux), sem dependências externas.

Entrega HTML/CSS/JS localmente e atua como proxy restrito de arquivos oficiais
do TSE. Não altera o JSON, não gera votos nem inventa dados.
"""
from __future__ import annotations
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import inteligencia
import conselho

ROOT = Path(__file__).resolve().parent
ORIGIN = "https://resultados.tse.jus.br/oficial/ele2026/"
PORT = int(os.environ.get("PORT", "8080"))
TTL_SECONDS = 20
TIMEOUT = 12
GOV_UFS = {"am", "rn", "df", "es", "ac", "to"}

# Não permite URL arbitrária nem outros domínios: só dois códigos e seus cargos.
PRES = re.compile(r"^6258/dados/(br|[a-z]{2})/([a-z]{2})([0-9]{5})?-c0001-e006258-u[.]json$")
GOV = re.compile(r"^6260/dados/([a-z]{2})/([a-z]{2})-c0003-e006260-u[.]json$")
_lock = threading.Lock()
_cached: dict[str, tuple[float, bytes]] = {}

def allowed(relative: str) -> bool:
    p = PRES.fullmatch(relative)
    if p:
        return p.group(1) == p.group(2) and (p.group(1) != "br" or p.group(3) is None)
    g = GOV.fullmatch(relative)
    return bool(g and g.group(1) == g.group(2) and g.group(1) in GOV_UFS)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/index"):
            self.path = "/ao-vivo.html"
        if path == "/api/conselho/status":
            self.send_json(200, conselho.public_status())
            return
        if path == "/api/ia/status":
            self.send_json(200, inteligencia.status())
            return
        if path.startswith("/api/tse/"):
            self.proxy_tse(path[len("/api/tse/"):])
            return
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path not in ("/api/ia/analisar", "/api/conselho/debater"):
            self.send_json(404, {"erro": "Endpoint inexistente."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not (0 < size <= 4096):
                self.send_json(413, {"erro": "Mensagem muito grande."})
                return
            if "application/json" not in self.headers.get("Content-Type", ""):
                self.send_json(415, {"erro": "Envie application/json."})
                return
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Envie um objeto JSON.")
            if path == "/api/conselho/debater":
                self.send_json(200, conselho.deliberate(payload))
            else:
                self.send_json(200, inteligencia.run(payload))
        except (ValueError, json.JSONDecodeError) as err:
            self.send_json(400, {"erro": str(err)[:300]})
        except RuntimeError as err:
            self.send_json(503, {"erro": str(err)[:300]})
        except Exception as err:
            # Não expor credenciais, URLs de requisição ou rastros internos.
            print("Falha no módulo de inteligência:", type(err).__name__)
            self.send_json(502, {"erro": "Não foi possível completar a consulta ao TSE ou às IAs neste momento."})

    def proxy_tse(self, relative: str):
        if not allowed(relative):
            self.send_json(400, {"erro": "Rota não permitida. Confirme os códigos oficiais do TSE."})
            return
        now = time.monotonic()
        with _lock:
            c = _cached.get(relative)
            if c and now - c[0] < TTL_SECONDS:
                self.send_raw(200, c[1])
                return
        try:
            req = urllib.request.Request(
                ORIGIN + relative,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Linux; Android 16; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                data = response.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024:
                    raise ValueError("Arquivo muito grande")
                decoded = json.loads(data)
                if not isinstance(decoded, dict) or "carg" not in decoded:
                    raise ValueError("O TSE retornou formato inesperado")
            with _lock:
                _cached[relative] = (time.monotonic(), data)
            self.send_raw(200, data)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print("TSE não disponível para", relative, str(exc)[:160])
            self.send_json(502, {"erro": "TSE não respondeu. A apuração não foi inventada."})

    def send_raw(self, status: int, data: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, obj: dict):
        self.send_raw(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt: str, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))

if __name__ == "__main__":
    print("Radar 2026 rodando em http://127.0.0.1:%s/ao-vivo.html" % PORT)
    print("Analista IA: " + ("configurado" if inteligencia.status()["configurada"] else "aguardando chave Groq/Gemini"))
    print("Mantenha o Termux aberto. Para encerrar: CTRL+C")
    with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()
