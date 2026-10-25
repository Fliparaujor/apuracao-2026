"""Gera os ícones PNG do PWA (192/512) sem dependências externas."""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web" / "icones"


def png(largura: int, altura: int, pixels: bytes) -> bytes:
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)
    linhas = b"".join(b"\x00" + pixels[y * largura * 4:(y + 1) * largura * 4] for y in range(altura))
    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(linhas, 9)) + bloco(b"IEND", b""))


def desenhar(n: int, maskable: bool = False) -> bytes:
    fundo = (6, 11, 22)
    azul = (61, 139, 253)
    ciano = (76, 201, 240)
    out = bytearray()
    cx = cy = n / 2
    raio_fundo = n * (0.5 if maskable else 0.46)
    for y in range(n):
        for x in range(n):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            if not maskable and d > raio_fundo:
                out += bytes((0, 0, 0, 0))
                continue
            r, g, b = fundo
            # grade sutil
            if (x % max(8, n // 24)) == 0 or (y % max(8, n // 24)) == 0:
                r, g, b = 10, 18, 34
            # anéis do radar
            for k, raio in enumerate((0.36, 0.26, 0.16)):
                if abs(d - n * raio) < n * 0.012:
                    r, g, b = azul if k != 1 else ciano
            # varredura (setor)
            ang = math.atan2(dy, dx)
            if 0 < d < n * 0.36 and -0.9 < ang < -0.2:
                f = 0.35 + 0.65 * (ang + 0.9) / 0.7
                r = int(r + (azul[0] - r) * 0.35 * f)
                g = int(g + (azul[1] - g) * 0.35 * f)
                b = int(b + (azul[2] - b) * 0.35 * f)
            # ponto central e alvo
            if d < n * 0.03 or (abs(dx - n * 0.17) < n * 0.028 and abs(dy + n * 0.14) < n * 0.028):
                r, g, b = ciano
            out += bytes((r, g, b, 255))
    return png(n, n, bytes(out))


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "icone-192.png").write_bytes(desenhar(192))
    (WEB / "icone-512.png").write_bytes(desenhar(512))
    (WEB / "icone-maskable-512.png").write_bytes(desenhar(512, maskable=True))
    print("Ícones gerados em", WEB)


if __name__ == "__main__":
    main()
