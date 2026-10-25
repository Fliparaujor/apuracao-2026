"""CLI: python -m radar <comando>

  iniciar        inicia o servidor local (padrão)
  configurar     assistente interativo das chaves gratuitas
  chaves         menu: listar / adicionar / remover / testar chaves
  testar-ia      testa a autenticação dos provedores configurados
  diagnostico    diagnóstico completo em texto (sem segredos)
  versao
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    comando = argv[0] if argv else "iniciar"
    if comando in ("-h", "--help", "ajuda"):
        print(__doc__)
        return 0
    if comando == "versao":
        from . import VERSAO
        print(VERSAO)
        return 0
    if comando == "iniciar":
        from .servidor import main as servir
        return servir(argv[1:])
    if comando == "configurar":
        from . import db
        from .configurador import assistente
        db.inicializar()
        return assistente(inicial="--inicial" in argv)
    if comando == "chaves":
        from . import db
        from .configurador import listar, menu_chaves, remover, testar, configurar_provedor
        db.inicializar()
        sub = argv[1] if len(argv) > 1 else ""
        if sub == "listar":
            return listar()
        if sub in ("adicionar", "substituir") and len(argv) > 2:
            r = configurar_provedor(argv[2].lower(), forcar_pergunta=False)
            return 0 if r and r.get("ok") else 2
        if sub == "remover" and len(argv) > 2:
            return remover(argv[2].lower())
        if sub == "testar":
            return testar(argv[2].lower() if len(argv) > 2 else None)
        return menu_chaves()
    if comando == "testar-ia":
        from . import db
        from .configurador import testar
        db.inicializar()
        return testar(argv[1] if len(argv) > 1 else None)
    if comando == "diagnostico":
        from . import db, diagnostico, tse
        db.inicializar()
        try:
            tse.descobrir_eleicoes()
        except Exception:  # noqa: BLE001
            pass
        d = diagnostico.executar(testar_ia="--sem-ia" not in argv)
        print(diagnostico.texto(d))
        return 0 if d["tse"]["ok"] and d["banco"]["ok"] else 1
    print("Comando desconhecido:", comando)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
