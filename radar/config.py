"""Configuração, caminhos e segredos.

Segredos ficam em um arquivo fora do repositório (permissão 600), nunca em
commits, logs, respostas HTTP ou telas. Variáveis de ambiente têm precedência,
para quem preferir exportá-las no Termux.
"""
from __future__ import annotations

import json
import os
import re
import stat
import threading
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
_lock = threading.RLock()

# Nome da variável -> provedor. Mantido aqui para o configurador e o mascaramento.
VARIAVEIS_SEGREDO = {
    "GROQ_API_KEY": "groq",
    "GEMINI_API_KEY": "gemini",
    "MISTRAL_API_KEY": "mistral",
    "OPENROUTER_API_KEY": "openrouter",
    "COHERE_API_KEY": "cohere",
    "CLOUDFLARE_API_TOKEN": "cloudflare",
    "CLOUDFLARE_ACCOUNT_ID": "cloudflare",
    "HF_TOKEN": "huggingface",
}

# Padrões de chaves conhecidos, usados apenas para MASCARAR texto antes de exibir.
PADROES_CHAVE = [
    re.compile(r"gsk_[A-Za-z0-9_\-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-or-v1-[0-9a-f]{20,}"),
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}"),
]

PADRAO_CONFIG = {
    "porta": 8080,
    "bind": "127.0.0.1",
    "coleta_automatica": True,
    "intervalo_coleta_segundos": 30,
    "intervalo_estados_segundos": 60,
    "escopos_prioritarios": ["br", "ce", "ap", "ce13897", "ap06050"],
    "analise_automatica": False,
    "limites_sessao": {"chamadas_ia_por_sessao": 120, "reunioes_por_hora": 6},
    "papeis_personalizados": {},
    "provedores_desativados": [],
    "modelos_preferidos": {},
    "rodadas_maximas": 5,
    "limites_cotas": {},
}


def home() -> Path:
    base = os.environ.get("RADAR_HOME")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".radar2026"


def garantir_home() -> Path:
    h = home()
    h.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(h, 0o700)
    except OSError:
        pass
    return h


def caminho_banco() -> Path:
    return Path(os.environ.get("RADAR_DB", str(garantir_home() / "radar.sqlite3")))


def caminho_segredos() -> Path:
    return garantir_home() / "segredos.env"


def caminho_config() -> Path:
    return garantir_home() / "config.json"


def caminho_log() -> Path:
    return garantir_home() / "radar.log"


def _ler_env_file(caminho: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not caminho.exists():
        return valores
    try:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave in VARIAVEIS_SEGREDO and valor:
                valores[chave] = valor
    except OSError:
        pass
    return valores


def segredo(nome: str) -> str:
    """Retorna o valor de um segredo (ambiente > arquivo). Nunca registre o retorno."""
    if nome not in VARIAVEIS_SEGREDO:
        return ""
    valor = os.environ.get(nome, "").strip()
    if valor:
        return valor
    with _lock:
        return _ler_env_file(caminho_segredos()).get(nome, "").strip()


def segredo_presente(nome: str) -> bool:
    return bool(segredo(nome))


def origem_segredo(nome: str) -> str:
    if os.environ.get(nome, "").strip():
        return "ambiente"
    if _ler_env_file(caminho_segredos()).get(nome):
        return "arquivo"
    return "ausente"


def gravar_segredo(nome: str, valor: str) -> None:
    if nome not in VARIAVEIS_SEGREDO:
        raise ValueError("Variável de segredo desconhecida.")
    valor = (valor or "").strip()
    if any(c in valor for c in "\r\n"):
        raise ValueError("Valor inválido.")
    with _lock:
        caminho = caminho_segredos()
        atual = _ler_env_file(caminho)
        if valor:
            atual[nome] = valor
        else:
            atual.pop(nome, None)
        linhas = ["# Radar 2026 — segredos locais. Nunca compartilhe este arquivo."]
        linhas += [f"{k}={v}" for k, v in sorted(atual.items())]
        tmp = caminho.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        os.replace(tmp, caminho)
        try:
            os.chmod(caminho, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def remover_segredo(nome: str) -> None:
    gravar_segredo(nome, "")


def permissoes_segredos_ok() -> bool:
    caminho = caminho_segredos()
    if not caminho.exists():
        return True
    try:
        modo = stat.S_IMODE(caminho.stat().st_mode)
    except OSError:
        return False
    return modo & 0o077 == 0


def mascarar(texto: str) -> str:
    """Remove qualquer segredo conhecido ou padrão de chave de um texto."""
    if not texto:
        return texto
    saida = str(texto)
    for nome in VARIAVEIS_SEGREDO:
        valor = segredo(nome)
        if valor and len(valor) >= 6:
            saida = saida.replace(valor, "[segredo]")
    for padrao in PADROES_CHAVE:
        saida = padrao.sub("[segredo]", saida)
    return saida


def carregar_config() -> dict:
    with _lock:
        dados = dict(PADRAO_CONFIG)
        caminho = caminho_config()
        if caminho.exists():
            try:
                lido = json.loads(caminho.read_text(encoding="utf-8"))
                if isinstance(lido, dict):
                    for k, v in lido.items():
                        if k in PADRAO_CONFIG:
                            dados[k] = v
            except (OSError, ValueError):
                pass
        porta = os.environ.get("PORT")
        if porta and porta.isdigit():
            dados["porta"] = int(porta)
        if os.environ.get("RADAR_BIND"):
            dados["bind"] = os.environ["RADAR_BIND"]
        if os.environ.get("RADAR_SEM_COLETA") == "1":
            dados["coleta_automatica"] = False
        return dados


def gravar_config(alteracoes: dict) -> dict:
    with _lock:
        atual = carregar_config()
        for k, v in alteracoes.items():
            if k in PADRAO_CONFIG:
                atual[k] = v
        caminho_config().write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
        return atual
