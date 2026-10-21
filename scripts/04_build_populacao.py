"""
Gera data/bi/populacao.js com a populacao residente por localidade e ano (IBGE).

Fontes (API de agregados do IBGE):
  - 6579 / variavel 9324 -> "Populacao residente estimada" (2001..2021, 2024..2026)
  - 4714 / variavel 93   -> "Populacao residente" do Censo 2022
  -  200 / variavel 93   -> "Populacao residente" do Censo 2010

Anos sem publicacao (2007, 2023) entram por interpolacao linear entre os vizinhos;
a base registra quais anos sao estimados/interpolados para o app poder avisar.

Estado e RGInt sao a soma dos municipios que os compoem.

Saida: BI.pop = {anos, valores} na ordem de BI.indice.localidades
       (vetor achatado por [localidade * n_anos + ano]).

Uso: python scripts/04_build_populacao.py
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comum import localidades  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(ROOT, "data", "bi", "populacao.js")

API = ("https://servicodados.ibge.gov.br/api/v3/agregados/{ag}/periodos/{per}"
       "/variaveis/{var}?localidades=N6[N3[41]]")
UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / ETL)"}

# fonte -> (agregado, periodos, variavel, rotulo)
FONTES = [
    ("estimativas", 6579, "2001-2026", 9324),
    ("censo2022", 4714, "2022", 93),
    ("censo2010", 200, "2010", 93),
]

# o censo tem precedencia sobre a estimativa quando ambos.publicam o mesmo ano
PRIORIDADE = {"estimativas": 1, "censo2022": 3, "censo2010": 3}


def baixar(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        bruto = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or bruto[:2] == b"\x1f\x8b":
            bruto = gzip.decompress(bruto)
    return json.loads(bruto.decode("utf-8"))


def serie_municipios(ag: int, per: str, var: int) -> dict:
    """{codigo_ibge: {ano: populacao}}"""
    dados = baixar(API.format(ag=ag, per=per, var=var))
    out: dict = {}
    for resultado in dados:
        for bloco in resultado["resultados"]:
            for s in bloco["series"]:
                cod = s["localidade"]["id"]
                vals = {int(a): float(v) for a, v in s["serie"].items()
                        if v not in ("", "-", "...", None)}
                out.setdefault(cod, {}).update(vals)
    return out


def completa(serie: dict, anos: list, conhecidos: set) -> list:
    """Preenche anos sem publicacao por interpolacao linear entre os vizinhos."""
    if not serie:
        return [None] * len(anos)
    vals = []
    for a in anos:
        if a in serie:
            vals.append(serie[a])
            continue
        antes = [k for k in sorted(serie) if k < a]
        depois = [k for k in sorted(serie) if k > a]
        if antes and depois:
            a0, a1 = antes[-1], depois[0]
            v0, v1 = serie[a0], serie[a1]
            vals.append(v0 + (v1 - v0) * (a - a0) / (a1 - a0))
        elif antes:
            vals.append(serie[antes[-1]])
        else:
            vals.append(serie[depois[0]])
    return [round(v) if v is not None else None for v in vals]


def main() -> None:
    long = pd.read_csv(os.path.join(ROOT, "data", "long.csv.gz"))
    ibge = json.load(open(os.path.join(ROOT, "data", "geo", "ibge_municipios.json"), encoding="utf-8"))
    locs = localidades(long, ibge)
    N = len(locs)

    series: dict = {}
    fonte_por_ponto: dict = {}
    for rotulo, ag, per, var in FONTES:
        obtidas = serie_municipios(ag, per, var)
        for cod, s in obtidas.items():
            for a, v in s.items():
                # precedencia por ponto (municipio, ano): censo > estimativa
                atual = fonte_por_ponto.get((cod, a))
                if atual is not None and PRIORIDADE.get(atual, 0) >= PRIORIDADE.get(rotulo, 0):
                    continue
                series.setdefault(cod, {})[a] = v
                fonte_por_ponto[(cod, a)] = rotulo

    # origem por ano (para o app poder avisar quando o denominador e estimado)
    origem_ano: dict = {}
    for (cod, a), rotulo in fonte_por_ponto.items():
        if a not in origem_ano or PRIORIDADE[rotulo] > PRIORIDADE[origem_ano[a]]:
            origem_ano[a] = rotulo

    anos = sorted({a for s in series.values() for a in s})
    print("anos publicados:", anos)
    faltando = [a for a in range(min(anos), max(anos) + 1) if a not in anos]
    print("anos interpolados:", faltando)
    anos = list(range(min(anos), max(anos) + 1))
    n = len(anos)

    por_cod = {cod: completa(s, anos, set(anos)) for cod, s in series.items()}

    valores = [None] * (N * n)
    municipios = [i for i, l in enumerate(locs) if l["t"] == "municipio"]
    sem_dado = [locs[i]["n"] for i in municipios if not por_cod.get(str(locs[i]["cod"]))]
    assert not sem_dado, "municipios sem populacao: %s" % sem_dado[:5]

    for i in municipios:
        cod = str(locs[i]["cod"])
        valores[i * n:(i + 1) * n] = por_cod[cod]

    # agregados: soma por RGInt e Estado
    grupos: dict = {}
    for i in municipios:
        grupos.setdefault(locs[i].get("reg") or "?", []).append(i)
    for nome, lis in grupos.items():
        alvo = next((i for i, l in enumerate(locs) if l["n"] == "RGInt de " + nome), None)
        assert alvo is not None, "RGInt sem localidade: %s" % nome
        valores[alvo * n:(alvo + 1) * n] = [sum(valores[l * n + j] for l in lis) for j in range(n)]
        print("  RGInt", nome, len(lis), "municipios")
    estado = next((i for i, l in enumerate(locs) if l["t"] == "estado"), None)
    assert estado is not None, "localidade do Estado ausente"
    valores[estado * n:(estado + 1) * n] = [sum(valores[l * n + j] for l in municipios) for j in range(n)]

    # --- checagens ---
    j2022 = anos.index(2022)
    soma22 = sum(valores[l * n + j2022] for l in municipios)
    assert soma22 == 11444380, "soma dos municipios em 2022 = %s (esperado 11444380)" % soma22
    j2025 = anos.index(2025)
    print("soma dos municipios em 2022:", soma22, "(Censo 2022 PR = 11444380)")
    print("soma dos municipios em 2025:", sum(valores[l * n + j2025] for l in municipios))

    info = {
        "fonte": "IBGE: estimativas (6579/9324), Censo 2022 (4714/93), Censo 2010 (200/93)",
        "anos": anos,
        "anos_interpolados": faltando,
        "origem_por_ano": {str(a): origem_ano.get(a, "interpolado") for a in anos},
    }

    with open(SAIDA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Populacao residente por localidade e ano (IBGE).\n")
        fh.write("   2007 e 2023 sao interpolados entre os vizinhos; 2010 e 2022 vem dos censos.\n")
        fh.write("   Estado e RGInt = soma dos municipios. Layout: [localidade * n_anos + ano]. */\n")
        fh.write("BI.pop=")
        json.dump({"anos": anos, "valores": valores, "info": info}, fh,
                  ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print("escrito:", SAIDA, round(os.path.getsize(SAIDA) / 1024), "KB")


if __name__ == "__main__":
    main()
