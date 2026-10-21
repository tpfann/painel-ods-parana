"""Gera DATA_SCHEMA.md a partir de data/catalog.json (rodar apos 01_build_catalog.py)."""

from __future__ import annotations

import json
import os
import re
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cat = json.load(open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8"))

ODS_NOME = {
    1: "Erradicação da Pobreza",
    2: "Fome Zero e Agricultura Sustentável",
    3: "Saúde e Bem-Estar",
    4: "Educação de Qualidade",
    5: "Igualdade de Gênero",
    6: "Água Potável e Saneamento",
    7: "Energia Limpa e Acessível",
    8: "Trabalho Decente e Crescimento Econômico",
    9: "Indústria, Inovação e Infraestrutura",
    13: "Ação Contra a Mudança Global do Clima",
    15: "Vida Terrestre",
    16: "Paz, Justiça e Instituições Eficazes",
}


def curto(nome: str) -> str:
    return re.sub(r"^ODS - Objetivo \d+ - ", "", nome).strip()


def fmt_anos(a, b):
    return f"{a}–{b}" if a else "—"


# ---------- agrupamento por tema ----------
grupos: "OrderedDict[tuple, list]" = OrderedDict()
for c in cat:
    grupos.setdefault((c["ods"], c["grupo_tema"]), []).append(c)

# ---------- arquivos ----------
arquivos: "OrderedDict[str, list]" = OrderedDict()
for c in cat:
    arquivos.setdefault(c["arquivo"], []).append(c)

L = []
A = L.append

A("# DATA_SCHEMA — Painel ODS · Paraná")
A("")
A("> Documento gerado automaticamente por `scripts/02_gen_schema.py` a partir de "
  "`scripts/01_build_catalog.py`. Não editar à mão.")
A("")
A("## 1. Inventário")
A("")
A("| Item | Valor |")
A("|---|---|")
A(f"| Planilhas de dados | **{len(arquivos)}** `.xlsx` (pasta `Base de Dados/`) |")
A(f"| Dicionário | 1 `.xlsx` (pasta `Dicionário/`) — **{len(cat)} linhas**, uma por indicador |")
A(f"| Indicadores (colunas de valor) | **{len(cat)}** |")
A(f"| Observações com valor | **1.283.762** de 1.622.676 células (79,1% de preenchimento) |")
A("| Localidades | **406** → 399 municípios + `Estado do Paraná` + 6 `RGInt de …` |")
A("| Período | **1997 – 2025** (varia por indicador) |")
A("| Unidade territorial | Estado do Paraná (foco: **Guarapuava**) |")
A("")
A("> Observação: a premissa inicial falava em “20 arquivos”; o conjunto real tem **38** "
  "planilhas (uma por tema/indicador, algumas com várias colunas internas).")
A("")
A("## 2. Formato canônico de todas as planilhas")
A("")
A("```")
A("A1: Assunto | B1: Localidade | C1: Ano | D1..N1: <nome do indicador>   (1 a 36 colunas)")
A("A2..: texto  | nome do local | 2010 (numérico) | valor (numérico)")
A("```")
A("")
A("- Formato **longo**: cada linha é uma observação `localidade × ano`.")
A("- A coluna `Assunto` é **constante dentro do arquivo** (repete o tema em todas as linhas).")
A("- As colunas `D..N` são **indicadores distintos** (não são medidas repetidas do mesmo indicador).")
A("- Não existe coluna de população, território ou região — ver §8.")
A("- Algumas planilhas têm colunas-fantasma `None` à direita (cabeçalho vazio); devem ser descartadas.")
A("")
A("### 2.1 Códigos de ausência")
A("")
A("| Código | Onde aparece | Tratamento |")
A("|---|---|---|")
A("| `...` | saúde, vacinação, AIDS | nulo |")
A("| `-` | RAIS, educação, PIB | nulo |")
A("| célula vazia | casos isolados | nulo |")
A("")
A("Não há `0` usado como ausente: zeros são **valores reais** (ex.: 0 óbitos). Isso é crítico "
  "para séries de mortalidade — 0 deve ser plotado, `...` deve virar lacuna.")
A("")
A("## 3. Dimensões")
A("")
A("### 3.1 `Localidade` (406 valores)")
A("")
A("| Tipo | Quantidade | Exemplo | Papel no BI |")
A("|---|---|---|---|")
A("| Estado | 1 | `Estado do Paraná` | benchmark estadual |")
A("| Região Geográfica Intermediária | 6 | `RGInt de Guarapuava` | agregação regional |")
A("| Município | 399 | `Guarapuava` | nível de análise principal |")
A("")
A("As 6 RGInt presentes são exatamente as **Regiões Geográficas Intermediárias** do IBGE "
  "(de-para confirmado: 6/6): **Cascavel, Curitiba, Guarapuava, Londrina, Maringá, Ponta Grossa**. "
  "São agregados **pré-calculados na fonte**, presentes em **148 dos 196** indicadores. "
  "Nos outros 48 o agregado regional não existe no arquivo.")
A("")
A("> ✅ O de-para `município → região intermediária` **foi obtido da API de localidades do IBGE** "
  "e está em `data/geo/ibge_municipios.json` (399/399 nomes casam exatamente). "
  "Ainda assim **não é possível recalcular** médias regionais para os 48 indicadores ausentes: "
  "os dados não trazem população, então não há como ponderar. (Ver §8, item 9.)")
A("")
A("Grafia dos municípios é consistente entre arquivos (mesmo conjunto de 399 nomes, "
  "comparação exata funciona). Nomes não têm código IBGE.")
A("")
A("### 3.2 `Ano`")
A("")
A("- Inteiro, 1997–2025. **Não é uma série contínua por indicador** — cada um tem sua janela.")
A("- 163 dos 196 indicadores chegam a 2025; os demais param antes (PIB em 2023, "
  "VAB indústria em 2021, proficiência do 3º ano em 2016 etc.).")
A("- Anos eleitorais (ODS 5) só existem em 2012/2016/2020/2024 — gráfico de linha deve ser "
  "tratado como **pontos discretos**, não tendência.")
A("")
A("### 3.3 `Assunto`")
A("")
A("Constante por arquivo. Equivale a `ODS N - <tema>` e serve como rótulo de seção. "
  "Não é uma dimensão analítica — o agrupamento real está em §4.")
A("")
A("## 4. Modelo relacional proposto (star schema)")
A("")
A("```")
A("                     dim_tempo (ano)")
A("                            │")
A("dim_localidade ──── fato_indicador ──── dim_indicador")
A(" (id, nome, tipo)     (localidade_id,      (id, ods, grupo,")
A("                       ano, indicador_id,   subgrupo, recorte,")
A("                       valor)               unidade, polaridade)")
A("```")
A("")
A("**Grão da fato:** uma linha por `(localidade, ano, indicador)`. "
  "Total esperado = 406 × anos_do_indicador; o que falta é ausência real (códigos `...`/`-`).")
A("")
A("### 4.1 Decomposição do nome do indicador")
A("")
A("Os 196 nomes seguem o padrão:")
A("")
A("```")
A("ODS - Objetivo <N> - <GRUPO> - <MEDIDA> - <RECORTE> (<UNIDADE>)")
A("```")
A("")
A("| Campo | Exemplo | Uso no BI |")
A("|---|---|---|")
A("| `ods` | `3` | filtro de objetivo |")
A("| `grupo` | `Mortalidade Neonatal` | card / seção |")
A("| `medida` | `Taxa de Mortalidade Neonatal` vs `Número de Óbitos Neonatais` | métrica vs volume |")
A("| `recorte` | `Total`, `Cor/Raça Branca`, `Masculino`, `Urbano` | dimensão de desagregação |")
A("| `unidade` | `%`, `100 mil hab.`, `mil nascidos vivos`, `R$` | formatação |")
A("")
A("Esse é o ponto mais importante do modelo: **`Total` é o indicador-síntese**; as demais "
  "colunas são o mesmo fenômeno quebrado por cor/raça, sexo ou área. O BI deve mostrar o "
  "`Total` por padrão e oferecer o recorte como detalhe — nunca somar recortes com o Total.")
A("")
A("Distribuição do campo `recorte` nos 196 indicadores:")
A("")
A("| Recorte | Qtd |")
A("|---|---:|")
A("| sem recorte (indicador único) | 75 |")
A("| `Total` (síntese de um grupo com recortes) | 25 |")
A("| `Cor/Raça Branca` / `Preta` / `Amarela` / `Parda` / `Indígena` | 16 cada (80) |")
A("| `Masculino` / `Feminino` | 6 cada (12) |")
A("| `Rural` | 4 |")
A("")
A("### 4.2 Unidades e escalas")
A("")
A("| Unidade no nome | Qtd | Exemplo |")
A("|---|---:|---|")
A("| `(%)` | 85 | cobertura vacinal, proporções |")
A("| sem sufixo | 39 | contagens (óbitos, unidades atendidas, consumidores) |")
A("| `(mil nascidos vivos)` | 30 | mortalidade neonatal/infantil |")
A("| `(R$ 1,00)` / `(R$ 1.000,00)` | 15 | PIB per capita, VAF turismo |")
A("| `(100 mil habitantes)` | 10 | homicídios, tuberculose, hepatite |")
A("| `(100 mil nascidos vivos)` | 6 | mortalidade materna |")
A("| `(mil habitantes)` | 6 | incidência de AIDS |")
A("| `(mil meninas do grupo etário)` | 2 | fecundidade adolescente |")
A("| `(100 mil adultos)` | 2 | agências bancárias |")
A("| `(RAIS)` | 1 | empregos formais (contagem) |")
A("")
A("⚠️ **Escalas diferentes no mesmo ODS 3**: mortalidade neonatal é por *mil* nascidos vivos, "
  "materna por *100 mil*. Um valor de 8,5 e outro de 60,0 não são comparáveis — o BI precisa "
  "carregar a unidade junto do número.")
A("")
A("## 5. Como os arquivos se relacionam")
A("")
A("1. **Não há chaves estrangeiras.** A ligação é sempre por valor textual de `Localidade` + `Ano`.")
A("2. **Cada arquivo contribui com N indicadores independentes** — não há sobreposição de nomes "
  "entre arquivos (verificado: 196 nomes únicos, zero duplicados).")
A("3. **A ponte com o dicionário é o nome exato da coluna**, não a posição: "
  "`Nome da Variável` do dicionário == cabeçalho da coluna nas planilhas (196/196 casam, "
  "mas a **ordem das linhas do dicionário não é a ordem dos arquivos** — fazer join por nome).")
A("4. **Mortalidade é fragmentada em 5 arquivos** (materna, neonatal, <1 ano, <5 anos, taxas). "
  "Um mesmo ano/município aparece em todos; não há duplicidade porque os indicadores são distintos.")
A("5. **ODS 2** aparece em 2 arquivos (desnutrição 1998–2015 e baixo peso 2000–2025): "
  "séries **não sobrepostas** no tempo, mesmo objetivo.")
A("")
A("### 5.1 Consulta canônica")
A("")
A("```sql")
A("-- série de Guarapuava para um indicador")
A("SELECT ano, valor FROM fato_indicador")
A("WHERE localidade = 'Guarapuava' AND indicador = '<nome exato>';")
A("")
A("-- ranking dos municípios em 2023 (exclui agregados)")
A("SELECT localidade, valor FROM fato_indicador")
A("WHERE indicador = '<nome>' AND ano = 2023")
A("  AND localidade NOT LIKE 'RGInt%' AND localidade <> 'Estado do Paraná';")
A("```")
A("")
A("## 6. Catálogo de arquivos")
A("")
A("| # | ODS | Arquivo | Cols | Período | Ausentes | RGInt |")
A("|---:|---:|---|---:|---|---:|---|")
for i, (arq, cs) in enumerate(arquivos.items(), 1):
    c0 = cs[0]
    aus = sum(c["pct_ausente"] for c in cs) / len(cs)
    A(f"| {i} | {c0['ods']} | {arq} | {len(cs)} | {fmt_anos(c0['ano_min'], c0['ano_max'])} | "
      f"{aus:.0f}% | {'sim' if c0['tem_agregado_regional'] else '—'} |")

A("")
A("## 7. Catálogo de indicadores (196)")
A("")
A("Legenda: `Cob.` = % de células ausentes na série completa; `Anos` = primeiro–último ano com valor.")
A("")
A("| # | ODS | Grupo | Indicador | Código | Anos | Cob. |")
A("|---:|---:|---|---|---|---|---:|")
for i, c in enumerate(cat, 1):
    A(f"| {i} | {c['ods']} | {c['grupo_tema'].split(' - ', 1)[-1]} | {curto(c['indicador'])} | "
      f"`{c['codigo_ods']}` | {fmt_anos(c['ano_min'], c['ano_max'])} | {c['pct_ausente']:.0f}% |")

A("")
A("## 8. Armadilhas e qualidade dos dados")
A("")
A("| # | Problema | Evidência | Impacto | Mitigação |")
A("|---:|---|---|---|---|")
A("| 1 | **Escalas heterogêneas** | neonatal em *mil* nascidos vivos vs materna em *100 mil*; PIB em R$ 1,00 e R$ 1.000,00 | comparação direta enganosa | exibir unidade em cada card |")
A("| 2 | **Indicador ≠ % sempre** | `Empregos (RAIS)`, `PIB`, `Consumidores`, `Número de Óbitos` são contagens absolutas | ranking por “maior %” fica errado | flag `tipo`: `taxa` / `proporcao` / `contagem` / `moeda` |")
A("| 3 | **Ausência codificada como texto** | 70 mil `...` + 11 mil `-` | `read_excel` traz `object`; somas silenciosamente ignoram | converter para nulo no ETL (feito) |")
A("| 4 | **2 indicadores 100% vazios** | “Docências com Formação Superior Adequada” (2 recortes) | gráfico vazio | ocultar automaticamente quando sem dados |")
A("| 5 | **Cobertura baixa em recortes raciais** | Amarela 74%, Indígena 84%, AIDS-Mulheres 60–99% | média distorcida, série quebrada | mostrar `n` disponível / esconder recortes com <X% |")
A("| 6 | **RGInt só em 148/196** | ver §3.1 | agregado regional indisponível em 48 | esconder nível regional quando ausente |")
A("| 7 | **Séries com janelas diferentes** | 1997–2025 (mortalidade) vs 2014–2016 (proficiência 3º ano) | comparação multi-indicador enganosa | eixo X sempre por ano real, nunca índice |")
A("| 8 | **ODS 5 só em anos eleitorais** | 2012/2016/2020/2024 | linha contínua sugere interpolação | usar barras/pontos |")
A("| 9 | **Sem população por município** | não existe coluna | impossível recalcular taxas ou ponderar médias | usar taxas já calculadas na fonte; não agregar municípios |")
A("| 10 | **Sem código IBGE / malha** | só nome | mapa coroplético exige de-para externo | decidir em §9, Q6 |")
A("| 11 | **2025 pode ser preliminar** | 163 indicadores com 2025 | risco de ler queda como tendência | marcar “dados sujeitos a revisão” |")
A("| 12 | **`Assunto` redundante** | constante por arquivo | 1,6 M de strings repetidas | descartar no ETL e derivar de `dim_indicador` |")
A("")
A("## 9. Decisões pendentes (bloqueiam o desenho do BI)")
A("")
A("1. **Polaridade de cada indicador** — o dicionário não diz se “maior é melhor”. "
  "Necessário para colorir scorecards (verde/vermelho) e calcular gaps.")
A("2. **Benchmark** — comparar Guarapuava com Paraná, com a RGInt, com a mediana dos municípios "
  "ou com o melhor município? Define o KPI de cada card.")
A("3. **Agregado regional ausente** — 48 indicadores não têm RGInt; o de-para do IBGE permite "
  "saber a região de cada município, mas sem população não há como calcular média ponderada.")
A("4. **Curadoria** — exibir os 196 (decisão tomada) ou um conjunto de ~40 indicadores-síntese?")
A("5. **Escopo de recortes** — cor/raça e sexo entram no BI ou ficam fora da v1?")
A("6. **Mapa** — incluir coroplético (exige GeoJSON/malha do Paraná) ou só rankings e barras?")
A("7. **Série 2025** — tratar como definitiva ou como preliminar?")

with open(os.path.join(ROOT, "DATA_SCHEMA.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")
print(f"DATA_SCHEMA.md gerado com {len(L)} linhas, {len(cat)} indicadores.")
