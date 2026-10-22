"""
Etapa 06: aquisicao das fontes cujo endereco muda todo ano (padrao SINISA).

O Ministerio das Cidades publica o SINISA com o ano no nome do arquivo
(SINISA_Resultados_Ref2023.zip, SINISA_GESTAOMUNICIPAL_Informacoes_2023.xlsx).
A URL antiga deixa de responder, mas a PAGINA DE RESULTADOS continua valida e
aponta sempre para a edicao corrente.

Este script:
  1. le a pagina de resultados e descobre a edicao publicada;
  2. compara com a edicao registrada em data/fontes.csv;
  3. se mudou, mostra o LEMBRETE com a URL nova proposta (e pode atualizar o
     registro com --aceitar);
  4. baixa o arquivo para o cache local (data/cache/) com o checksum registrado.

    python scripts/06_fetch_sinisa.py            # checa e avisa
    python scripts/06_fetch_sinisa.py --aceitar  # atualiza a URL no registro
    python scripts/06_fetch_sinisa.py --baixar   # baixa para o cache

Nao ha gravacao de dados no painel aqui: a ingestao dos indicadores do SINISA
depende do glossario oficial (que associa codigo IRS a nome e unidade) e vem na
etapa seguinte. O que esta etapa garante e a procedencia: qual edicao oficial
foi baixada, de onde e com qual checksum.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(ROOT, "data", "fontes.csv")
CACHE = os.path.join(ROOT, "data", "cache")
STATUS = os.path.join(ROOT, "data", "bi", "sinisa_status.json")

LANDING = ("https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/"
           "saneamento/sinisa/resultados-sinisa")
UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / aquisicao de fonte oficial)"}
TIMEOUT = 120

PADRAO_ZIP = re.compile(r"SINISA_Resultados_Ref(\d{4})\.zip$", re.I)
PADRAO_XLSX = re.compile(r"SINISA_GESTAOMUNICIPAL_Informacoes_(\d{4})\.xlsx$", re.I)


def baixar(url: str, destino: str = None) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        bruto = r.read()
    if destino:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as fh:
            fh.write(bruto)
    return bruto


def sha256(bruto: bytes) -> str:
    return hashlib.sha256(bruto).hexdigest()


def ler_registro() -> list:
    with io.open(REGISTRO, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def gravar_registro(linhas: list) -> None:
    with io.open(REGISTRO, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()), delimiter=";", lineterminator="\n")
        w.writeheader()
        for l in linhas:
            w.writerow(l)


def descobrir() -> dict:
    """Le a pagina de resultados e devolve a edicao publicada + os arquivos."""
    html = baixar(LANDING).decode("utf-8", "replace")
    links = re.findall(r'href="([^"]+\.(?:zip|xlsx))"', html, re.I)
    zip_ref = [u for u in links if PADRAO_ZIP.search(u)]
    xlsx_ref = [u for u in links if PADRAO_XLSX.search(u)]
    edicao = None
    for u in zip_ref + xlsx_ref:
        m = PADRAO_ZIP.search(u) or PADRAO_XLSX.search(u)
        if m:
            edicao = m.group(1)
            break
    return {
        "edicao": edicao,
        "zip": zip_ref[0] if zip_ref else None,
        "xlsx": xlsx_ref[0] if xlsx_ref else None,
        "landing": LANDING,
        "outros": [u for u in links if u not in zip_ref + xlsx_ref],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aceitar", action="store_true",
                    help="atualiza data/fontes.csv com a URL descoberta")
    ap.add_argument("--baixar", action="store_true", help="baixa o arquivo para data/cache/")
    args = ap.parse_args()

    print("consultando %s" % LANDING)
    info = descobrir()
    if not info["edicao"]:
        print("Nao foi possivel identificar a edicao publicada (a pagina mudou?).")
        print("Verifique manualmente: %s" % info["landing"])
        return

    print("edicao publicada: %s" % info["edicao"])
    if info["zip"]:
        print("  zip : %s" % info["zip"].split("/")[-1])
    if info["xlsx"]:
        print("  xlsx: %s" % info["xlsx"].split("/")[-1])

    linhas = ler_registro()
    alvo = None
    for l in linhas:
        if "SINISA" in (l.get("publicador", "") + l.get("observacao", "")).upper():
            alvo = l
            break
    if alvo is None:
        alvo = next((l for l in linhas if l["id"] == "f25"), None)  # saneamento/esgoto
    if alvo is None:
        print("Nenhuma fonte do registro referencia o SINISA.")
        return

    registrada = alvo.get("url_direta", "")
    if info["zip"] and registrada and info["zip"] not in registrada:
        print("\nLEMBRETE: a URL registrada aponta para uma edicao antiga.")
        print("  registrada : %s" % registrada.split("/")[-1])
        print("  publicada  : %s" % info["zip"].split("/")[-1])
        print("  nova URL   : %s" % info["zip"])
        print("  pagina     : %s" % info["landing"])
        if args.aceitar:
            alvo["url_direta"] = info["zip"]
            alvo["edicao_fonte"] = "%s-12-31" % info["edicao"]
            gravar_registro(linhas)
            print("  -> registro atualizado (data/fontes.csv)")
    else:
        print("URL registrada em dia.")

    sha = ""
    if args.baixar and info["zip"]:
        destino = os.path.join(CACHE, "SINISA_Resultados_Ref%s.zip" % info["edicao"])
        bruto = baixar(info["zip"], destino)
        sha = sha256(bruto)
        print("\nbaixado: %s (%.1f MB) | sha256 %s" % (destino, len(bruto) / 1e6, sha[:16]))
        try:
            z = zipfile.ZipFile(destino)
            nomes = z.namelist()
            base = [n for n in nomes if n.lower().endswith(".xlsx")]
            print("arquivos no zip: %d (%d planilhas)" % (len(nomes), len(base)))
            for n in base:
                print("   %s" % n.split("/")[-1])
        except zipfile.BadZipFile:
            print("aviso: o arquivo baixado nao e um zip valido")

    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with io.open(STATUS, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({
            "gerado_em": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "edicao": info["edicao"],
            "zip": info["zip"], "xlsx": info["xlsx"], "landing": info["landing"],
            "sha256": sha,
        }, fh, ensure_ascii=False, indent=1)
    print("status: %s" % os.path.relpath(STATUS, ROOT))


if __name__ == "__main__":
    main()
