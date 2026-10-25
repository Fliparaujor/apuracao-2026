#!/usr/bin/env bash
# Radar 2026 — atalhos para o Termux (Samsung Galaxy S23).
#   bash radar.sh            → inicia o servidor
#   bash radar.sh iniciar    → idem
#   bash radar.sh configurar → assistente de chaves (uma vez)
#   bash radar.sh chaves     → listar / adicionar / remover / testar chaves
#   bash radar.sh diagnostico
#   bash radar.sh atualizar  → git pull + reinício
#   bash radar.sh testes     → testes automatizados
set -u
cd "$(dirname "$0")"
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
cmd="${1:-iniciar}"; shift || true
wake_lock() { command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock 2>/dev/null || true; }
wake_unlock() { command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock 2>/dev/null || true; }
case "$cmd" in
  iniciar|start)
    wake_lock
    trap wake_unlock EXIT
    echo "Abra no Chrome: http://127.0.0.1:${PORT:-8080}/   (Ctrl+C encerra; o histórico fica guardado)"
    "$PY" -m radar iniciar "$@"
    ;;
  configurar|config) "$PY" -m radar configurar "$@" ;;
  chaves|keys) "$PY" -m radar chaves "$@" ;;
  testar-ia) "$PY" -m radar testar-ia "$@" ;;
  diagnostico|diag) "$PY" -m radar diagnostico "$@" ;;
  atualizar|update)
    git pull --ff-only && echo "Atualizado. Inicie com: bash radar.sh iniciar"
    ;;
  testes|test) "$PY" -m unittest discover -s tests -v ;;
  *) echo "Uso: bash radar.sh [iniciar|configurar|chaves|testar-ia|diagnostico|atualizar|testes]"; exit 1 ;;
esac
