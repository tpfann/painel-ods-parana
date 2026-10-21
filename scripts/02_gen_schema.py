"""
Gera DATA_SCHEMA.md a partir de data/catalog.json + data/bi/indice.js.

Todos os numeros do documento sao CALCULADOS (nada fixo no codigo): o documento
nao pode envelhecer sem que a base mude junto.

As decisoes do projeto (tomadas com o cliente) NAO ficam aqui: vivem em
DECISOES.md, que e curado a mao e nunca e sobrescrito por este script.

Uso: python scripts/02_gen_schema.py   (depois de 01, 04 e 03)
"""

from __future__ import annotations

import json
import os
from collections import Counter, OrderedDict

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = os.path.join(ROOT, "data", "catalog.json")
INDICE = os.path.join(ROOT, "data", "bi", "indice.js")
LONG = os.path.join(ROOT, "data", "long.csv.gz")
SAIDA = os.path.join(ROOT, "DATA_SCHEMA.md")

N_MUN = 399


def curto(nome: str) -> str:
    import re
    return re.sub(r"^ODS - Objetivo \d+ - ", "", nome).strip()


def main() -> None:
    cat = json.load(open(CAT, encoding="utf-8"))
    txt = open(INDICE, encoding="utf-8").read()
    ind = json.loads(txt.split("BI.indice=", 1)[1].rstrip().rstrip(";"))
    build = json.loads(txt.split("window.BI.build=", 1)[1].split(";BI.indice=")[0])

    inds = ind["indicadores"]
    locs = ind["localidades"]
    long = pd.read_csv(LONG)

    celulas = sum(c["n_linhas"] for c in cat)
    observacoes = int(len(long))
    muns = sorted(l["n"] for l in locs if l["t"] == "municipio")
    regs = sorted(l["n"] for l in locs if l["t"] == "regiao")
    anos_min = min(int(a) for a in long["ano"].dropna())
    anos_max = max(int(a) for a in long["ano"].dropna())
    com_2025 = sum(1 for i in inds if i["anos"][-1] == 2025)

    grupos: "OrderedDict[tuple, list]" = OrderedDict()
    for c in cat:
        grupos.setdefault((c["ods"], c["grupo_tema"]), []).append(c)
    arquivos: "OrderedDict[str, list]" = OrderedDict()
    for c in cat:
        arquivos.setdefault(c["arquivo"], []).append(c)

    L: list = []
    A = L.append

    A("# DATA_SCHEMA — Painel ODS · Paraná")
    A("")
    A("> Documento **gerado** por `scripts/02_gen_schema.py` a partir de "
      "`scripts/01_build_catalog.py` e `scripts/03_build_bi.py`. Não editar à mão.")
    A("> As decisões do projeto (com o cliente) estão em **[DECISOES.md](DECISOES.md)** — "
      "esse arquivo é curado à mão e não é sobrescrito por este script.")
    A("")
    A("| Build | Gerado em | Regras |")
    A("|---|---|---|")
    A(f"| `{build['id']}` | {build['gerado_em']} | {build.get('regras', '—')} |")
    A("")

    A("## 1. Inventário")
    A("")
    A("| Item | Valor |")
    A("|---|---|")
    A(f"| Planilhas de dados | **{len(arquivos)}** `.xlsx` (pasta `Base de Dados/`) |")
    A(f"| Dicionário | 1 `.xlsx` (pasta `Dicionário/`) — **{len(cat)}** variáveis |")
    A(f"| Indicadores na base | **{len(cat)}** (dos quais **{len(inds)}** têm dados e entram no BI) |")
    A(f"| Observações com valor | **{observacoes:,}** de {celulas:,} células "
      f"({100*observacoes/celulas:.1f}% de preenchimento) |")
    A(f"| Localidades | **{len(locs)}** → {len(muns)} municípios + `Estado do Paraná` + {len(regs)} `RGInt de …` |")
    A(f"| Período | **{anos_min} – {anos_max}** (varia por indicador) |")
    A(f"| Indicadores com dado em {anos_max} | {com_2025} de {len(inds)} |")
    A("| Unidade territorial | Estado do Paraná (foco: **Guarapuava**) |")
    A("")

    A("## 2. Formato canônico de todas as planilhas")
    A("")
    A("```")
    A("A1: Assunto | B1: Localidade | C1: Ano | D..N1: <nome do indicador>   (1 a 36 colunas)")
    A("A2..: texto  | nome do local | 2010 (numérico) | valor (numérico)")
    A("```")
    A("")
    A("- Formato **longo**: uma linha por `localidade × ano`.")
    A("- A coluna `Assunto` é constante dentro do arquivo.")
    A("- As colunas `D..N` são **indicadores distintos** (não medidas repetidas).")
    A("- Não existe coluna de população, território ou região — a população vem do IBGE (§8).")
    A("")
    A("### 2.1 Códigos de ausência")
    A("")
    A("| Código | Onde aparece | Tratamento |")
    A("|---|---|---|")
    A("| `...` | saúde, vacinação, AIDS | nulo |")
    A("| `-` | RAIS, educação, PIB | nulo |")
    A("| `..` | idem | nulo |")
    A("| célula vazia | casos isolados | nulo |")
    A("")
    A("Não há `0` usado como ausente: zeros são **valores reais** (ex.: 0 óbitos). Isso é crítico "
      "para séries de mortalidade — 0 deve ser plotado, `...` deve virar lacuna.")
    A("")

    A("## 3. Dimensões")
    A("")
    A("### 3.1 `Localidade`")
    A("")
    A("| Tipo | Quantidade | Papel no BI |")
    A("|---|---:|---|")
    A(f"| Estado | 1 | benchmark estadual |")
    A(f"| Região Geográfica Intermediária | {len(regs)} | agregação regional |")
    A(f"| Município | {len(muns)} | nível de análise principal |")
    A("")
    A("As RGInt são exatamente as **Regiões Geográficas Intermediárias** do IBGE (de-para "
      "confirmado por `scripts/00_build_geo.py`, com asserção): "
      + ", ".join(r.replace("RGInt de ", "") for r in regs) + ".")
    A("")
    A("Os agregados regionais são **pré-calculados na fonte** e existem apenas em parte dos "
      "indicadores; nos demais o nível regional simplesmente não é exibido.")
    A("")

    A("### 3.2 `Ano`")
    A("")
    A(f"- Inteiro, {anos_min}–{anos_max}. **Não é uma série contínua por indicador** — cada um tem sua janela.")
    A("- Séries com anos faltantes (ex.: ODS 5 só em anos eleitorais) **não** podem ser lidas "
      "como linha contínua: o app desenha pontos em anos sem vizinho.")
    A("")

    A("### 3.3 `Assunto`")
    A("")
    A("Constante por arquivo. Equivale a `ODS N - <tema>` e serve de rótulo de seção. "
      "Não é uma dimensão analítica — o agrupamento real está em §4.")
    A("")

    A("## 4. Modelo dos indicadores")
    A("")
    A("```")
    A("ODS - Objetivo <N> - <GRUPO> - <MEDIDA> - <RECORTE> (<UNIDADE>)")
    A("```")
    A("")
    A("| Campo | Exemplo | Uso no BI |")
    A("|---|---|---|")
    A("| `ods` | `3` | filtro de objetivo |")
    A("| `grupo` | `Mortalidade Neonatal` | seção / cartão |")
    A("| `medida` | `Taxa de Mortalidade Neonatal` vs `Número de Óbitos Neonatais` | métrica vs volume |")
    A("| `recorte` | `Total`, `Cor/Raça Branca`, `Masculino`, `Urbano` | desagregação |")
    A("| `unidade` | `%`, `100 mil hab.`, `mil nascidos vivos`, `R$` | formatação |")
    A("")
    A("**`Total` é o indicador-síntese**; as demais colunas são o mesmo fenômeno quebrado por "
      "cor/raça, sexo ou área. O BI mostra o `Total` e oferece o recorte como detalhe — nunca "
      "soma recorte com Total.")
    A("")
    rec = Counter(str(i["recorte"] or "sem recorte") for i in inds)
    A("Distribuição do campo `recorte` nos indicadores do BI:")
    A("")
    A("| Recorte | Qtd |")
    A("|---|---:|")
    for k, v in sorted(rec.items(), key=lambda kv: (-kv[1], kv[0])):
        A(f"| `{k}` | {v} |")
    A("")
    un = Counter(i["unidade"] or "(sem unidade explícita)" for i in inds)
    A("### 4.1 Unidades e escalas")
    A("")
    A("| Unidade | Qtd |")
    A("|---|---:|")
    for k, v in sorted(un.items(), key=lambda kv: (-kv[1], kv[0])):
        A(f"| `{k}` | {v} |")
    A("")
    A("⚠️ **Escalas diferentes dentro do mesmo ODS 3**: mortalidade neonatal é por *mil* nascidos "
      "vivos, materna por *100 mil*. Um valor de 8,5 e outro de 60,0 não são comparáveis — o BI "
      "carrega a unidade junto do número e nunca converte.")
    A("")

    A("## 5. Chaves e identidade")
    A("")
    A("| Chave | Onde | Estabilidade |")
    A("|---|---|---|")
    A("| `chave` | nome original da coluna de origem (`chave` no `indice.js`) | **estável**: não depende da ordem do catálogo |")
    A("| `id` | hash curto de 8 caracteres da `chave` | estável, curto (DOM/JS) |")
    A("| `BI.build.id` | manifesto do payload | muda quando dados ou regras mudam |")
    A("")
    A("A revisão de polaridade é exportada **por `chave`**, nunca por `id` posicional: assim uma "
      "atualização da base não desloca as decisões do revisor.")
    A("")

    A("## 6. Catálogo de arquivos")
    A("")
    A("| # | ODS | Arquivo | Cols | Período | Ausentes | RGInt |")
    A("|---:|---:|---|---:|---|---:|---|")
    for i, (arq, cs) in enumerate(arquivos.items(), 1):
        c0 = cs[0]
        aus = sum(x["pct_ausente"] for x in cs) / len(cs)
        A(f"| {i} | {c0['ods']} | {arq} | {len(cs)} | {c0['ano_min']}–{c0['ano_max']} | "
          f"{aus:.0f}% | {'sim' if c0['tem_agregado_regional'] else '—'} |")
    A("")

    A("## 7. Catálogo de indicadores (BI)")
    A("")
    A("| # | id | ODS | Grupo | Indicador | Código | Anos | Fonte |")
    A("|---:|---|---|---|---|---|---|---|")
    for i, ind_ in enumerate(inds, 1):
        A(f"| {i} | `{ind_['id']}` | {ind_['ods']} | {ind_['grupo']} | {ind_['nome']} | "
          f"`{ind_['codigo']}` | {ind_['anos'][0]}–{ind_['anos'][-1]} | "
          f"{str(ind_.get('atualizado_em') or '—')[:10]} |")
    A("")

    A("## 8. Armadilhas e qualidade dos dados")
    A("")
    A("| # | Problema | Impacto | Mitigação |")
    A("|---:|---|---|---|")
    A("| 1 | Escalas heterogêneas dentro do mesmo tema | comparação direta enganosa | unidade sempre visível |")
    A("| 2 | Indicador ≠ % sempre (contagens, moeda) | ranking por “maior %” fica errado | campo `tipo` por indicador |")
    A("| 3 | Ausência codificada como texto (`...`, `-`) | somas silenciosamente ignoradas | ETL converte para nulo |")
    A("| 4 | Indicadores 100% vazios | gráfico vazio | ignorados no ETL (2 de 196) |")
    A("| 5 | Cobertura baixa em recortes raciais | média distorcida, série quebrada | mostra-se o `n` disponível |")
    A("| 6 | Agregado regional ausente em parte dos indicadores | nível regional não exibido | oculto quando ausente |")
    A("| 7 | Séries com janelas diferentes | comparação multi-indicador enganosa | eixo X no ano real; lacunas desenhadas como pontos |")
    A("| 8 | ODS 5 só em anos eleitorais | linha contínua sugere interpolação | sem segmento entre anos distantes |")
    A("| 9 | Indicadores com muitos municípios empatados | percentil vira 100% para todos | regra de elegibilidade para síntese (ver DECISOES.md) |")
    A("| 10 | Indicadores com pouquíssimos municípios com dado | posição sem base de comparação | `n` exibido; fora das sínteses |")
    A("| 11 | Sem população por município na base | impossível recalcular taxas | denominador do IBGE (populate.js) |")
    A("| 12 | `Assunto` redundante | 1,2 M de strings repetidas | descartado no ETL |")
    A("")

    A("## 9. População (denominador das taxas calculadas)")
    A("")
    A("`data/bi/populacao.js` traz `BI.pop = {anos, valores, info}` na mesma ordem de "
      "`BI.indice.localidades`, achatado por `[localidade × n_anos + ano]`. Fontes: estimativas do "
      "IBGE (agregado 6579/9324), Censo 2022 (4714/93) e Censo 2010 (200/93). Anos sem "
      "publicação são interpolados linearmente entre os vizinhos e **marcados em `info`**. "
      "Estado e RGInt são a soma dos municípios.")
    A("")

    with open(SAIDA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("DATA_SCHEMA.md gerado com %d linhas (%d indicadores)." % (len(L), len(inds)))


if __name__ == "__main__":
    main()
