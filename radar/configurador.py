"""Configurador interativo para Termux: chaves sem exibição, teste real e gravação segura."""
from __future__ import annotations

import getpass
import sys

from . import config, provedores
from .provedores import ORDEM, PROVEDORES

AJUDA_PROVEDOR = {
    "groq": "GroqCloud (gratuito, sem cartão): crie em https://console.groq.com/keys",
    "gemini": "Google AI Studio (free tier): crie em https://aistudio.google.com/api-keys",
    "mistral": "Mistral (plano gratuito; pede telefone): https://console.mistral.ai/api-keys",
    "openrouter": "OpenRouter (só modelos ':free'): https://openrouter.ai/settings/keys",
    "cohere": "Cohere (chave trial, uso não comercial): https://dashboard.cohere.com/api-keys",
    "cloudflare": "Cloudflare Workers AI (plano Workers Free): token + ID da conta em https://dash.cloudflare.com",
    "huggingface": "Hugging Face (crédito mensal mínimo; opcional): https://huggingface.co/settings/tokens",
}


def _perguntar_sim(texto: str, padrao: bool = False) -> bool:
    r = input(f"{texto} [{'S/n' if padrao else 's/N'}] ").strip().lower()
    if not r:
        return padrao
    return r in ("s", "sim", "y", "yes")


def _ler_segredo(rotulo: str) -> str:
    try:
        return getpass.getpass(f"  Cole {rotulo} (não aparece ao digitar; Enter para pular): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _resultado(r: dict) -> str:
    if r["ok"]:
        return f"✔ autenticado · modelo: {r['modelo']} ({len(r.get('modelos', []))} utilizáveis)"
    return f"✘ {r['estado']}: {r['mensagem']}"


def configurar_provedor(ident: str, forcar_pergunta: bool = True) -> dict | None:
    p = PROVEDORES[ident]
    print(f"\n— {p.nome}: {AJUDA_PROVEDOR.get(ident, '')}")
    print(f"  {p.nota_gratuita}")
    if p.configurado():
        print(f"  Já existe uma chave ({config.origem_segredo(p.variaveis[0])}).")
        if not _perguntar_sim("  Substituir?", False):
            r = provedores.autenticar(ident, forcar=True)
            print("  " + _resultado(r))
            return r
    elif forcar_pergunta and not _perguntar_sim(f"  Você tem chave do {p.nome}?", False):
        return None
    valores = {}
    for var in p.variaveis:
        rotulo = "o ID da conta (32 caracteres)" if var == "CLOUDFLARE_ACCOUNT_ID" else "a chave"
        if var == "CLOUDFLARE_ACCOUNT_ID":
            valor = input(f"  Digite {rotulo}: ").strip()
        else:
            valor = _ler_segredo(rotulo)
        if not valor:
            print("  Pulado.")
            return None
        valores[var] = valor
    for var, valor in valores.items():
        config.gravar_segredo(var, valor)
    provedores.limpar_cache_auth(ident)
    print("  Testando a autenticação (a chave não será exibida)…")
    r = provedores.autenticar(ident, forcar=True)
    print("  " + _resultado(r))
    if not r["ok"] and r["estado"] in ("chave_invalida", "sem_permissao"):
        if _perguntar_sim("  Remover esta chave inválida do arquivo?", True):
            for var in p.variaveis:
                config.remover_segredo(var)
            provedores.limpar_cache_auth(ident)
    return r


def assistente(inicial: bool = False) -> int:
    print("\n=== Radar 2026 · configuração das chaves gratuitas ===")
    print(f"As chaves ficam em {config.caminho_segredos()} (permissão 600), fora do Git.")
    print("Nunca cole chaves em conversas, prints ou mensagens. Pule o que não tiver.\n")
    config.garantir_home()
    resultados = []
    for ident in ORDEM:
        try:
            r = configurar_provedor(ident)
        except (EOFError, KeyboardInterrupt):
            print("\nInterrompido.")
            break
        if r:
            resultados.append((ident, r))
    prontos = [i for i, r in resultados if r["ok"]]
    print("\nResumo:")
    for ident in ORDEM:
        p = PROVEDORES[ident]
        r = dict(resultados).get(ident)
        print(f"  {p.nome:<22} " + ("sem chave" if not p.configurado() else _resultado(r) if r else "chave presente (não testada agora)"))
    print(f"\nModelos prontos para O Conselho: {len(prontos)}" + (" (mínimo 2 para haver confronto; 1 gera análise individual)" if len(prontos) < 2 else ""))
    if not config.permissoes_segredos_ok():
        print("AVISO: o arquivo de segredos está com permissões abertas; rode: chmod 600 " + str(config.caminho_segredos()))
    return 0


def listar() -> int:
    print(f"Arquivo: {config.caminho_segredos()} · permissões {'ok' if config.permissoes_segredos_ok() else 'ABERTAS'}")
    for ident in ORDEM:
        p = PROVEDORES[ident]
        estado = "sem chave"
        if p.configurado():
            estado = f"chave presente ({config.origem_segredo(p.variaveis[0])})"
        print(f"  {ident:<12} {p.nome:<22} {estado}")
    return 0


def remover(ident: str) -> int:
    if ident not in PROVEDORES:
        print("Provedor desconhecido. Opções: " + ", ".join(ORDEM))
        return 1
    for var in PROVEDORES[ident].variaveis:
        config.remover_segredo(var)
    provedores.limpar_cache_auth(ident)
    print(f"Chave do {PROVEDORES[ident].nome} removida do arquivo local. Revogue-a também no site do provedor.")
    return 0


def testar(ident: str | None = None) -> int:
    alvos = [ident] if ident else [i for i in ORDEM if PROVEDORES[i].configurado()]
    if not alvos:
        print("Nenhuma chave configurada. Use: bash radar.sh chaves")
        return 1
    codigo = 0
    for i in alvos:
        if i not in PROVEDORES:
            print("Provedor desconhecido:", i)
            return 1
        r = provedores.autenticar(i, forcar=True)
        print(f"{PROVEDORES[i].nome:<22} {_resultado(r)}")
        codigo = codigo or (0 if r["ok"] else 2)
    return codigo


def menu_chaves() -> int:
    while True:
        print("\nChaves: [1] listar  [2] adicionar/substituir  [3] remover  [4] testar  [0] sair")
        try:
            op = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if op == "0":
            return 0
        if op == "1":
            listar()
        elif op == "2":
            ident = input("Provedor (" + ", ".join(ORDEM) + "): ").strip().lower()
            if ident in PROVEDORES:
                configurar_provedor(ident, forcar_pergunta=False)
            else:
                print("Provedor desconhecido.")
        elif op == "3":
            remover(input("Provedor: ").strip().lower())
        elif op == "4":
            testar()
