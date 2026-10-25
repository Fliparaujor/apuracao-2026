#!/usr/bin/env python3
"""Ponto de entrada compatível: `python server.py` inicia o Radar 2026."""
import sys

from radar.servidor import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
