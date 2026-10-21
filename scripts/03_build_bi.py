"""
Gera o payload do BI (JS classico, para rodar via file:// sem servidor).

Saidas em data/bi/:
  indice.js        -> BI.localidades, BI.indicadores (metadados), BI.ods
  val_odsN.js      -> BI.valores[id] = [valores...]  (matriz localidade x ano, achatada)
  mapa.js          -> BI.mapa = [{c, d}]  (path SVG por codigo IBGE)

Ordem do array achatado: idx = localidade_idx * n_anos + ano_idx
Valores ausentes = null.

Uso: python scripts/03_build_bi.py
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import OrderedDict

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bi")
os.makedirs(OUT, exist_ok=True)

CORES_ODS = {
    1: "#E5243B", 2: "#DDA63A", 3: "#4C9F38", 4: "#C5192D", 5: "#FF3A21",
    6: "#26BDE2", 7: "#FCC30B", 8: "#A21942", 9: "#FD6925", 10: "#DD1367",
    11: "#FD9D24", 12: "#BF8B2E", 13: "#3F7E44", 14: "#0A97D9", 15: "#56C02B",
    16: "#00689D", 17: "#19486A",
}
NOME_ODS = {
    1: "Erradicação da Pobreza", 2: "Fome Zero e Agricultura Sustentável",
    3: "Saúde e Bem-Estar", 4: "Educação de Qualidade", 5: "Igualdade de Gênero",
    6: "Água Potável e Saneamento", 7: "Energia Limpa e Acessível",
    8: "Trabalho Decente e Crescimento Econômico",
    9: "Indústria, Inovação e Infraestrutura", 13: "Ação Contra a Mudança Global do Clima",
    15: "Vida Terrestre", 16: "Paz, Justiça e Instituições Eficazes",
}

RECORTES = {
    "Total", "Masculino", "Feminino", "Urbano", "Urbana", "Rural",
    "Cor/Raça Branca", "Cor/Raça Preta", "Cor/Raça Amarela",
    "Cor/Raça Parda", "Cor/Raça Indígena",
}


def curto(nome: str) -> str:
    return re.sub(r"^ODS - Objetivo \d+ - ", "", nome).strip()


def split_unidade(nome: str):
    m = re.search(r"\s*\(([^()]*)\)\s*$", nome)
    if not m:
        return nome, ""
    return nome[: m.start()].strip(), m.group(1).strip()


def parse(nome: str, grupo_tema: str) -> dict:
    base, unidade = split_unidade(curto(nome))
    partes = [p.strip() for p in base.split(" - ")]
    recorte = partes[-1] if partes[-1] in RECORTES else None
    medida = " - ".join(partes[:-1]) if recorte else base

    grupo = re.sub(r"^ODS \d+ - ", "", grupo_tema or "").strip()

    if unidade == "%":
        tipo = "percentual"
    elif unidade.startswith("R$"):
        tipo = "moeda"
    elif any(k in unidade for k in ("habitantes", "nascidos vivos", "adultos", "meninas")):
        tipo = "taxa"
    else:
        tipo = "contagem"

    if tipo == "contagem" and not unidade:
        for chave, rotulo in (
            ("Óbitos", "óbitos"),
            ("Profissionais", "profissionais"),
            ("Empregos", "vínculos"),
            ("Consumidores", "consumidores"),
            ("Unidades Atendidas", "unidades"),
            ("Mortes", "pessoas"),
        ):
            if chave in nome:
                unidade = rotulo
                break

    return {
        "grupo": grupo,
        "medida": medida,
        "recorte": recorte or "Total" if recorte else None,
        "unidade": unidade,
        "tipo": tipo,
    }


def polaridade(nome: str) -> int:
    """+1 maior é melhor | -1 menor é melhor | 0 sem juízo de valor."""
    if "Casos de AIDS entre Mulheres" in nome:
        return 0  # indicador de composição/disparidade, não de volume
    if "Cobertura Vacinal" in nome:
        return 1  # mais cobertura é melhor (evita falso negativo por "Hepatite"/"Tuberculose")
    baixos = ("Mortalidade", "Óbitos", "Mortes", "Desnutrid", "Baixo Peso",
              "Homicíd", "Hepatite", "Tuberculose", "Incidência de AIDS",
              "Mães Adolescentes", "Desastres")
    return -1 if any(k in nome for k in baixos) else 1


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


# rótulos curtos por tema (chave = norm(grupo)); usados em cartões, listas e mapas
GRUPOS_CURTOS = {
    "proporcao do total das despesas publicas municipais com educacao e seguridade social":
        "Despesas com educação e seguridade social",
    "proporcao de criancas desnutridas com ate dois anos de idade": "Crianças desnutridas (até 2 anos)",
    "proporcao de nascidos vivos com baixo peso ao nascer": "Baixo peso ao nascer",
    "cobertura vacinal": "Cobertura vacinal",
    "mortalidade materna": "Mortalidade materna",
    "mortalidade neonatal": "Mortalidade neonatal",
    "mortalidade em menores de 1 ano de idade": "Mortalidade infantil (< 1 ano)",
    "mortalidade em menores de 5 anos de idade": "Mortalidade na infância (< 5 anos)",
    "numero de profissionais de saude": "Profissionais de saúde",
    "proporcao de nascidos vivos com 7 ou mais consultas pre-natal": "Pré-natal (7+ consultas)",
    "proporcao dos casos de aids entre mulheres": "Casos de AIDS entre mulheres",
    "taxa de incidencia de aids por ano de diagnostico": "Incidência de AIDS",
    "taxa de incidencia de hepatite b": "Incidência de hepatite B",
    "taxa de incidencia de tuberculose": "Incidência de tuberculose",
    "taxa de nascidos vivos de maes adolescentes": "Mães adolescentes",
    "taxas de mortalidade": "Mortalidade por causas específicas",
    "infraestrutura nas escolas": "Infraestrutura das escolas",
    "proporcao de estudantes do terceiro ano do ensino fundamental que atingiram um nivel minimo de proficiencia":
        "Proficiência — 3º ano",
    "proporcao de estudantes do ensino fundamental que atingiram um nivel minimo de proficiencia":
        "Proficiência — Ensino Fundamental",
    "proporcao de pessoas de 4 a 5 anos matriculadas na pre-escola": "Pré-escola (4–5 anos)",
    "proporcao de docencias com professores cuja formacao superior esta adequada a area de conhecimento que lecionam":
        "Formação docente adequada",
    "proporcao de cadeiras ocupadas por mulheres nas camaras de vereadores": "Cadeiras em câmaras de vereadores",
    "proporcao de mulheres em posicoes gerenciais (rais)": "Mulheres em cargos gerenciais",
    "abastecimento de agua - unidades atendidas residenciais": "Abastecimento de água",
    "atendimento de esgoto - unidades atendidas residenciais": "Atendimento de esgoto",
    "energia eletrica residencial - consumidores": "Consumidores de energia elétrica",
    "empregos (rais)": "Empregos formais (RAIS)",
    "numero de agencias bancarias e postos de atendimento eletronico (pae)": "Agências e postos bancários",
    "produto interno bruto (pib)": "Produto Interno Bruto (PIB)",
    "proporcao de empregos (rais) nas atividades caracteristicas do turismo": "Empregos no turismo",
    "rendimento nominal medio por hora": "Rendimento médio por hora",
    "valor adicionado fiscal nas atividades caracteristicas do turismo": "Valor adicionado — turismo",
    "emprego no setor de industria como percentual do emprego total": "Emprego na indústria",
    "percentual do valor adicionado bruto na industria sobre o pib": "Valor adicionado — indústria",
    "numero de mortes, pessoas desaparecidas e pessoas diretamente afetadas atribuido a desastres":
        "Afetados por desastres",
    "area de remanescente florestal como proporcao da area territorial": "Remanescente florestal",
    "proporcao de nascidos vivos que tiveram seus nascimentos registrados por uma autoridade civil":
        "Registro civil de nascimentos",
    "taxa de mortalidade por homicidios": "Homicídios",
}


def js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- dados
long = pd.read_csv(os.path.join(ROOT, "data", "long.csv.gz"))
catalogo = json.load(open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8"))
ibge = json.load(open(os.path.join(ROOT, "data", "geo", "ibge_municipios.json"), encoding="utf-8"))
geo = json.load(open(os.path.join(ROOT, "data", "geo", "pr_municipios.geojson"), encoding="utf-8"))

cod_por_nome = {norm(m["nome"]): m["cod"] for m in ibge}
reg_por_nome = {norm(m["nome"]): m["rgint"] for m in ibge}

# ordem das localidades: estado -> regioes -> municipios (alfabetico)
todos = set(long["localidade"].unique())
muns = sorted(l for l in todos if not l.startswith("RGInt") and l != "Estado do Paraná")
regs = sorted(l for l in todos if l.startswith("RGInt"))
localidades = []
for l in ["Estado do Paraná"] + regs + muns:
    if l == "Estado do Paraná":
        localidades.append({"n": l, "t": "estado"})
    elif l.startswith("RGInt"):
        localidades.append({"n": l, "t": "regiao", "reg": l.replace("RGInt de ", "")})
    else:
        localidades.append({"n": l, "t": "municipio", "cod": cod_por_nome.get(norm(l)), "reg": reg_por_nome.get(norm(l))})

idx_loc = {l["n"]: i for i, l in enumerate(localidades)}
N = len(localidades)

# ---------------------------------------------------------------- indicadores
pilhas = {l: {} for l in long["localidade"].unique()}
for r in long.itertuples(index=False):
    pilhas[r.localidade].setdefault(r.indicador, {})[int(r.ano)] = r.valor

indicadores = []
por_ods: "OrderedDict[int, list]" = OrderedDict()
for i, c in enumerate(catalogo):
    p = parse(c["indicador"], c["grupo_tema"])
    anos = sorted({int(a) for a in c["anos_com_dados"]})
    if not anos:
        continue
    meta = {
        "id": f"i{i}",
        "ods": c["ods"],
        "grupo": p["grupo"],
        "gcurto": GRUPOS_CURTOS.get(norm(p["grupo"]), p["grupo"]),
        "medida": p["medida"],
        "recorte": p["recorte"],
        "unidade": p["unidade"],
        "tipo": p["tipo"],
        "pol": polaridade(c["indicador"]),
        "nome": curto(c["indicador"]),
        "codigo": c["codigo_ods"],
        "fonte": c["fonte"],
        "definicao": c["definicao"],
        "formula": c["formula"],
        "anos": anos,
    }
    indicadores.append(meta)
    por_ods.setdefault(c["ods"], []).append((meta, anos, c["indicador"]))

# ---------------------------------------------------------------- valores
total_bytes = 0
for ods, itens in por_ods.items():
    linhas = ["window.BI=window.BI||{};window.BI.valores=window.BI.valores||{};"]
    for meta, anos, nome_original in itens:
        n_a = len(anos)
        arr = [None] * (N * n_a)
        for loc, i in idx_loc.items():
            serie = pilhas[loc].get(nome_original)
            if not serie:
                continue
            base = i * n_a
            for j, a in enumerate(anos):
                v = serie.get(a)
                if v is not None and v == v:
                    arr[base + j] = round(float(v), 3)
        linhas.append(f'BI.valores["{meta["id"]}"]={js(arr)};')
    conteudo = "\n".join(linhas)
    caminho = os.path.join(OUT, f"val_ods{ods}.js")
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(conteudo)
    total_bytes += len(conteudo.encode("utf-8"))
    print(f"  val_ods{ods}.js  {len(conteudo)/1e6:5.1f} MB  ({len(itens)} indicadores)")

print(f"  TOTAL valores: {total_bytes/1e6:.1f} MB")

# ---------------------------------------------------------------- indice
ods_meta = []
for ods in sorted(por_ods):
    its = por_ods[ods]
    grupos = list(OrderedDict.fromkeys(m["grupo"] for m, _, _ in its))
    ods_meta.append({
        "n": ods, "nome": NOME_ODS.get(ods, ""), "cor": CORES_ODS.get(ods, "#666"),
        "n_ind": len(its), "grupos": grupos,
    })

indice = {
    "gerado": pd.Timestamp.now().strftime("%Y-%m-%d"),
    "fonte_estado": "Paraná",
    "localidades": localidades,
    "indicadores": indicadores,
    "ods": ods_meta,
}
with open(os.path.join(OUT, "indice.js"), "w", encoding="utf-8") as fh:
    fh.write("window.BI=window.BI||{};BI.indice=" + js(indice) + ";")
print(f"  indice.js        {os.path.getsize(os.path.join(OUT,'indice.js'))/1e6:5.2f} MB")

# ---------------------------------------------------------------- mapa
def projetar(lon, lat):
    # equiretangular simples, ajustado para o PR
    x = (lon + 54.3) * 1.0
    y = (22.5 - lat) * 1.0
    return x, y


paths = []
for feat in geo["features"]:
    cod = feat["properties"]["codarea"]
    g = feat["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    d = []
    for poly in polys:
        for ring in poly:
            pts = []
            for lon, lat in ring:
                x, y = projetar(lon, lat)
                pts.append(f"{x:.3f},{y:.3f}")
            if pts:
                d.append("M" + "L".join(pts) + "Z")
    paths.append({"c": cod, "d": "".join(d)})

xs, ys = [], []
for p in paths:
    for par in p["d"].replace("M", "").replace("Z", "").split("L"):
        if "," in par:
            a, b = par.split(",")
            xs.append(float(a)); ys.append(float(b))
x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
# normaliza para viewBox 0 0 1000 x h
k = 1000 / (x1 - x0)
h = round((y1 - y0) * k, 1)
for p in paths:
    novo = []
    for seg in p["d"].split("Z"):
        if not seg:
            continue
        pts = seg.replace("M", "").split("L")
        novo.append("M" + "L".join(
            f"{(float(a)-x0)*k:.1f},{(float(b)-y0)*k:.1f}" for a, b in (q.split(",") for q in pts)
        ) + "Z")
    p["d"] = "".join(novo)

mapa = {"w": 1000, "h": h, "p": paths}
with open(os.path.join(OUT, "mapa.js"), "w", encoding="utf-8") as fh:
    fh.write("window.BI=window.BI||{};BI.mapa=" + js(mapa) + ";")
print(f"  mapa.js          {os.path.getsize(os.path.join(OUT,'mapa.js'))/1e6:5.2f} MB | {len(paths)} municipios")

# ---------------------------------------------------------------- resumo
print(f"\nlocalidades={N} indicadores={len(indicadores)} ods={len(ods_meta)}")
print("tipos:", pd.Series([i["tipo"] for i in indicadores]).value_counts().to_dict())
print("polaridade:", pd.Series([i["pol"] for i in indicadores]).value_counts().to_dict())
print("sem recorte:", sum(1 for i in indicadores if not i["recorte"]))
