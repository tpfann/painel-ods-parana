"""
Etapa 09: monitoramento continuo das fontes oficiais.

Vigia as fontes cuja URL muda a cada edicao (padrao SINISA) e checa se as
fontes com API publicaram algo novo. Nada e publicado sozinho: o script
*detecta* e *registra*; a ingestao so roda se o arquivo de flag permitir.

    python scripts/09_monitor_fontes.py            # uma verificacao
    python scripts/09_monitor_fontes.py --ingerir  # forca a ingestao (se houver novidade)

Saidas:
    data/bi/monitoramento.js   status (lido pelo painel)
    data/monitoramento.log     historico das verificacoes
    data/NOVIDADE.md           novidades detectadas (revisar e decidir)

Agendamento (Windows, a cada 6 horas):
    schtasks /create /tn "Painel ODS - monitor de fontes" /sc hourly /mo 6 ^
      /tr "<python> <repo>\\scripts\\09_monitor_fontes.py" /f
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(ROOT, "data", "bi", "monitoramento.js")
LOG = os.path.join(ROOT, "data", "monitoramento.log")
NOVIDADE = os.path.join(ROOT, "data", "NOVIDADE.md")
FLAG_AUTO = os.path.join(ROOT, "data", "monitoramento_auto.txt")

UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / monitoramento de fontes oficiais)"}
SINAISA_PAGINA = ("https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/"
                   "saneamento/sinisa/resultados-sinisa")


def agora() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def log(msg: str) -> None:
    linha = "[%s] %s" % (agora(), msg)
    print(linha)
    with io.open(LOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(linha + "\n")


def get(url: str, timeout: int = 90) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        bruto = r.read()
    if bruto[:2] == b"\x1f\x8b":          # resposta gzip
        bruto = gzip.decompress(bruto)
    return bruto.decode("utf-8", "replace")


def checar_sinisa() -> dict:
    """Descobre a edicao do SINISA publicada e compara com a registrada."""
    res = {"id": "f39", "fonte": "SINISA (Ministerio das Cidades)", "status": "ok", "detalhe": ""}
    try:
        html = get(SINAISA_PAGINA)
    except Exception as e:
        res["status"] = "sem_rede"
        res["detalhe"] = "%s: %s" % (type(e).__name__, str(e)[:80])
        return res
    links = re.findall(r'href="([^"]+\.(?:zip|xlsx))"', html, re.I)
    zip_ref = [u for u in links if re.search(r"SINISA_Resultados_Ref(\d{4})\.zip$", u, re.I)]
    if not zip_ref:
        res["status"] = "sem_edicao_identificada"
        res["detalhe"] = "a pagina nao lista mais um ZIP de resultados"
        return res
    m = re.search(r"Ref(\d{4})\.zip$", zip_ref[0], re.I)
    edicao = m.group(1)
    with io.open(os.path.join(ROOT, "data", "fontes.csv"), encoding="utf-8-sig", newline="") as fh:
        import csv
        linhas = list(csv.DictReader(fh, delimiter=";"))
    atual = next((l for l in linhas if l["id"] == "f39"), None)
    registrada = (atual or {}).get("edicao_fonte", "")[:4]
    res["edicao_publicada"] = edicao
    res["edicao_registrada"] = registrada
    res["url"] = zip_ref[0]
    if registrada and registrada != edicao:
        res["status"] = "nova_edicao"
        res["detalhe"] = ("a edicao %s ja esta publicada (registrada: %s). Nova URL: %s"
                          % (edicao, registrada, zip_ref[0]))
    else:
        res["status"] = "em_dia"
        res["detalhe"] = "edicao %s" % edicao
    return res


def checar_ibge_populacao() -> dict:
    """Verifica se o IBGE publicou estimativas de populacao mais recentes."""
    res = {"id": "ibge_estimativas", "fonte": "IBGE (estimativas de populacao)", "status": "ok", "detalhe": ""}
    try:
        j = json.loads(get("https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos"))
        anos = sorted(int(p["id"]) for p in j)
        res["detalhe"] = "estimativas ate %d" % anos[-1]
        res["ano_max"] = anos[-1]
    except Exception as e:
        res["status"] = "sem_rede"
        res["detalhe"] = "%s: %s" % (type(e).__name__, str(e)[:70])
    return res


def checar_idsc() -> dict:
    """Confere a edicao do IDSC (sem regravar o payload de 20 MB toda hora)."""
    res = {"id": "idsc", "fonte": "IDSC-BR (referencia de convergencia)", "status": "ok", "detalhe": ""}
    cache = os.path.join(ROOT, "data", "cache", "idsc_payload.json")
    try:
        if os.path.exists(cache) and (datetime.datetime.now().timestamp()
                                      - os.path.getmtime(cache)) < 6 * 86400:
            with open(cache, "rb") as fh:
                j = json.loads(fh.read().decode("utf-8"))
            ed = str(j["base"]["meta"].get("edicao", "?"))
            res["detalhe"] = "edicao %s (cache local)" % ed
            res["edicao"] = ed
        else:
            res["status"] = "cache_desatualizado"
            res["detalhe"] = "cache do IDSC com mais de 6 dias (rode 08 com --atualizar)"
    except Exception as e:
        res["status"] = "erro"
        res["detalhe"] = "%s: %s" % (type(e).__name__, str(e)[:70])
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingerir", action="store_true",
                    help="roda a ingestao (SINISA) se houver edicao nova")
    args = ap.parse_args()

    log("verificacao iniciada")
    fontes = [checar_sinisa(), checar_ibge_populacao(), checar_idsc()]
    novidades = [f for f in fontes if f["status"] == "nova_edicao"]

    # ingestao automatica (opt-in pela flag)
    ingerido = None
    if novidades and args.ingerir and os.path.exists(FLAG_AUTO):
        try:
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "06_fetch_sinisa.py"), "--baixar"],
                           check=True, timeout=1800)
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "07_build_sinisa.py")],
                           check=True, timeout=1800)
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "03_build_bi.py")],
                           check=True, timeout=1800)
            ingerido = "SINISA ingerido e payload regerado (revise e commit)"
            log(ingerido)
        except Exception as e:
            ingerido = "falha na ingestao: %s: %s" % (type(e).__name__, str(e)[:120])
            log(ingerido)
    elif novidades:
        log("novidade detectada (sem ingestao automatica: flag ausente ou --ingerir nao usado)")

    # saidas
    with io.open(SAIDA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Monitoramento das fontes oficiais — gerado por scripts/09_monitor_fontes.py */\n")
        fh.write("BI.monitoramento=")
        json.dump({
            "verificado_em": agora(),
            "fontes": fontes,
            "novidades": [f.get("detalhe") for f in novidades],
            "ingerido": ingerido,
        }, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")

    if novidades:
        L = ["# Novidade nas fontes oficiais", "",
             "> Detectado em %s pelo monitor automático." % agora(), ""]
        for f in novidades:
            L.append("## %s" % f["fonte"])
            L.append("")
            L.append(f["detalhe"])
            L.append("")
        L.append("## O que fazer")
        L.append("")
        L.append("```bash")
        L.append("python scripts/09_monitor_fontes.py --ingerir")
        L.append("python scripts/02_gen_schema.py")
        L.append("```")
        L.append("")
        with io.open(NOVIDADE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(L) + "\n")
    elif os.path.exists(NOVIDADE):
        os.remove(NOVIDADE)

    for f in fontes:
        log("  %-42s %s" % (f["fonte"][:42], f["status"] + (" — " + f["detalhe"][:70] if f["detalhe"] else "")))
    log("verificacao concluida (%d novidade(s))" % len(novidades))


if __name__ == "__main__":
    main()
