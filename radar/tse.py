"""Camada 1 — coleta dos arquivos oficiais de resultado do TSE (EA20, `-u.json`).

Fonte: https://resultados.tse.jus.br/oficial/ele2026/<eleicao>/dados/<uf>/<uf><mun>-c<cargo>-e<eleicao>-u.json

Códigos confirmados na página técnica do TSE e no arquivo de configuração
`comum/config/ele-c.json` (pleito de 25/10/2026):
  6257 — Eleição Ordinária Federal 2026, 1º turno (04/10/2026)
  6258 — Eleição Ordinária Federal 2026, 2º turno (25/10/2026)
  6260 — Eleições Gerais Estaduais 2026, 2º turno (25/10/2026)
O código do 1º turno estadual (6259) segue o padrão numérico do TSE e só é
usado quando confirmado em `ele-c.json`; até lá fica marcado como não verificado.

Esta camada não inventa números: qualquer falha vira erro explícito.
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
from datetime import datetime, timedelta, timezone

BASE_PADRAO = "https://resultados.tse.jus.br/oficial"
CICLO = "ele2026"
BRASILIA = timezone(timedelta(hours=-3))
DATA_SEGUNDO_TURNO = "25/10/2026"
TIMEOUT = 12
TTL_SEGUNDOS = 15
LIMITE_BYTES = 4 * 1024 * 1024
USER_AGENT = "Radar2026/3.0 (+https://github.com/Fliparaujor/apuracao-2026; Termux Android)"

ELEICOES = {
    "presidente": {"cargo": "0001", "turno2": 6258, "turno1": 6257, "verificado": True,
                   "nome": "Presidente"},
    "governador": {"cargo": "0003", "turno2": 6260, "turno1": 6259, "verificado": True,
                   "turno1_verificado": False, "nome": "Governador"},
}

UFS = ("ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg",
       "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to")
NOMES_UF = {
    "ac": "Acre", "al": "Alagoas", "ap": "Amapá", "am": "Amazonas", "ba": "Bahia", "ce": "Ceará",
    "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás", "ma": "Maranhão",
    "mt": "Mato Grosso", "ms": "Mato Grosso do Sul", "mg": "Minas Gerais", "pa": "Pará",
    "pb": "Paraíba", "pr": "Paraná", "pe": "Pernambuco", "pi": "Piauí", "rj": "Rio de Janeiro",
    "rn": "Rio Grande do Norte", "rs": "Rio Grande do Sul", "ro": "Rondônia", "rr": "Roraima",
    "sc": "Santa Catarina", "sp": "São Paulo", "se": "Sergipe", "to": "Tocantins",
    "br": "Brasil", "zz": "Exterior",
}
# Municípios acompanhados por padrão (código TSE de 5 dígitos).
MUNICIPIOS_PADRAO = {"ce13897": "Fortaleza", "ap06050": "Macapá"}
# UFs com 2º turno para governador em 25/10/2026, segundo a imprensa oficial
# (Agência Brasil) e a lista do TRE. A lista real é confirmada em tempo de
# execução: uma UF só aparece na interface quando o TSE publica o arquivo.
GOVERNADOR_2T_PADRAO = ("ac", "am", "df", "es", "rn", "to")
GOVERNADOR_2T_INCERTO = ("rj",)

_ESCOPO = re.compile(r"^(br|zz|[a-z]{2})([0-9]{5})?$")
_lock = threading.RLock()
_cache: dict[str, tuple[float, dict]] = {}
_em_curso: dict[str, threading.Event] = {}
_config_eleicoes: dict | None = None


def base_url() -> str:
    return os.environ.get("RADAR_TSE_BASE", BASE_PADRAO).rstrip("/")


def agora_brasilia() -> datetime:
    return datetime.now(BRASILIA)


def nome_escopo(escopo: str) -> str:
    if escopo in MUNICIPIOS_PADRAO:
        return MUNICIPIOS_PADRAO[escopo]
    if escopo in NOMES_UF:
        return NOMES_UF[escopo]
    m = _ESCOPO.match(escopo or "")
    if m and m.group(2):
        return f"Município {m.group(2)} ({m.group(1).upper()})"
    return (escopo or "").upper()


def validar_escopo(escopo: str) -> str:
    e = str(escopo or "").strip().lower()
    m = _ESCOPO.fullmatch(e)
    if not m:
        raise ValueError("Região inválida.")
    uf, mun = m.group(1), m.group(2)
    if uf not in NOMES_UF:
        raise ValueError("UF desconhecida.")
    if mun and uf in ("br", "zz"):
        raise ValueError("Município exige UF.")
    return e


def validar_cargo(cargo: str) -> str:
    c = str(cargo or "presidente").strip().lower()
    if c not in ELEICOES:
        raise ValueError("Cargo inválido.")
    return c


def codigo_eleicao(cargo: str, turno: int) -> int:
    info = ELEICOES[validar_cargo(cargo)]
    return int(info["turno2"] if int(turno) == 2 else info["turno1"])


def url_resultado(escopo: str, cargo: str = "presidente", turno: int = 2) -> str:
    escopo = validar_escopo(escopo)
    cargo = validar_cargo(cargo)
    if cargo == "governador" and escopo in ("br", "zz"):
        raise ValueError("Governador exige uma UF.")
    ele = codigo_eleicao(cargo, turno)
    m = _ESCOPO.fullmatch(escopo)
    uf, mun = m.group(1), m.group(2) or ""
    arquivo = f"{uf}{mun}-c{ELEICOES[cargo]['cargo']}-e{ele:06d}-u.json"
    return f"{base_url()}/{CICLO}/{ele}/dados/{uf}/{arquivo}"


def url_config_eleicoes() -> str:
    return f"{base_url()}/comum/config/ele-c.json"


def url_municipios(cargo: str = "presidente", turno: int = 2) -> str:
    ele = codigo_eleicao(cargo, turno)
    return f"{base_url()}/{CICLO}/{ele}/config/mun-e{ele:06d}-cm.json"


class TSEIndisponivel(RuntimeError):
    """O TSE não respondeu, respondeu com erro HTTP ou com formato inesperado."""

    def __init__(self, mensagem: str, http: int | None = None, categoria: str = "rede"):
        super().__init__(mensagem)
        self.http = http
        self.categoria = categoria


def _baixar(url: str, timeout: int = TIMEOUT) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json", "Cache-Control": "no-cache",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = resp.read(LIMITE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise TSEIndisponivel("O TSE ainda não publicou este arquivo (HTTP 404).", 404, "sem_dados")
        if exc.code == 403:
            raise TSEIndisponivel("O TSE recusou a consulta (HTTP 403).", 403, "recusado")
        raise TSEIndisponivel(f"O TSE respondeu HTTP {exc.code}.", exc.code, "http")
    except urllib.error.URLError as exc:
        raise TSEIndisponivel("Sem conexão com o TSE: " + str(getattr(exc, "reason", exc))[:80], None, "rede")
    except (TimeoutError, OSError) as exc:
        raise TSEIndisponivel("O TSE demorou para responder.", None, "rede")
    if len(dados) > LIMITE_BYTES:
        raise TSEIndisponivel("Arquivo do TSE maior que o limite seguro.", None, "formato")
    try:
        decodificado = json.loads(dados)
    except ValueError:
        raise TSEIndisponivel("O TSE devolveu um conteúdo que não é JSON.", None, "formato")
    if not isinstance(decodificado, dict):
        raise TSEIndisponivel("Formato inesperado do TSE.", None, "formato")
    return decodificado


def baixar_json(url: str, ttl: float = TTL_SEGUNDOS, timeout: int = TIMEOUT) -> dict:
    """Baixa com cache curto e coalescência: várias threads pedindo a mesma URL
    disparam uma única requisição ao TSE."""
    agora = time.monotonic()
    with _lock:
        hit = _cache.get(url)
        if hit and agora - hit[0] < ttl:
            return hit[1]
        evento = _em_curso.get(url)
        if evento is None:
            evento = threading.Event()
            _em_curso[url] = evento
            lider = True
        else:
            lider = False
    if not lider:
        evento.wait(timeout + 2)
        with _lock:
            hit = _cache.get(url)
        if hit:
            return hit[1]
        raise TSEIndisponivel("Consulta anterior ao TSE falhou.", None, "rede")
    try:
        dados = _baixar(url, timeout)
        with _lock:
            _cache[url] = (time.monotonic(), dados)
        return dados
    finally:
        with _lock:
            _em_curso.pop(url, None)
            evento.set()


def limpar_cache() -> None:
    with _lock:
        _cache.clear()


# ---------------------------------------------------------------- normalização

def numero(valor) -> float:
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    try:
        if "," in s:
            return float(s.replace(".", "").replace(",", "."))
        if s.count(".") == 1 and len(s.split(".")[1]) != 3:
            return float(s)
        return float(s.replace(".", ""))
    except ValueError:
        return 0.0


def inteiro(valor) -> int:
    return int(round(numero(valor)))


def percentual(valor) -> float:
    return round(numero(valor), 2)


def _horario(dados: dict) -> tuple[str, str]:
    """(horário da totalização, horário de geração do arquivo), em 'dd/mm/aaaa hh:mm:ss'."""
    tot = (str(dados.get("dt") or "") + " " + str(dados.get("ht") or "")).strip()
    ger = (str(dados.get("dg") or "") + " " + str(dados.get("hg") or "")).strip()
    return (tot or ger, ger or tot)


def horario_para_datetime(texto: str) -> datetime | None:
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?", texto or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), int(m.group(4)),
                        int(m.group(5)), int(m.group(6) or 0), tzinfo=BRASILIA)
    except ValueError:
        return None


def normalizar(dados: dict, escopo: str, cargo: str = "presidente", turno: int = 2,
               fonte: str | None = None) -> dict:
    """Converte o JSON EA20 do TSE em um snapshot com nomes legíveis.

    Mantém apenas valores publicados; nada é estimado.
    """
    if not isinstance(dados, dict) or not isinstance(dados.get("carg"), list) or not dados["carg"]:
        raise TSEIndisponivel("Resposta do TSE sem bloco de cargo (carg).", None, "formato")
    bloco = dados["carg"][0]
    candidatos = []
    for agr in bloco.get("agr") or []:
        for par in agr.get("par") or []:
            for cand in par.get("cand") or []:
                nome_urna = str(cand.get("nmu") or cand.get("nm") or "").strip()
                candidatos.append({
                    "numero": str(cand.get("n") or "").strip(),
                    "nome": nome_urna[:80],
                    "nome_completo": str(cand.get("nm") or nome_urna)[:120],
                    "partido": str(par.get("sg") or "")[:30],
                    "votos": inteiro(cand.get("vap")),
                    "percentual": percentual(cand.get("pvapn") if cand.get("pvapn") not in (None, "") else cand.get("pvap")),
                    "situacao": str(cand.get("st") or "")[:60],
                    "eleito": str(cand.get("e") or "").lower() == "s",
                    "sequencial": str(cand.get("sqcand") or "")[:20],
                    "destino_voto": str(cand.get("dvt") or "")[:30],
                })
    candidatos.sort(key=lambda c: (-c["votos"], c["numero"]))
    s = dados.get("s") or {}
    v = dados.get("v") or {}
    e = dados.get("e") or {}
    horario_tot, horario_ger = _horario(dados)
    turno_arquivo = str(dados.get("t") or "").strip()
    snapshot = {
        "escopo": escopo, "nome_escopo": nome_escopo(escopo),
        "cargo": validar_cargo(cargo), "cargo_nome": ELEICOES[validar_cargo(cargo)]["nome"],
        "turno": int(turno), "turno_arquivo": turno_arquivo,
        "eleicao": str(dados.get("ele") or codigo_eleicao(cargo, turno)),
        "abrangencia_tse": str(dados.get("cdabr") or "").lower(),
        "horario_tse": horario_tot, "horario_geracao_tse": horario_ger,
        "consulta_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "secoes_pct": percentual(s.get("pstn") if s.get("pstn") not in (None, "") else s.get("pst")),
        "secoes_totalizadas": inteiro(s.get("st")), "secoes_total": inteiro(s.get("ts")),
        "secoes_nao_totalizadas": inteiro(s.get("snt")) if s.get("snt") not in (None, "") else None,
        "votos_validos": inteiro(v.get("vv")), "votos_validos_pct": percentual(v.get("pvv")),
        "brancos": inteiro(v.get("vb")), "brancos_pct": percentual(v.get("pvb")),
        "nulos": inteiro(v.get("tvn") if v.get("tvn") not in (None, "") else v.get("vn")),
        "nulos_pct": percentual(v.get("ptvn") if v.get("ptvn") not in (None, "") else v.get("pvn")),
        "total_votos": inteiro(v.get("tv")),
        "eleitorado": inteiro(e.get("te")), "eleitorado_secoes_totalizadas": inteiro(e.get("est")),
        "comparecimento": inteiro(e.get("c")), "comparecimento_pct": percentual(e.get("pc")),
        "abstencao": inteiro(e.get("a")), "abstencao_pct": percentual(e.get("pa")),
        "totalizacao_final": str(dados.get("tf") or "").lower() == "s",
        "matematicamente_definido": str(dados.get("md") or "").lower() == "s",
        "candidatos": candidatos,
        "fonte": fonte or "",
    }
    snapshot["status_oficial"] = status_oficial(snapshot)
    return snapshot


def status_oficial(snapshot: dict) -> str:
    if snapshot.get("totalizacao_final"):
        return "Totalização encerrada pelo TSE"
    if snapshot.get("secoes_totalizadas", 0) == 0:
        return "Nenhuma seção totalizada"
    if snapshot.get("secoes_pct", 0) >= 100:
        return "Todas as seções totalizadas; aguardando encerramento oficial"
    return "Totalização parcial em andamento"


def classificar_atualidade(snapshot: dict, agora: datetime | None = None) -> dict:
    """Decide se o boletim pode ser chamado de 'ao vivo' ou é histórico."""
    agora = agora or agora_brasilia()
    momento = horario_para_datetime(snapshot.get("horario_tse", ""))
    if snapshot.get("totalizacao_final"):
        return {"estado": "encerrada", "rotulo": "Totalização encerrada", "ao_vivo": False, "idade_min": None}
    if momento is None:
        return {"estado": "indefinida", "rotulo": "Horário do TSE indisponível", "ao_vivo": False, "idade_min": None}
    idade = int((agora - momento).total_seconds() // 60)
    if idade < 0:
        idade = 0
    if momento.date() != agora.date() and idade > 24 * 60:
        return {"estado": "historica", "rotulo": "Dados históricos", "ao_vivo": False, "idade_min": idade}
    if idade <= 15:
        return {"estado": "ao_vivo", "rotulo": "AO VIVO", "ao_vivo": True, "idade_min": idade}
    return {"estado": "estavel", "rotulo": f"Boletim há {idade} min", "ao_vivo": False, "idade_min": idade}


def obter(escopo: str, cargo: str = "presidente", turno: int = 2, ttl: float = TTL_SEGUNDOS) -> dict:
    """Baixa e normaliza um resultado oficial. Lança TSEIndisponivel em falhas."""
    url = url_resultado(escopo, cargo, turno)
    dados = baixar_json(url, ttl=ttl if turno == 2 else 6 * 3600)
    snap = normalizar(dados, validar_escopo(escopo), cargo, turno, fonte=url)
    if snap["turno_arquivo"] and snap["turno_arquivo"] != str(turno):
        raise TSEIndisponivel("O arquivo do TSE não corresponde ao turno solicitado.", None, "formato")
    return snap


# ------------------------------------------------------------- configuração TSE

def descobrir_eleicoes(forcar: bool = False) -> dict:
    """Lê `comum/config/ele-c.json` para confirmar os códigos usados.

    Retorna {'ok': bool, 'codigos': {...}, 'divergencias': [...], 'mensagem': str}.
    Nunca altera silenciosamente os códigos padrão sem registrar a divergência.
    """
    global _config_eleicoes
    if _config_eleicoes and not forcar:
        return _config_eleicoes
    resultado = {"ok": False, "codigos": {}, "divergencias": [], "mensagem": "", "pleitos": []}
    try:
        dados = baixar_json(url_config_eleicoes(), ttl=3600, timeout=15)
    except TSEIndisponivel as exc:
        resultado["mensagem"] = f"Configuração ele-c.json indisponível: {exc}. Códigos padrão em uso (6257/6258/6260)."
        _config_eleicoes = resultado
        return resultado
    encontrados = []

    def percorrer(obj, data_pleito=""):
        if isinstance(obj, dict):
            dp = str(obj.get("dt") or data_pleito)
            if "cd" in obj and "nm" in obj and isinstance(obj.get("nm"), str):
                encontrados.append({"cd": str(obj.get("cd")), "nm": obj["nm"], "t": str(obj.get("t") or ""),
                                    "cdt2": str(obj.get("cdt2") or ""), "dt": dp})
            for valor in obj.values():
                percorrer(valor, dp)
        elif isinstance(obj, list):
            for item in obj:
                percorrer(item, data_pleito)

    percorrer(dados)
    resultado["pleitos"] = encontrados[:40]
    for item in encontrados:
        nome = item["nm"].lower()
        federal = "federal" in nome
        estadual = "estadua" in nome
        segundo = item["t"] == "2" or "2º" in nome or "2o" in nome
        primeiro = item["t"] == "1" or "1º" in nome or "1o" in nome
        chave = None
        if federal and segundo:
            chave = ("presidente", "turno2")
        elif federal and primeiro:
            chave = ("presidente", "turno1")
        elif estadual and segundo:
            chave = ("governador", "turno2")
        elif estadual and primeiro:
            chave = ("governador", "turno1")
        if chave and item["cd"].isdigit():
            resultado["codigos"][f"{chave[0]}.{chave[1]}"] = int(item["cd"])
            atual = ELEICOES[chave[0]][chave[1]]
            if int(item["cd"]) != atual:
                resultado["divergencias"].append(
                    f"{chave[0]} {chave[1]}: padrão {atual}, TSE informa {item['cd']} ({item['nm']}).")
                ELEICOES[chave[0]][chave[1]] = int(item["cd"])
            if chave == ("governador", "turno1"):
                ELEICOES["governador"]["turno1_verificado"] = True
    resultado["ok"] = bool(resultado["codigos"])
    resultado["mensagem"] = ("Códigos confirmados pelo TSE." if resultado["ok"]
                             else "ele-c.json lido, mas sem eleições reconhecidas; códigos padrão mantidos.")
    _config_eleicoes = resultado
    return resultado


def ufs_governador_2t(verificar: bool = False) -> dict:
    """Lista de UFs com 2º turno para governador.

    Com `verificar=True` consulta o TSE para cada UF candidata e devolve apenas
    as que têm arquivo publicado (o restante vai para 'sem_arquivo').
    """
    candidatas = list(GOVERNADOR_2T_PADRAO) + list(GOVERNADOR_2T_INCERTO)
    if not verificar:
        return {"confirmadas": [], "padrao": list(GOVERNADOR_2T_PADRAO), "incertas": list(GOVERNADOR_2T_INCERTO),
                "sem_arquivo": [], "verificado": False}
    confirmadas, sem_arquivo = [], []
    for uf in candidatas:
        try:
            obter(uf, "governador", 2, ttl=300)
            confirmadas.append(uf)
        except TSEIndisponivel as exc:
            sem_arquivo.append({"uf": uf, "motivo": str(exc)})
    return {"confirmadas": confirmadas, "padrao": list(GOVERNADOR_2T_PADRAO),
            "incertas": list(GOVERNADOR_2T_INCERTO), "sem_arquivo": sem_arquivo, "verificado": True}


def municipios(uf: str, cargo: str = "presidente", turno: int = 2) -> list[dict]:
    """Municípios de uma UF segundo o arquivo de configuração do TSE.

    Formato esperado (EA11): {"abr":[{"cd":"CE","mu":[{"cd":"13897","nm":"FORTALEZA"},...]}]}.
    Em falha, devolve só os municípios conhecidos localmente.
    """
    uf = validar_escopo(uf)
    if len(uf) != 2 or uf in ("br", "zz"):
        raise ValueError("Informe uma UF.")
    locais = [{"codigo": k[2:], "nome": v, "escopo": k} for k, v in MUNICIPIOS_PADRAO.items() if k.startswith(uf)]
    try:
        dados = baixar_json(url_municipios(cargo, turno), ttl=6 * 3600, timeout=20)
    except TSEIndisponivel:
        return locais
    saida = []
    for abr in dados.get("abr") or []:
        if str(abr.get("cd") or "").lower() != uf:
            continue
        for mu in abr.get("mu") or []:
            cd = str(mu.get("cd") or "").zfill(5)
            if cd.isdigit():
                saida.append({"codigo": cd, "nome": str(mu.get("nm") or "").title(), "escopo": uf + cd})
    saida.sort(key=lambda m: m["nome"])
    return saida or locais
