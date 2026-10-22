"""
Gera o payload do BI (JS classico, para rodar via file:// sem servidor).

Saidas em data/bi/:
  indice.js        -> BI.indice (localidades, indicadores, ods) + BI.build
  val_odsN.js      -> BI.valores[id] = [valores...]  (matriz localidade x ano, achatada)
  mapa.js          -> BI.mapa = {w, h, p:[{c, d, x, y}]}  (path SVG por codigo IBGE)
  (populacao.js e gerado por 04_build_populacao.py)

Ordem do array achatado: idx = localidade_idx * n_anos + ano_idx
Valores ausentes = null.

Identidade do payload: BI.build.id = hash do catalogo + geografia + populacao.
Se algum arquivo for gerado fora de sequencia, os ids nao batem e o app recusa
a renderizar (ver prototipo.js, checagem de integridade).

Uso: python scripts/03_build_bi.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from collections import OrderedDict

import pandas as pd

from _comum import chave_negocio, id_curto, localidades, norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bi")
os.makedirs(OUT, exist_ok=True)


def ler_fontes():
    """Registro de fontes oficiais (data/fontes.csv) — a proveniencia de cada espelho local."""
    caminho = os.path.join(ROOT, "data", "fontes.csv")
    if not os.path.exists(caminho):
        return {}
    import csv
    import io
    with io.open(caminho, encoding="utf-8-sig", newline="") as fh:
        return {r["arquivo"]: r for r in csv.DictReader(fh, delimiter=";")}

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
    9: "Indústria, Inovação e Infraestrutura", 11: "Cidades Sustentáveis",
    13: "Ação Contra a Mudança Global do Clima",
    15: "Vida Terrestre", 16: "Paz, Justiça e Instituições Eficazes",
}

RECORTES = {
    "Total", "Masculino", "Feminino", "Urbano", "Urbana", "Rural",
    "Cor/Raça Branca", "Cor/Raça Preta", "Cor/Raça Amarela",
    "Cor/Raça Parda", "Cor/Raça Indígena",
}

# Indicador principal de cada ODS — nome EXATO da coluna de origem (chave de negócio).
# Substitui a busca por substring que vivia no JavaScript (fragil e duplicada).
# 13: "Mortes no trânsito" -> 11.2
# 16: "Proporção de Nascidos Vivos Registrados por Autoridade Civil" -> 16.10
PRINCIPAL_POR_ODS = {
    1: "Proporção do Total das Despesas Públicas Municipais com Educação e Seguridade Social (%)",
    2: "Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Total (%)",
    3: "Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Total (mil nascidos vivos)",
    4: "Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Total (%)",
    5: "Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Total (%)",
    6: "Atendimento de Esgoto - Unidades Atendidas Residenciais",
    7: "Energia Elétrica Residencial - Consumidores",
    8: "Produto Interno Bruto (PIB) per Capita (R$ 1,00)",
    9: "Percentual do Valor Adicionado Bruto na Indústria sobre o PIB (%)",
    13: "Número de Mortes, Pessoas Desaparecidas e Pessoas Diretamente Afetadas Atribuído a Desastres (100 mil habitantes)",
    15: "Área de Remanescente Florestal como Proporção da Área Territorial (%)",
    16: "Taxa de Mortalidade por Homicídios (100 mil habitantes)",
    11: "Mortes no trânsito (100 mil habitantes)",
}

# Indicadores que aparecem em um segundo ODS sem duplicar a serie.
# A mesma serie oficial e espelhada (mesmos valores, ids diferentes) e a sintese
# conta cada serie underlying uma vez só.
ESPELHOS = {
    11: [dict(
        origem="Taxa de Mortalidade Causas Externas - Acidentes de Trânsito (Transporte)",
        grupo="Cidades Sustentáveis",
        medida="Mortes no trânsito",
        gcurto="Mortes no trânsito",
        justificativa="Mesma serie oficial do Ministerio da Saude (CID10 V01-V99), "
                      "classificada tambem no ODS 11 (cidades sustentaveis), como faz o IDSC.",
    )],
}

# Contagens que podem ser vistas como taxa por 100 mil habitantes: o numerador tem de
# contar pessoas ou eventos. "Unidades atendidas", "consumidores" etc. sao de outra
# natureza e ficam no absoluto (decisao do cliente em 21/10/2026).
UNIDADES_PROPORCIONAIS = {"óbitos", "vínculos", "RAIS"}
MOTIVO_PROPORCIONAL = {
    "óbitos": "numerador conta pessoas (óbitos)",
    "vínculos": "numerador conta vínculos de emprego (pessoas)",
    "RAIS": "numerador conta vínculos de emprego (pessoas)",
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

    proporcional = tipo == "contagem" and unidade in UNIDADES_PROPORCIONAIS

    return {
        "grupo": grupo,
        "medida": medida,
        "recorte": recorte,
        "unidade": unidade,
        "tipo": tipo,
        "proporcional": proporcional,
        "proporcional_motivo": MOTIVO_PROPORCIONAL.get(unidade) if proporcional else None,
    }


# --- Critérios de polaridade (DECISOES.md §2.7) -------------------------------
#   -1  menos é melhor (mortalidade, doença, risco)
#    0  sem juízo de valor (volume absoluto, indicador estrutural/descritivo,
#       diferença entre grupos: não medem o desempenho do município)
#   +1  mais é melhor (cobertura, acesso, renda, registro, equidade)
PALAVRAS_ADVERSAS = (
    "mortalidade", "obito", "óbitos", "mortes", "casos de", "incidencia", "incidência",
    "desnutri", "baixo peso", "homicid", "suicid", "desaparec", "desastre",
    "internac", "uti", "tuberculose", "hepatite", "aids", "hiv",
    "mães adolescentes", "insuficiente",
)

# exceções curadas: indicadores em que o critério geral pede decisão humana
POLARIDADE_CURADA = {
    "Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores":
        (1, "indicador de equidade de gênero: mais representação é melhor"),
    "Proporção de Mulheres em Posições Gerenciais - RAIS":
        (1, "indicador de equidade de gênero: mais representação é melhor"),
    "Proporção dos Casos de AIDS entre Mulheres":
        (0, "indicador de composição/disparidade: não mede o desempenho do município"),
    "Percentual do Valor Adicionado Bruto na Indústria sobre o PIB":
        (0, "indicador estrutural (composição da economia), sem direção de valor "
            "— como no ODS 9.2.1 das ONU"),
    "Emprego no Setor de Indústria como Percentual do Emprego Total":
        (0, "indicador estrutural (participação setorial do emprego), sem direção de valor"),
    "Proporção de Empregos (RAIS) nas Atividades Características do Turismo":
        (0, "indicador estrutural (participação setorial), sem direção de valor"),
    "Valor Adicionado Fiscal nas Atividades Características do Turismo":
        (0, "indicador estrutural (valor adicionado setorial), sem direção de valor"),
    "Área de Remanescente Florestal como Proporção da Área Territorial":
        (1, "proxy ambiental: mais cobertura florestal é melhor"),
    "Proporção de Nascidos Vivos Registrados por uma Autoridade Civil":
        (1, "mais registro significa mais cobertura do sistema civil"),
    "Número de Agências Bancárias e Postos de Atendimento Eletrônico":
        (1, "proxy de acesso financeiro: mais agência por 100 mil adultos é melhor"),
    "Proporção de Pessoas de 4 a 5 anos Matriculados na Pré-Escola":
        (1, "cobertura de matrícula: mais matriculado é melhor"),
    "Proporção do Total das Despesas Públicas Municipais com Educação e Seguridade Social":
        (1, "esforço municipal em educação: mais é melhor"),
    "Taxa de Incidência de AIDS":
        (-1, "incidência de doença: menos é melhor"),
    "Taxa de Incidência de Hepatite B":
        (-1, "incidência de doença: menos é melhor"),
    "Taxa de Incidência de Tuberculose":
        (-1, "incidência de doença: menos é melhor"),
}


def polaridade(nome: str, tipo: str = "", grupo: str = ""):
    """(+1 maior é melhor | -1 menor é melhor | 0 sem juízo de valor, motivo).

    A tabela curada é casada pelo GRUPO (nome do tema no dicionário), que é estável
    entre versões da base; a medida vem da coluna de origem.
    """
    medida = nome.lower()
    alvo = medida + " | " + (grupo or "").lower()
    for k, v in POLARIDADE_CURADA.items():
        if k.lower() in alvo:
            return v
    if any(k in medida for k in ("cobertura vacinal", "vacinal")):
        return 1, "cobertura vacinal: mais cobertura é melhor"
    # 1) volume absoluto: só tem juízo se o volume for um evento adverso
    if tipo == "contagem":
        if any(k in medida for k in PALAVRAS_ADVERSAS):
            return -1, "volume de eventos adversos: menos é melhor"
        return 0, "volume absoluto (não mede qualidade): sem juízo de valor"
    # 2) eventos adversos e risco
    if any(k in medida for k in PALAVRAS_ADVERSAS):
        return -1, "mortalidade, doença ou risco: menos é melhor"
    # 3) indicadores estruturais/descritivos (composição do econômico, diferenças)
    if any(k in medida for k in ("valor adicionado", "participa", "composi",
                                "percentual do valor", "diferença", "diferenca",
                                "razão", "razao", "coeficiente", "favela",
                                "comunidades urbanas")):
        return 0, "indicador estrutural/descritivo: sem juízo de valor"
    # 4) demais: cobertura, acesso, resultado positivo
    return 1, "cobertura, acesso ou resultado positivo: mais é melhor"


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
    "taxa de incidencia de hepatite b": "Incidência de Hepatite B",
    "taxa de incidencia de tuberculose": "Incidência de Tuberculose",
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


def sha(*blobs: bytes) -> str:
    h = hashlib.sha256()
    for b in blobs:
        h.update(b)
        h.update(b"\x00")
    return h.hexdigest()[:12]


# ---------------------------------------------------------------- dados
long = pd.read_csv(os.path.join(ROOT, "data", "long.csv.gz"))
catalogo = json.load(open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8"))
ibge = json.load(open(os.path.join(ROOT, "data", "geo", "ibge_municipios.json"), encoding="utf-8"))
geo = json.load(open(os.path.join(ROOT, "data", "geo", "pr_municipios.geojson"), encoding="utf-8"))
caminho_pop = os.path.join(ROOT, "data", "bi", "populacao.js")
pop_bytes = b""
if os.path.exists(caminho_pop):
    with open(caminho_pop, "rb") as fh:
        pop_bytes = fh.read()

# registro de fontes oficiais (proveniencia de cada espelho local)
FONTES = ler_fontes()

# --- Revisão de polaridade (exportada pela aba Revisão do painel) -------------
# O JSON é a decisão do revisor e TEM precedência sobre o critério automático.
# Chave = nome da coluna de origem (estável). Chave desconhecida = erro alto:
# nada de aplicar parte da revisão e publicar em silêncio.
CAMINHO_POLARIDADE = os.path.join(ROOT, "data", "polaridade.json")
REVISADO = {}
if os.path.exists(CAMINHO_POLARIDADE):
    with open(CAMINHO_POLARIDADE, encoding="utf-8") as fh:
        bruto = json.load(fh)
    if "polaridade" in bruto and isinstance(bruto["polaridade"], dict):
        REVISADO = {str(k): int(v) for k, v in bruto["polaridade"].items()}
    else:
        REVISADO = {str(k): int(v) for k, v in bruto.items()}
    print("  revisão de polaridade carregada: %d decisão(ões)" % len(REVISADO))

# indicadores de fontes externas ja processadas (ex.: SINISA)
caminho_sinisa = os.path.join(OUT, "sinisa.js")
sinisa_bytes = b""
SINISA = None
if os.path.exists(caminho_sinisa):
    with open(caminho_sinisa, "rb") as fh:
        sinisa_bytes = fh.read()
    SINISA = json.loads(sinisa_bytes.decode("utf-8").split("BI.sinisa=", 1)[1].rstrip().rstrip(";"))

# manifest: identidade do payload ( impede misturar geracoes diferentes )
# REGRAS_VERSION entra no hash: se as regras de derivacao mudarem (polaridade,
# proporcionalidade, rotulos), o build muda e o app recusa payload antigo.
REGRAS_VERSION = "2026-10-21"
# Versao PUBLICA: o painel vai para fora (GitHub Pages) e a aba de Revisao
# nao pode existir — revisar polaridade e privilegio do curador.
# Uso: python scripts/03_build_bi.py --publico
PUBLICO = "--publico" in sys.argv
BUILD_ID = sha(
    REGRAS_VERSION.encode("utf-8"),
    json.dumps(catalogo, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    json.dumps(ibge, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    pop_bytes,
    sinisa_bytes,
)
BUILD = {
    "id": BUILD_ID,
    "gerado_em": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
    "regras": REGRAS_VERSION,
    "fonte_catalogo": "scripts/01_build_catalog.py",
    "n_indicadores_catalogo": len(catalogo),
    "publico": PUBLICO,
    "revisao": not PUBLICO,
}

# ---------------------------------------------------------------- localidades
localidades_ = localidades(long, ibge)
N = len(localidades_)
idx_loc = {l["n"]: i for i, l in enumerate(localidades_)}

# ---------------------------------------------------------------- indicadores
pilhas = {l: {} for l in long["localidade"].unique()}
for r in long.itertuples(index=False):
    pilhas[r.localidade].setdefault(r.indicador, {})[int(r.ano)] = r.valor

indicadores = []
por_ods: "OrderedDict[int, list]" = OrderedDict()
chaves_vistas = {}

for c in catalogo:
    p = parse(c["indicador"], c["grupo_tema"])
    anos = sorted({int(a) for a in c["anos_com_dados"]})
    if not anos:
        continue
    chave = chave_negocio(c["indicador"])
    if chave in chaves_vistas:
        raise ValueError("chave de negócio duplicada: %r (já usada por %s)"
                         % (chave, chaves_vistas[chave]))
    chaves_vistas[chave] = c["indicador"]
    pol, pol_motivo = polaridade(p["medida"], p["tipo"], p["grupo"])
    if c["indicador"] in REVISADO:
        novo = REVISADO[c["indicador"]]
        if novo != pol:
            pol_motivo = "revisado por_curador"
        pol = novo
    fonte = FONTES.get(c["arquivo"], {})
    meta = {
        "id": id_curto(chave),
        "chave": chave,
        "ods": c["ods"],
        "grupo": p["grupo"],
        "gcurto": GRUPOS_CURTOS.get(norm(p["grupo"]), p["grupo"]),
        "medida": p["medida"],
        "recorte": p["recorte"],
        "unidade": p["unidade"],
        "tipo": p["tipo"],
        "pol": pol,
        "pol_motivo": pol_motivo,
        "proporcional": p["proporcional"],
        "proporcional_motivo": p["proporcional_motivo"],
        "nome": curto(c["indicador"]),
        "codigo": c["codigo_ods"],
        "fonte": c["fonte"],
        "definicao": c["definicao"],
        "formula": c["formula"],
        "arquivo": c["arquivo"],
        "atualizado_em": str(c.get("atualizado_em") or "")[:10],
        "n_municipios": c["n_municipios"],
        "pct_ausente": c["pct_ausente"],
        # proveniencia da fonte oficial (data/fontes.csv)
        "fonte_id": fonte.get("id", ""),
        "fonte_publicador": fonte.get("publicador", ""),
        "fonte_acesso": fonte.get("tipo_acesso", ""),
        "fonte_url": fonte.get("url_landing", ""),
        "fonte_baixado": fonte.get("ultima_aquisicao", ""),
        "fonte_sha": (fonte.get("sha256", "") or "")[:12],
        "anos": anos,
    }
    indicadores.append(meta)
    por_ods.setdefault(c["ods"], []).append((meta, anos, c["indicador"]))

# (o indicador principal de cada ODS e marcado depois dos espelhos)

# indicadores de fontes externas (SINISA): entram como indicadores proprios,
# nunca substituem um indicador existente (cada um com a sua fonte declarada)
valores_externos = {}
if SINISA:
    for meta in SINISA["ind"]:
        indicadores.append(meta)
        por_ods.setdefault(meta["ods"], []).append((meta, meta["anos"], None))
        valores_externos[meta["id"]] = SINISA["valores"][meta["id"]]

# espelhos: a mesma serie oficial classificada em um segundo ODS
espelhos = {}
for ods, itens in ESPELHOS.items():
    for item in itens:
        orig = next((m for m in indicadores if norm(m["medida"]) == norm(item["origem"])), None)
        if orig is None:
            raise ValueError("indicador de origem do espelho nao encontrado: %r" % item["origem"])
        chave = "ESPELHO %s | %s" % (ods, item["medida"])
        clone = dict(orig)
        clone["id"] = id_curto(chave)
        clone["chave"] = chave
        clone["ods"] = ods
        clone["grupo"] = item["grupo"]
        clone["gcurto"] = item["gcurto"]
        clone["medida"] = item["medida"]
        clone["espelho_de"] = orig["id"]
        clone["espelho_motivo"] = item["justificativa"]
        clone["nome"] = "%s (%s)" % (item["medida"], orig["unidade"])
        clone["principal"] = False
        indicadores.append(clone)
        espelhos[clone["id"]] = orig["id"]
        por_ods.setdefault(ods, []).append((clone, clone["anos"], None))
        print("  espelho: ODS %d <- %s (%s)" % (ods, orig["gcurto"], orig["id"]))

# marca o indicador principal de cada ODS (chave de negocio explicita)
for ods, nome in PRINCIPAL_POR_ODS.items():
    achou = [m for m, _, _ in por_ods.get(ods, []) if m["nome"] == nome]
    if not achou:
        raise ValueError("indicador principal do ODS %d nao encontrado: %r" % (ods, nome))
    achou[0]["principal"] = True
for m in indicadores:
    m.setdefault("principal", False)

# ---------------------------------------------------------------- valores
total_bytes = 0
for ods, itens in por_ods.items():
    nome_arquivo = f"val_ods{ods}.js"
    linhas = ["window.BI=window.BI||{};",
              "window.BI.builds=window.BI.builds||{};",
              'window.BI.builds["%s"]=%s;' % (nome_arquivo, js(BUILD)),
              "window.BI.valores=window.BI.valores||{};"]
    for meta, anos, nome_original in itens:
        n_a = len(anos)
        if meta["id"] in espelhos:
            # o espelho e escrito junto com a serie de origem (alias em JS)
            continue
        if nome_original is None:
            # valor de fonte externa (ja no layout do payload)
            linhas.append('BI.valores["%s"]=%s;' % (meta["id"], js(valores_externos[meta["id"]])))
            continue
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
        # espelhos desta serie: alias em JS (mesmos dados, sem duplicar)
        for esp_id, orig_id in espelhos.items():
            if orig_id == meta["id"]:
                linhas.append('BI.valores["%s"]=BI.valores["%s"];' % (esp_id, orig_id))
    conteudo = "\n".join(linhas)
    caminho = os.path.join(OUT, nome_arquivo)
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
    principal = next((m["id"] for m, _, _ in its if m["principal"]), None)
    ods_meta.append({
        "n": ods, "nome": NOME_ODS.get(ods, ""), "cor": CORES_ODS.get(ods, "#666"),
        "n_ind": len(its), "grupos": grupos, "principal": principal,
    })

indice = {
    "gerado": BUILD["gerado_em"][:10],
    "fonte_estado": "Paraná",
    "localidades": localidades_,
    "indicadores": indicadores,
    "ods": ods_meta,
}
with open(os.path.join(OUT, "indice.js"), "w", encoding="utf-8") as fh:
    fh.write("window.BI=window.BI||{};window.BI.build=" + js(BUILD) +
             ';window.BI.builds=window.BI.builds||{};window.BI.builds["indice.js"]=' + js(BUILD) +
             ";BI.indice=" + js(indice) + ";")
print(f"  indice.js        {os.path.getsize(os.path.join(OUT,'indice.js'))/1e6:5.2f} MB")

# ---------------------------------------------------------------- mapa
# equirretangular com correcao de latitude (paralelo padrao no centro do Parana)
LAT0 = -23.5


def projetar(lon, lat):
    x = (lon + 54.3) * math.cos(math.radians(LAT0))
    y = (22.5 - lat)
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
    xs_p, ys_p = [], []
    for seg in p["d"].split("Z"):
        if not seg:
            continue
        pts = seg.replace("M", "").split("L")
        conv = []
        for q in pts:
            a, b = q.split(",")
            nx, ny = (float(a) - x0) * k, (float(b) - y0) * k
            xs_p.append(nx); ys_p.append(ny)
            conv.append(f"{nx:.1f},{ny:.1f}")
        novo.append("M" + "L".join(conv) + "Z")
    p["d"] = "".join(novo)
    # centroide (caixa delimitadora) para o rotulo do municipio em foco
    p["x"] = round((min(xs_p) + max(xs_p)) / 2, 1) if xs_p else 0
    p["y"] = round((min(ys_p) + max(ys_p)) / 2, 1) if ys_p else 0

mapa = {"w": 1000, "h": h, "p": paths}
with open(os.path.join(OUT, "mapa.js"), "w", encoding="utf-8") as fh:
    fh.write("window.BI=window.BI||{};window.BI.builds=window.BI.builds||{};"
             'window.BI.builds["mapa.js"]=' + js(BUILD) + ";BI.mapa=" + js(mapa) + ";")
print(f"  mapa.js          {os.path.getsize(os.path.join(OUT,'mapa.js'))/1e6:5.2f} MB | {len(paths)} municipios")

# ---------------------------------------------------------------- html sincronizado
# Reescreve as tags <script src="...js"> com a versao do build, para que o HTML
# abra sempre o payload da mesma geracao (e o navegador nao sirva cache velho).
caminho_html = os.path.join(ROOT, "prototipo.html")
with open(caminho_html, encoding="utf-8") as fh:
    html = fh.read()
html = re.sub(r'(src="(?:core\.js|data/bi/[a-z0-9_]+\.js))(\?v=[0-9a-f]+)?"',
              r'\1?v=' + BUILD_ID + '"', html)
if PUBLICO:
    # versao publica: a aba de Revisao nao existe (so o curador revisa, na sua maquina)
    html = re.sub(r'\s*<button data-view="revisao"[^>]*>Revisão</button>', "", html)
    html = re.sub(r'\s*<!-- =+ REVISÃO =+ -->\s*<section class="view" id="view-revisao">[\s\S]*?</section>',
                  "", html)
    html = re.sub(r'\s*<section class="view" id="view-revisao">[\s\S]*?</section>', "", html)
with open(caminho_html, "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"  prototipo.html    sincronizado com o build {BUILD_ID}"
      + (" (versão pública: aba de revisão removida)" if PUBLICO else ""))

# ---------------------------------------------------------------- resumo e checagens
print(f"\nlocalidades={N} indicadores={len(indicadores)} ods={len(ods_meta)} build={BUILD_ID}")
print("tipos:", pd.Series([i["tipo"] for i in indicadores]).value_counts().to_dict())
print("polaridade:", pd.Series([i["pol"] for i in indicadores]).value_counts().to_dict())
print("proporcionais (contagens -> por 100 mil hab.):",
      sum(1 for i in indicadores if i["proporcional"]))
print("sem recorte:", sum(1 for i in indicadores if not i["recorte"]))

# checagens de contrato (falham alto, nao apenas avisam)
chaves_desconhecidas = [k for k in REVISADO if k not in {c["indicador"] for c in cat}]
if chaves_desconhecidas:
    raise SystemExit(
        "polaridade.json tem %d chave(s) que nao existem na base:\n  - %s\n"
        "A base mudou desde a revisao: reexporte a revisao na aba Revisao."
        % (len(chaves_desconhecidas), "\n  - ".join(chaves_desconhecidas[:5])))
n_esperados = (len(catalogo) - 2 + (len(SINISA["ind"]) if SINISA else 0)
                + sum(len(v) for v in ESPELHOS.values()))
assert len(indicadores) == n_esperados, (
    "esperados %d indicadores (2 sem dados no catalogo), vieram %d" % (n_esperados, len(indicadores)))
assert len({i["id"] for i in indicadores}) == len(indicadores), "id de indicador duplicado"
assert all(i["anos"] == sorted(i["anos"]) for i in indicadores), "anos fora de ordem"
assert all(i["n_municipios"] == 399 for i in indicadores), "indicador sem os 399 municipios"
print("checagens de contrato: OK")
