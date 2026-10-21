"""Gera data/bi/populacao.js com a populacao residente por localidade e ano.

Fontes (API de agregados do IBGE):
  - 6579 / variavel 9324 -> "Populacao residente estimada" (2001..2026, anos esparsos)
  - 4714 / variavel 93   -> "Populacao residente" do Censo 2022

Anos ausentes nas duas fontes entram por interpolacao linear entre os vizinhos
(2007, 2010, 2023). O Estado e as RGInt sao a soma dos municipios que os compoem.

Saida: BI.pop = { anos:[...], valores:[...] } na mesma ordem de BI.indice.localidades,
com valores achatados por [localidade * n_anos + ano].
"""
import io
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDICE = os.path.join(ROOT, "data", "bi", "indice.js")
SAIDA = os.path.join(ROOT, "data", "bi", "populacao.js")

API = "https://servicodados.ibge.gov.br/api/v3/agregados/{ag}/periodos/{per}/variaveis/{var}?localidades=N6[N3[41]]"
UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / ETL)"}


def baixar(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        bruto = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or bruto[:2] == b"\x1f\x8b":
            import gzip
            bruto = gzip.decompress(bruto)
        return json.loads(bruto.decode("utf-8"))


def serie_municipios(ag: int, per: str, var: int) -> dict:
    """{codigo_ibge: {ano: populacao}}"""
    dados = baixar(API.format(ag=ag, per=per, var=var))
    out = {}
    for resultado in dados:
        for bloco in resultado["resultados"]:
            for s in bloco["series"]:
                cod = s["localidade"]["id"]
                ano_vals = {int(a): float(v) for a, v in s["serie"].items() if v not in ("", "-", "...", None)}
                out.setdefault(cod, {}).update(ano_vals)
    return out


def completa(serie: dict, anos: list) -> list:
    """Preenche anos faltantes por interpolacao linear entre vizinhos."""
    conhecidos = sorted(serie)
    if not conhecidos:
        return [None] * len(anos)
    vals = []
    for a in anos:
        if a in serie:
            vals.append(serie[a])
            continue
        anteriores = [k for k in conhecidos if k < a]
        posteriores = [k for k in conhecidos if k > a]
        if anteriores and posteriores:
            a0, a1 = anteriores[-1], posteriores[0]
            v0, v1 = serie[a0], serie[a1]
            vals.append(v0 + (v1 - v0) * (a - a0) / (a1 - a0))
        elif anteriores:
            vals.append(serie[anteriores[-1]])
        else:
            vals.append(serie[posteriores[0]])
    return [round(v) if v is not None else None for v in vals]


def main() -> None:
    with io.open(INDICE, encoding="utf-8") as fh:
        txt = fh.read()
    ini = txt.index("BI.indice=") + len("BI.indice=")
    loc = json.loads(txt[ini:].rstrip().rstrip(";"))["localidades"]

    estim = serie_municipios(6579, "2001-2026", 9324)
    censo = serie_municipios(4714, "2022", 93)
    for cod, s in censo.items():
        estim.setdefault(cod, {}).update(s)

    anos = sorted({int(a) for s in estim.values() for a in s})
    print("anos disponiveis:", anos)
    faltando = [a for a in range(min(anos), max(anos) + 1) if a not in anos]
    print("anos interpolados:", faltando)
    anos = list(range(min(anos), max(anos) + 1))

    por_cod = {cod: completa(s, anos) for cod, s in estim.items()}

    n = len(anos)
    valores = [None] * (len(loc) * n)
    municipios = [i for i, l in enumerate(loc) if l.get("t") == "municipio"]
    sem_dado = []
    for li in municipios:
        cod = str(loc[li].get("cod") or "")
        if cod not in por_cod:
            sem_dado.append(loc[li]["n"])
    print("municipios sem populacao:", len(sem_dado), sem_dado[:6])

    for li in municipios:
        cod = str(loc[li].get("cod") or "")
        v = por_cod.get(cod)
        if v:
            valores[li * n:(li + 1) * n] = v

    # agregados: soma por RGInt e Estado
    grupos = {}
    for li in municipios:
        grupos.setdefault(loc[li].get("reg") or "?", []).append(li)
    for nome, lis in grupos.items():
        alvo = next((i for i, l in enumerate(loc) if l["n"] == "RGInt de " + nome), None)
        if alvo is None:
            print("RGInt sem localidade:", nome)
            continue
        valores[alvo * n:(alvo + 1) * n] = [sum(valores[l * n + j] for l in lis) for j in range(n)]
        print("RGInt", nome, len(lis), "municipios")
    estado = next((i for i, l in enumerate(loc) if l.get("t") == "estado"), None)
    if estado is not None:
        valores[estado * n:(estado + 1) * n] = [sum(valores[l * n + j] for l in municipios) for j in range(n)]

    # checagem
    j2022 = anos.index(2022)
    soma22 = sum(valores[l * n + j2022] for l in municipios)
    print("soma dos municipios em 2022:", soma22, "(Censo 2022 PR = 11444380)")
    j2025 = anos.index(2025)
    print("soma dos municipios em 2025:", sum(valores[l * n + j2025] for l in municipios))

    with io.open(SAIDA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Populacao residente por localidade e ano (IBGE: estimativas 6579/9324, Censo 2022 4714/93).\n")
        fh.write("   Anos sem publicacao (2007, 2010, 2023) interpolados linearmente entre vizinhos.\n")
        fh.write("   Estado e RGInt = soma dos municipios. Layout: [localidade * n_anos + ano]. */\n")
        fh.write("BI.pop=")
        json.dump({"anos": anos, "valores": valores}, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print("escrito:", SAIDA, round(os.path.getsize(SAIDA) / 1024), "KB")


main()
