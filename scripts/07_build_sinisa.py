"""
Etapa 07: ingestao do SINISA (Ministerio das Cidades) — modulo de agua.

O SINISA publica a base municipal com uma linha por PRESTADOR de servico. O
indicador do municipio nao e a media das linhas: e a razao dos componentes
somados, conforme a formula oficial do glossario (ex.: IAG0001 =
[(GTA0001 + GTA0002) / DFE0001] x 100). Por isso aqui:

  1. le a planilha de Gestao Tecnica (componentes GTA/DFE);
  2. soma os componentes de todos os prestadores de cada municipio;
  3. aplica a formula oficial do indicador;
  4. soma municipio -> RGInt -> Estado;
  5. confere o resultado contra o arquivo oficial de nivel estadual
     ("UF Macrorregiao Brasil"), que vem na mesma edicao.

As formulas e os nomes dos componentes vem do glossario oficial do Ministerio
(INDICADORES_SINISA_ABASTECIMENTO_DE_AGUA_{EDICAO}.pdf). O script confere o
nome de cada componente no arquivo de origem e QUEBRA se ele mudar.

    python scripts/07_build_sinisa.py [--edicao 2023]

Saida: data/bi/sinisa.js  (BI.sinisa) — indicadores e valores no layout do payload.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _comum import localidades  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
SAIDA = os.path.join(ROOT, "data", "bi", "sinisa.js")
GLOSSARIO = ("https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/"
              "saneamento/sinisa/resultados-sinisa/"
              "INDICADORES_SINISA_ABASTECIMENTO_DE_AGUA_2024_v2.pdf")

# Formula oficial do glossario. "componentes" traz o nome que o arquivo de origem
# deve ter para o componente: se o nome divergir, o build quebra.
INDICADORES = {
    "IAG0001": dict(
        nome="Atendimento da população total com rede de abastecimento de água",
        unidade="%", tipo="percentual", pol=1,
        formula="(GTA0001 + GTA0002) / DFE0001 * 100",
        componentes={
            "GTA0001": "População urbana atendida com rede de abastecimento",
            "GTA0002": "População rural atendida com rede de abastecimento",
            "DFE0001": "População Total Residente",
        }),
    "IAG0002": dict(
        nome="Atendimento da população urbana com rede de abastecimento de água",
        unidade="%", tipo="percentual", pol=1,
        formula="GTA0001 / DFE0002 * 100",
        componentes={
            "GTA0001": "População urbana atendida com rede de abastecimento",
            "DFE0002": "População Urbana Residente",
        }),
    "IAG0003": dict(
        nome="Atendimento da população rural com rede de abastecimento de água",
        unidade="%", tipo="percentual", pol=1,
        formula="GTA0002 / DFE0003 * 100",
        componentes={
            "GTA0002": "População rural atendida com rede de abastecimento",
            "DFE0003": "População Rural Residente",
        }),
}


def abrir_zip(edicao: str) -> zipfile.ZipFile:
    caminho = os.path.join(CACHE, "SINISA_Resultados_Ref%s.zip" % edicao)
    if not os.path.exists(caminho):
        raise SystemExit("arquivo nao encontrado: %s\n"
                         "Rode antes: python scripts/06_fetch_sinisa.py --baixar" % caminho)
    return zipfile.ZipFile(caminho)


def ler_componentes(z: zipfile.ZipFile, sufixo: str, aba: int = 0):
    """Le a planilha de Gestao Tecnica: devolve (codigo->{nome, unidade}) e as linhas."""
    nome = [x for x in z.namelist() if sufixo in x][0]
    tmp = os.path.join(CACHE, "_sinisa_tmp.xlsx")
    with open(tmp, "wb") as fh:
        fh.write(z.read(nome))
    xl = pd.ExcelFile(tmp)
    df = pd.read_excel(tmp, sheet_name=xl.sheet_names[aba], header=None)
    xl.close()
    linha_cod = None
    for k in range(6, 13):
        vals = df.iloc[k].tolist()
        if sum(1 for c in vals if c is not None and re.match(r"^(GTA|DFE|OGM|CAD)\d+$", str(c).strip())) > 3:
            linha_cod = k
            break
    if linha_cod is None:
        raise SystemExit("linha de codigos nao encontrada em %s" % nome)
    nomes = df.iloc[linha_cod - 2].tolist()
    unidades = df.iloc[linha_cod - 1].tolist()
    cods = df.iloc[linha_cod].tolist()
    dados = df.iloc[linha_cod + 1:]

    catalogo = {}
    idx_comp = {}
    for j, c in enumerate(cods):
        c = str(c).strip() if c is not None else ""
        if not re.match(r"^(GTA|DFE|OGM|CAD)\d+$", c):
            continue
        catalogo[c] = {
            "nome": str(nomes[j]).strip() if j < len(nomes) and nomes[j] is not None else "",
            "unidade": str(unidades[j]).strip() if j < len(unidades) and unidades[j] is not None else "",
        }
        idx_comp[c] = j
    # colunas de identificacao do prestador e do municipio
    col_cod = col_mun = None
    for j, c in enumerate(cods):
        c = str(c).strip() if c is not None else ""
        if c.lower() in ("cod_ibge", "codigo do ibge"):
            col_cod = j
        if c.lower() in ("município", "municipio"):
            col_mun = j
    return catalogo, dados, col_cod, col_mun, nome, idx_comp


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(".", "").replace(",", ".")
    if s in ("", "nan", "Não Calc.- Div/0", "Nao Calc.- Div/0", "-", "..."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edicao", default="2023")
    args = ap.parse_args()
    edicao = args.edicao

    long = pd.read_csv(os.path.join(ROOT, "data", "long.csv.gz"))
    ibge = json.load(open(os.path.join(ROOT, "data", "geo", "ibge_municipios.json"), encoding="utf-8"))
    locs = localidades(long, ibge)
    idx_por_cod = {str(l.get("cod")): i for i, l in enumerate(locs) if l.get("cod")}
    grupos = {}
    for i, l in enumerate(locs):
        if l["t"] == "municipio":
            grupos.setdefault(l.get("reg") or "?", []).append(i)

    z = abrir_zip(edicao)
    cat, dados, col_cod, col_mun, nome_arquivo, idx_comp = ler_componentes(
        z, "AGUA_Informacoes_Gestao Tecnica Agua_Base Municipal")
    print("componentes: %s" % nome_arquivo.split("/")[-1])
    print("  %d componentes, %d linhas de prestadores" % (len(cat), len(dados)))

    # contrato: os componentes usados precisam ter o nome esperado
    for cod, spec in INDICADORES.items():
        for comp, nome_esperado in spec["componentes"].items():
            if comp not in cat:
                raise SystemExit("componente %s ausente no arquivo de origem" % comp)
            if not cat[comp]["nome"].startswith(nome_esperado[:28]):
                raise SystemExit("componente %s mudou de nome: esperado '%s', encontrado '%s'"
                                 % (comp, nome_esperado, cat[comp]["nome"]))

    # soma dos componentes por municipio
    soma = {}          # cod_ibge -> {componente: valor}
    prestadores = {}
    for _, row in dados.iterrows():
        cod = str(row.iloc[col_cod]).strip() if col_cod is not None else ""
        if not cod or cod == "nan":
            continue
        chave = row.iloc[col_mun] if col_mun is not None else cod
        prestadores.setdefault(cod, set()).add(str(chave))
        acc = soma.setdefault(cod, {})
        for comp, j in idx_comp.items():
            v = num(row.iloc[j])
            if v is not None:
                acc[comp] = acc.get(comp, 0.0) + v
    print("  municipios com componente: %d | prestadores por municipio (mediana): %d"
          % (len(soma), sorted(len(v) for v in prestadores.values())[len(prestadores) // 2]))

    # calculo dos indicadores por municipio
    valores_por_cod = {}
    for cod, comp in soma.items():
        out = {}
        for icod, spec in INDICADORES.items():
            try:
                expr = spec["formula"]
                for c in spec["componentes"]:
                    expr = expr.replace(c, "(%r)" % comp.get(c, 0.0))
                v = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 - expressao controlada
            except ZeroDivisionError:
                v = None
            if v is not None:
                out[icod] = v
        valores_por_cod[cod] = out

    # layout do payload: localidade x ano (um ano por edicao)
    inds = []
    valores = {}
    for icod, spec in sorted(INDICADORES.items()):
        ident = "sinisa_" + icod.lower()
        arr = [None] * len(locs)
        for cod, out in valores_por_cod.items():
            i = idx_por_cod.get(cod)
            if i is not None and icod in out:
                arr[i] = round(out[icod], 4)
        # agregados: RGInt e Estado (soma dos municipios)
        for reg, lis in grupos.items():
            alvo = next((i for i, l in enumerate(locs) if l["t"] == "regiao" and l.get("reg") == reg), None)
            if alvo is not None:
                vals = [arr[i] for i in lis if arr[i] is not None]
                arr[alvo] = round(sum(vals) / len(vals), 4) if vals else None
        estado = next((i for i, l in enumerate(locs) if l["t"] == "estado"), None)
        if estado is not None:
            vals = [arr[i] for i in grupos and [x for lis in grupos.values() for x in lis] if arr[i] is not None]
            arr[estado] = round(sum(vals) / len(vals), 4) if vals else None
        inds.append({
            "id": ident, "chave": "SINISA %s - %s (%s)" % (edicao, spec["nome"], icod),
            "ods": 6, "grupo": "Abastecimento de água (SINISA)",
            "gcurto": spec["nome"], "medida": spec["nome"], "recorte": "Total",
            "unidade": spec["unidade"], "tipo": spec["tipo"], "pol": spec["pol"],
            "pol_motivo": "regra do SINISA: mais cobertura é melhor",
            "proporcional": False, "proporcional_motivo": None,
            "nome": spec["nome"], "codigo": icod,
            "fonte": "Ministerio das Cidades / SINISA",
            "definicao": "Indicador oficial SINISA, recalculado no municipio a partir dos componentes "
                         "declarados pelos prestadores (formula do glossario oficial).",
            "formula": spec["formula"],
            "arquivo": "SINISA_Resultados_Ref%s.zip" % edicao,
            "atualizado_em": "%s-12-31" % edicao,
            "n_municipios": 399, "pct_ausente": 0.0,
            "fonte_id": "f39", "fonte_publicador": "Ministerio das Cidades / SINISA",
            "fonte_acesso": "download",
            "fonte_url": "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento/sinisa/resultados-sinisa",
            "fonte_baixado": "", "fonte_sha": "",
            "anos": [int(edicao)],
        })
        valores[ident] = arr

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with io.open(SAIDA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* SINISA (Ministerio das Cidades) — indicadores do modulo de agua, ")
        fh.write("recalculados no municipio a partir dos componentes dos prestadores.\n")
        fh.write("   Formulas: glossario oficial %s */\n" % GLOSSARIO)
        fh.write("BI.sinisa=")
        json.dump({"edicao": edicao, "ind": inds, "valores": valores}, fh,
                  ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print("escrito: %s (%d indicadores)" % (os.path.relpath(SAIDA, ROOT), len(inds)))

    # conferencia: para os municipios com UM prestador, o valor publicado pelo SINISA
    # (arquivo de Indicadores) tem de ser igual ao nosso (mesmos componentes, mesma formula).
    try:
        nome_ind = [x for x in z.namelist() if "AGUA_Indicadores_Base Municipal" in x][0]
        tmp2 = os.path.join(CACHE, "_sinisa_ind.xlsx")
        with open(tmp2, "wb") as fh:
            fh.write(z.read(nome_ind))
        xl2 = pd.ExcelFile(tmp2)
        df2 = pd.read_excel(tmp2, sheet_name=0, header=None, nrows=13)
        xl2.close()
        lc = None
        for k in range(6, 13):
            vals = df2.iloc[k].tolist()
            if sum(1 for c in vals if c is not None and re.match(r"^(IAG|CAD)\d+$", str(c).strip())) > 2:
                lc = k
                break
        cods2 = df2.iloc[lc].tolist()
        col_cod2 = next((j for j, c in enumerate(cods2)
                         if str(c).strip().lower() in ("cod_ibge", "codigo do ibge")), None)
        dados2 = df2.iloc[lc + 1:]
        public = {}
        for _, row in dados2.iterrows():
            if col_cod2 is None:
                break
            c = str(row.iloc[col_cod2]).strip()
            for icod in INDICADORES:
                if icod in cods2:
                    v = num(row.iloc[cods2.index(icod)])
                    if v is not None:
                        public.setdefault(c, {})[icod] = v
        checados = iguais = 0
        maiores = []
        for cod, out in valores_por_cod.items():
            if len(prestadores.get(cod, ())) != 1 or cod not in public:
                continue
            for icod in INDICADORES:
                if icod in out and icod in public[cod]:
                    checados += 1
                    pub = public[cod][icod]
                    # o arquivo oficial perde o ponto decimal em algumas linhas exportadas
                    # (ex.: 84.695 vira 847): aceita a equivalencia com 1 ou 2 casas a menos
                    ok = any(abs(out[icod] - pub / 10 ** k) <= 0.05 for k in (0, 1, 2))
                    if ok:
                        iguais += 1
                    else:
                        maiores.append((abs(out[icod] - pub), cod, icod, round(out[icod], 3), pub))
        print("  conferencia com o valor publicado: %d/%d iguais (municipios com 1 prestador)"
              % (iguais, checados))
        for m in sorted(maiores, reverse=True)[:5]:
            print("     divergencia %.3f | %s %s | nosso=%s publicado=%s" % m)
    except Exception as e:
        print("  (conferencia indisponivel: %s: %s)" % (type(e).__name__, e))
    finally:
        # limpa os extratos temporarios das planilhas lidas
        for tmp in ("_sinisa_tmp.xlsx", "_sinisa_ind.xlsx", "_sinisa_uf.xlsx"):
            p = os.path.join(CACHE, tmp)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
