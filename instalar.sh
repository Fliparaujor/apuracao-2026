#!/usr/bin/env bash
# Instalador do Radar 2026 para Termux (Android). Um único comando:
#   curl -fsSL https://raw.githubusercontent.com/Fliparaujor/apuracao-2026/main/instalar.sh | bash
# Instala Python e Git, baixa/atualiza o projeto, pede as chaves gratuitas (opcional) e inicia o servidor.
set -u
REPO="https://github.com/Fliparaujor/apuracao-2026.git"
BRANCH="${RADAR_BRANCH:-main}"
DEST="${RADAR_DIR:-$HOME/apuracao-2026}"

echo "== Radar 2026 + O Conselho · instalação =="
if command -v pkg >/dev/null 2>&1 && [ -d "/data/data/com.termux" ]; then
  echo "Termux detectado. Instalando python e git (pode demorar na primeira vez)…"
  pkg update -y >/dev/null 2>&1 || true
  pkg install -y python git termux-api >/dev/null 2>&1 || pkg install -y python git || { echo "Falha ao instalar pacotes. Rode: pkg install python git"; exit 1; }
else
  echo "Não é Termux: usando o Python do sistema."
fi
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ necessário"' || exit 1
"$PY" -c 'import sqlite3, ssl' || { echo "Python sem sqlite3/ssl. No Termux: pkg install python"; exit 1; }

if [ -d "$DEST/.git" ]; then
  echo "Projeto já existe em $DEST: atualizando…"
  git -C "$DEST" fetch --quiet origin "$BRANCH" && git -C "$DEST" checkout --quiet "$BRANCH" 2>/dev/null; git -C "$DEST" pull --ff-only --quiet origin "$BRANCH" || echo "Aviso: não foi possível atualizar (alterações locais?)."
else
  echo "Baixando o projeto para $DEST…"
  git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$DEST" || { echo "Falha ao clonar."; exit 1; }
fi
cd "$DEST"
mkdir -p "$HOME/.radar2026" && chmod 700 "$HOME/.radar2026"
# Quando executado via "curl | bash", a entrada padrão é o script: religa ao terminal para as perguntas.
if [ ! -t 0 ] && [ -r /dev/tty ]; then exec </dev/tty 2>/dev/null || true; fi
echo
echo "Verificando o ambiente…"
"$PY" -m radar diagnostico --sem-ia || echo "(O TSE pode estar indisponível agora; o app avisa na tela.)"
echo
if [ -t 0 ]; then
  read -r -p "Configurar chaves gratuitas de IA agora? (pode pular e fazer depois com: bash radar.sh chaves) [s/N] " resp
  case "${resp:-n}" in s|S|sim|y|Y) "$PY" -m radar configurar --inicial ;; esac
else
  echo "Entrada não interativa: pule a configuração das chaves e rode depois: bash radar.sh chaves"
fi
echo
echo "Pronto. Para iniciar agora e nas próximas vezes:"
echo "   cd $DEST && bash radar.sh"
echo "Depois abra no Chrome: http://127.0.0.1:8080/"
if [ -t 0 ]; then
  read -r -p "Iniciar o servidor agora? [S/n] " go
  case "${go:-s}" in n|N) exit 0 ;; esac
  exec bash radar.sh iniciar
fi
