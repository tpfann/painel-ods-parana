# DATA_SCHEMA — Painel ODS · Paraná

> Documento gerado automaticamente por `scripts/02_gen_schema.py` a partir de `scripts/01_build_catalog.py`. Não editar à mão.

## 1. Inventário

| Item | Valor |
|---|---|
| Planilhas de dados | **38** `.xlsx` (pasta `Base de Dados/`) |
| Dicionário | 1 `.xlsx` (pasta `Dicionário/`) — **196 linhas**, uma por indicador |
| Indicadores (colunas de valor) | **196** |
| Observações com valor | **1.283.762** de 1.622.676 células (79,1% de preenchimento) |
| Localidades | **406** → 399 municípios + `Estado do Paraná` + 6 `RGInt de …` |
| Período | **1997 – 2025** (varia por indicador) |
| Unidade territorial | Estado do Paraná (foco: **Guarapuava**) |

> Observação: a premissa inicial falava em “20 arquivos”; o conjunto real tem **38** planilhas (uma por tema/indicador, algumas com várias colunas internas).

## 2. Formato canônico de todas as planilhas

```
A1: Assunto | B1: Localidade | C1: Ano | D1..N1: <nome do indicador>   (1 a 36 colunas)
A2..: texto  | nome do local | 2010 (numérico) | valor (numérico)
```

- Formato **longo**: cada linha é uma observação `localidade × ano`.
- A coluna `Assunto` é **constante dentro do arquivo** (repete o tema em todas as linhas).
- As colunas `D..N` são **indicadores distintos** (não são medidas repetidas do mesmo indicador).
- Não existe coluna de população, território ou região — ver §8.
- Algumas planilhas têm colunas-fantasma `None` à direita (cabeçalho vazio); devem ser descartadas.

### 2.1 Códigos de ausência

| Código | Onde aparece | Tratamento |
|---|---|---|
| `...` | saúde, vacinação, AIDS | nulo |
| `-` | RAIS, educação, PIB | nulo |
| célula vazia | casos isolados | nulo |

Não há `0` usado como ausente: zeros são **valores reais** (ex.: 0 óbitos). Isso é crítico para séries de mortalidade — 0 deve ser plotado, `...` deve virar lacuna.

## 3. Dimensões

### 3.1 `Localidade` (406 valores)

| Tipo | Quantidade | Exemplo | Papel no BI |
|---|---|---|---|
| Estado | 1 | `Estado do Paraná` | benchmark estadual |
| Região Geográfica Intermediária | 6 | `RGInt de Guarapuava` | agregação regional |
| Município | 399 | `Guarapuava` | nível de análise principal |

As 6 RGInt presentes são exatamente as **Regiões Geográficas Intermediárias** do IBGE (de-para confirmado: 6/6): **Cascavel, Curitiba, Guarapuava, Londrina, Maringá, Ponta Grossa**. São agregados **pré-calculados na fonte**, presentes em **148 dos 196** indicadores. Nos outros 48 o agregado regional não existe no arquivo.

> ✅ O de-para `município → região intermediária` **foi obtido da API de localidades do IBGE** e está em `data/geo/ibge_municipios.json` (399/399 nomes casam exatamente). Ainda assim **não é possível recalcular** médias regionais para os 48 indicadores ausentes: os dados não trazem população, então não há como ponderar. (Ver §8, item 9.)

Grafia dos municípios é consistente entre arquivos (mesmo conjunto de 399 nomes, comparação exata funciona). Nomes não têm código IBGE.

### 3.2 `Ano`

- Inteiro, 1997–2025. **Não é uma série contínua por indicador** — cada um tem sua janela.
- 163 dos 196 indicadores chegam a 2025; os demais param antes (PIB em 2023, VAB indústria em 2021, proficiência do 3º ano em 2016 etc.).
- Anos eleitorais (ODS 5) só existem em 2012/2016/2020/2024 — gráfico de linha deve ser tratado como **pontos discretos**, não tendência.

### 3.3 `Assunto`

Constante por arquivo. Equivale a `ODS N - <tema>` e serve como rótulo de seção. Não é uma dimensão analítica — o agrupamento real está em §4.

## 4. Modelo relacional proposto (star schema)

```
                     dim_tempo (ano)
                            │
dim_localidade ──── fato_indicador ──── dim_indicador
 (id, nome, tipo)     (localidade_id,      (id, ods, grupo,
                       ano, indicador_id,   subgrupo, recorte,
                       valor)               unidade, polaridade)
```

**Grão da fato:** uma linha por `(localidade, ano, indicador)`. Total esperado = 406 × anos_do_indicador; o que falta é ausência real (códigos `...`/`-`).

### 4.1 Decomposição do nome do indicador

Os 196 nomes seguem o padrão:

```
ODS - Objetivo <N> - <GRUPO> - <MEDIDA> - <RECORTE> (<UNIDADE>)
```

| Campo | Exemplo | Uso no BI |
|---|---|---|
| `ods` | `3` | filtro de objetivo |
| `grupo` | `Mortalidade Neonatal` | card / seção |
| `medida` | `Taxa de Mortalidade Neonatal` vs `Número de Óbitos Neonatais` | métrica vs volume |
| `recorte` | `Total`, `Cor/Raça Branca`, `Masculino`, `Urbano` | dimensão de desagregação |
| `unidade` | `%`, `100 mil hab.`, `mil nascidos vivos`, `R$` | formatação |

Esse é o ponto mais importante do modelo: **`Total` é o indicador-síntese**; as demais colunas são o mesmo fenômeno quebrado por cor/raça, sexo ou área. O BI deve mostrar o `Total` por padrão e oferecer o recorte como detalhe — nunca somar recortes com o Total.

Distribuição do campo `recorte` nos 196 indicadores:

| Recorte | Qtd |
|---|---:|
| sem recorte (indicador único) | 75 |
| `Total` (síntese de um grupo com recortes) | 25 |
| `Cor/Raça Branca` / `Preta` / `Amarela` / `Parda` / `Indígena` | 16 cada (80) |
| `Masculino` / `Feminino` | 6 cada (12) |
| `Rural` | 4 |

### 4.2 Unidades e escalas

| Unidade no nome | Qtd | Exemplo |
|---|---:|---|
| `(%)` | 85 | cobertura vacinal, proporções |
| sem sufixo | 39 | contagens (óbitos, unidades atendidas, consumidores) |
| `(mil nascidos vivos)` | 30 | mortalidade neonatal/infantil |
| `(R$ 1,00)` / `(R$ 1.000,00)` | 15 | PIB per capita, VAF turismo |
| `(100 mil habitantes)` | 10 | homicídios, tuberculose, hepatite |
| `(100 mil nascidos vivos)` | 6 | mortalidade materna |
| `(mil habitantes)` | 6 | incidência de AIDS |
| `(mil meninas do grupo etário)` | 2 | fecundidade adolescente |
| `(100 mil adultos)` | 2 | agências bancárias |
| `(RAIS)` | 1 | empregos formais (contagem) |

⚠️ **Escalas diferentes no mesmo ODS 3**: mortalidade neonatal é por *mil* nascidos vivos, materna por *100 mil*. Um valor de 8,5 e outro de 60,0 não são comparáveis — o BI precisa carregar a unidade junto do número.

## 5. Como os arquivos se relacionam

1. **Não há chaves estrangeiras.** A ligação é sempre por valor textual de `Localidade` + `Ano`.
2. **Cada arquivo contribui com N indicadores independentes** — não há sobreposição de nomes entre arquivos (verificado: 196 nomes únicos, zero duplicados).
3. **A ponte com o dicionário é o nome exato da coluna**, não a posição: `Nome da Variável` do dicionário == cabeçalho da coluna nas planilhas (196/196 casam, mas a **ordem das linhas do dicionário não é a ordem dos arquivos** — fazer join por nome).
4. **Mortalidade é fragmentada em 5 arquivos** (materna, neonatal, <1 ano, <5 anos, taxas). Um mesmo ano/município aparece em todos; não há duplicidade porque os indicadores são distintos.
5. **ODS 2** aparece em 2 arquivos (desnutrição 1998–2015 e baixo peso 2000–2025): séries **não sobrepostas** no tempo, mesmo objetivo.

### 5.1 Consulta canônica

```sql
-- série de Guarapuava para um indicador
SELECT ano, valor FROM fato_indicador
WHERE localidade = 'Guarapuava' AND indicador = '<nome exato>';

-- ranking dos municípios em 2023 (exclui agregados)
SELECT localidade, valor FROM fato_indicador
WHERE indicador = '<nome>' AND ano = 2023
  AND localidade NOT LIKE 'RGInt%' AND localidade <> 'Estado do Paraná';
```

## 6. Catálogo de arquivos

| # | ODS | Arquivo | Cols | Período | Ausentes | RGInt |
|---:|---:|---|---:|---|---:|---|
| 1 | 1 | ODS - Objetivo 01 - Proporção de Despesas Públicas com Educação e Seguridade.xlsx | 1 | 2010–2025 | 0% | sim |
| 2 | 2 | ODS - Objetivo 02 - Proporção de Crianças Desnutridas com até dois Anos de Idade.xlsx | 1 | 1998–2015 | 6% | sim |
| 3 | 2 | ODS - Objetivo 02 - Proporção de Nascidos Vivos com Baixo Peso ao Nascer.xlsx | 6 | 2000–2025 | 32% | sim |
| 4 | 3 | ODS - Objetivo 03 - Cobertura Vacinal.xlsx | 12 | 1997–2025 | 36% | — |
| 5 | 3 | ODS - Objetivo 03 - Mortalidade Materna.xlsx | 12 | 2000–2025 | 16% | sim |
| 6 | 3 | ODS - Objetivo 03 - Mortalidade Neonatal.xlsx | 36 | 2000–2025 | 16% | sim |
| 7 | 3 | ODS - Objetivo 03 - Mortalidade em Menores de 1 ano de Idade.xlsx | 12 | 2000–2025 | 16% | sim |
| 8 | 3 | ODS - Objetivo 03 - Mortalidade em Menores de 5 anos de Idade.xlsx | 12 | 2000–2025 | 16% | sim |
| 9 | 3 | ODS - Objetivo 03 - Número de Profissionais de Saúde.xlsx | 5 | 2007–2025 | 0% | sim |
| 10 | 3 | ODS - Objetivo 03 - Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal.xlsx | 6 | 2001–2025 | 32% | sim |
| 11 | 3 | ODS - Objetivo 03 - Proporção dos Casos de AIDS entre Mulheres.xlsx | 6 | 2000–2024 | 82% | sim |
| 12 | 3 | ODS - Objetivo 03 - Taxa de Incidência de AIDS.xlsx | 1 | 1997–2024 | 0% | sim |
| 13 | 3 | ODS - Objetivo 03 - Taxa de Incidência de Hepatite B.xlsx | 1 | 2007–2023 | 0% | sim |
| 14 | 3 | ODS - Objetivo 03 - Taxa de Incidência de Tuberculose.xlsx | 1 | 2001–2025 | 0% | sim |
| 15 | 3 | ODS - Objetivo 03 - Taxa de Nascidos Vivos de Mães Adolescentes.xlsx | 2 | 2011–2025 | 0% | sim |
| 16 | 3 | ODS - Objetivo 03 - Taxas de Mortalidade.xlsx | 6 | 1997–2025 | 0% | sim |
| 17 | 4 | ODS - Objetivo 04 - Infraestrutura nas Escolas.xlsx | 5 | 2015–2025 | 25% | sim |
| 18 | 4 | ODS - Objetivo 04 - Nível de Proficiência de Estudantes do Terceiro Ano Fundamental.xlsx | 3 | 2014–2016 | 2% | — |
| 19 | 4 | ODS - Objetivo 04 - Nível de Proficiência de Estudantes dos Anos Iniciais e Finais.xlsx | 12 | 2015–2025 | 25% | — |
| 20 | 4 | ODS - Objetivo 04 - Proporção de Pessoas de 4 a 5 anos Matriculados na Pré-Escola.xlsx | 1 | 2014–2020 | 0% | — |
| 21 | 4 | ODS - Objetivo 04 - Proporção de Professores com Formação Superior Adequada.xlsx | 20 | 2013–2025 | 46% | — |
| 22 | 5 | ODS - Objetivo 05 - Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores.xlsx | 6 | 2012–2024 | 58% | sim |
| 23 | 5 | ODS - Objetivo 05 - Proporção de Mulheres em Posições Gerenciais - RAIS.xlsx | 1 | 2010–2025 | 2% | sim |
| 24 | 6 | ODS - Objetivo 06 - Abastecimento de Água - Unidade Atendidas Residenciais.xlsx | 1 | 2010–2024 | 2% | sim |
| 25 | 6 | ODS - Objetivo 06 - Atendimento de Esgoto - Unidade Atendidas Residenciais.xlsx | 1 | 2010–2024 | 47% | sim |
| 26 | 7 | ODS - Objetivo 07 - Energia Elétrica Residencial - Consumidores.xlsx | 1 | 2010–2025 | 0% | sim |
| 27 | 8 | ODS - Objetivo 08 - Emprego (RAIS).xlsx | 1 | 2010–2025 | 0% | sim |
| 28 | 8 | ODS - Objetivo 08 - Número Agências Bancárias e Postos de Atendimento Eletrônico.xlsx | 2 | 2011–2025 | 0% | sim |
| 29 | 8 | ODS - Objetivo 08 - Produto Interno Bruto (PIB).xlsx | 2 | 2002–2023 | 0% | sim |
| 30 | 8 | ODS - Objetivo 08 - Proporção de Empregos nas Atividades Características do Turismo.xlsx | 1 | 2010–2023 | 0% | sim |
| 31 | 8 | ODS - Objetivo 08 - Rendimento Nominal Médio por Hora.xlsx | 12 | 2010–2025 | 5% | sim |
| 32 | 8 | ODS - Objetivo 08 - Valor Adicionado Fiscal nas Atividades Características do Turismo.xlsx | 1 | 2010–2024 | 0% | sim |
| 33 | 9 | ODS - Objetivo 09 - Emprego no Setor de Indústria como Percentual do Emprego Total.xlsx | 1 | 2002–2025 | 0% | sim |
| 34 | 9 | ODS - Objetivo 09 - Percentual do Valor Adicionado na Indústria sobre o PIB.xlsx | 1 | 2002–2021 | 0% | sim |
| 35 | 13 | ODS - Objetivo 13 - Número de Mortos, Desaparecidos e Diretamente Afetados Atribuído a Desastres.xlsx | 1 | 2011–2025 | 0% | sim |
| 36 | 15 | ODS - Objetivo 15 - Área de Remanescente Florestal como Proporção da Área Territorial.xlsx | 1 | 2012–2025 | 0% | sim |
| 37 | 16 | ODS - Objetivo 16 - Proporção de Nascidos Vivos Registrados por uma Autoridade Civil.xlsx | 1 | 2015–2024 | 0% | sim |
| 38 | 16 | ODS - Objetivo 16 - Taxa de Mortalidade por Homicídios.xlsx | 1 | 1997–2025 | 0% | sim |

## 7. Catálogo de indicadores (196)

Legenda: `Cob.` = % de células ausentes na série completa; `Anos` = primeiro–último ano com valor.

| # | ODS | Grupo | Indicador | Código | Anos | Cob. |
|---:|---:|---|---|---|---|---:|
| 1 | 1 | Proporção do Total das Despesas Públicas Municipais com Educação e Seguridade Social | Proporção do Total das Despesas Públicas Municipais com Educação e Seguridade Social (%) | `1.a.2.A` | 2010–2025 | 0% |
| 2 | 2 | Proporção de Crianças Desnutridas com até dois Anos de Idade | Proporção de Crianças Desnutridas com até dois Anos de Idade (%) | `2.1.1.A` | 1998–2015 | 6% |
| 3 | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Total (%) | `2.2.2.A` | 2000–2025 | 0% |
| 4 | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Branca (%) | `2.2.2.A` | 2000–2025 | 0% |
| 5 | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Preta (%) | `2.2.2.A` | 2000–2025 | 30% |
| 6 | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Amarela (%) | `2.2.2.A` | 2000–2025 | 74% |
| 7 | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Parda (%) | `2.2.2.A` | 2000–2025 | 7% |
| 8 | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Indígena (%) | `2.2.2.A` | 2000–2025 | 84% |
| 9 | 3 | Cobertura Vacinal | Cobertura Vacinal - BCG (Tuberculose) (%) | `3.b.1` | 1997–2025 | 0% |
| 10 | 3 | Cobertura Vacinal | Cobertura Vacinal - Hepatite A (HA) (%) | `3.b.1` | 2014–2025 | 59% |
| 11 | 3 | Cobertura Vacinal | Cobertura Vacinal - Hepatite B (HB) (%) | `3.b.1` | 1997–2024 | 3% |
| 12 | 3 | Cobertura Vacinal | Cobertura Vacinal - Hepatite B em Menores de 1 mês (HB < 1m) (%) | `3.b.1` | 2014–2025 | 59% |
| 13 | 3 | Cobertura Vacinal | Cobertura Vacinal - Rotavírus Humano (VORH) (%) | `3.b.1` | 2006–2025 | 31% |
| 14 | 3 | Cobertura Vacinal | Cobertura Vacinal - Meningocócica Conjugada (Men C) (%) | `3.b.1` | 2010–2025 | 45% |
| 15 | 3 | Cobertura Vacinal | Cobertura Vacinal - Penta Bacteriana (Pentavalente) (DTP+Hib+HB) (PENTA) (%) | `3.b.1` | 2012–2025 | 52% |
| 16 | 3 | Cobertura Vacinal | Cobertura Vacinal - Pneumocócica 10V (Pncc10V) (%) | `3.b.1` | 2010–2025 | 45% |
| 17 | 3 | Cobertura Vacinal | Cobertura Vacinal - Poliomielite (VOP) (%) | `3.b.1` | 1997–2024 | 3% |
| 18 | 3 | Cobertura Vacinal | Cobertura Vacinal - Tríplice Viral (SCR) (%) | `3.b.1` | 2000–2025 | 10% |
| 19 | 3 | Cobertura Vacinal | Cobertura Vacinal - Tetra Viral (SCR+VZ) (%) | `3.b.1` | 2013–2022 | 66% |
| 20 | 3 | Cobertura Vacinal | Cobertura Vacinal - Tríplice Acelular Gestante (dTpa) (%) | `3.b.1` | 2013–2025 | 55% |
| 21 | 3 | Mortalidade Materna | Número de Óbitos Maternos - Total | `3.1.1` | 2000–2025 | 0% |
| 22 | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Branca | `3.1.1` | 2000–2025 | 0% |
| 23 | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Preta | `3.1.1` | 2000–2025 | 0% |
| 24 | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Amarela | `3.1.1` | 2000–2025 | 0% |
| 25 | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Parda | `3.1.1` | 2000–2025 | 0% |
| 26 | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Indígena | `3.1.1` | 2000–2025 | 0% |
| 27 | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Total (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 0% |
| 28 | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Branca (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 0% |
| 29 | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Preta (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 30% |
| 30 | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Amarela (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 74% |
| 31 | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Parda (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 7% |
| 32 | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Indígena (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 84% |
| 33 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Total | `3.2.2` | 2000–2025 | 0% |
| 34 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Branca | `3.2.2` | 2000–2025 | 0% |
| 35 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Preta | `3.2.2` | 2000–2025 | 0% |
| 36 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Amarela | `3.2.2` | 2000–2025 | 0% |
| 37 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Parda | `3.2.2` | 2000–2025 | 0% |
| 38 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Indígena | `3.2.2` | 2000–2025 | 0% |
| 39 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Total (mil nascidos vivos) | `3.2.2` | 2000–2025 | 0% |
| 40 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Branca (mil nascidos vivos) | `3.2.2` | 2000–2025 | 0% |
| 41 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Preta (mil nascidos vivos) | `3.2.2` | 2000–2025 | 30% |
| 42 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Amarela (mil nascidos vivos) | `3.2.2` | 2000–2025 | 74% |
| 43 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Parda (mil nascidos vivos) | `3.2.2` | 2000–2025 | 7% |
| 44 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Indígena (mil nascidos vivos) | `3.2.2` | 2000–2025 | 84% |
| 45 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Total | `3.2.2.A` | 2000–2025 | 0% |
| 46 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Branca | `3.2.2.A` | 2000–2025 | 0% |
| 47 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Preta | `3.2.2.A` | 2000–2025 | 0% |
| 48 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Amarela | `3.2.2.A` | 2000–2025 | 0% |
| 49 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Parda | `3.2.2.A` | 2000–2025 | 0% |
| 50 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Indígena | `3.2.2.A` | 2000–2025 | 0% |
| 51 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Total (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 0% |
| 52 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Branca (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 0% |
| 53 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Preta (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 30% |
| 54 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Amarela (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 74% |
| 55 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Parda (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 7% |
| 56 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Indígena (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 84% |
| 57 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Total | `3.2.2.B` | 2000–2025 | 0% |
| 58 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Branca | `3.2.2.B` | 2000–2025 | 0% |
| 59 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Preta | `3.2.2.B` | 2000–2025 | 0% |
| 60 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Amarela | `3.2.2.B` | 2000–2025 | 0% |
| 61 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Parda | `3.2.2.B` | 2000–2025 | 0% |
| 62 | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Indígena | `3.2.2.B` | 2000–2025 | 0% |
| 63 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Total (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 0% |
| 64 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Branca (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 0% |
| 65 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Preta (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 30% |
| 66 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Amarela (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 74% |
| 67 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Parda (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 7% |
| 68 | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Indígena (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 84% |
| 69 | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Total | `3.2.1.A` | 2000–2025 | 0% |
| 70 | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Branca | `3.2.1.A` | 2000–2025 | 0% |
| 71 | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Preta | `3.2.1.A` | 2000–2025 | 0% |
| 72 | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Amarela | `3.2.1.A` | 2000–2025 | 0% |
| 73 | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Parda | `3.2.1.A` | 2000–2025 | 0% |
| 74 | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Indígena | `3.2.1.A` | 2000–2025 | 0% |
| 75 | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Total (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 0% |
| 76 | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Branca (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 0% |
| 77 | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Preta (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 30% |
| 78 | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Amarela (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 74% |
| 79 | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Parda (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 7% |
| 80 | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Indígena (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 84% |
| 81 | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Total | `3.2.1` | 2000–2025 | 0% |
| 82 | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Branca | `3.2.1` | 2000–2025 | 0% |
| 83 | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Preta | `3.2.1` | 2000–2025 | 0% |
| 84 | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Amarela | `3.2.1` | 2000–2025 | 0% |
| 85 | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Parda | `3.2.1` | 2000–2025 | 0% |
| 86 | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Indígena | `3.2.1` | 2000–2025 | 0% |
| 87 | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Total (mil nascidos vivos) | `3.2.1` | 2000–2025 | 0% |
| 88 | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Branca (mil nascidos vivos) | `3.2.1` | 2000–2025 | 0% |
| 89 | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Preta (mil nascidos vivos) | `3.2.1` | 2000–2025 | 30% |
| 90 | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Amarela (mil nascidos vivos) | `3.2.1` | 2000–2025 | 74% |
| 91 | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Parda (mil nascidos vivos) | `3.2.1` | 2000–2025 | 7% |
| 92 | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Indígena (mil nascidos vivos) | `3.2.1` | 2000–2025 | 84% |
| 93 | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Total (mil habitantes) | `3.c.1` | 2007–2025 | 0% |
| 94 | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Médicos (mil habitantes) | `3.c.1.A` | 2007–2025 | 0% |
| 95 | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Enfermeiros (mil habitantes) | `3.c.1.B` | 2007–2025 | 0% |
| 96 | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Dentistas (mil habitantes) | `3.c.1.C` | 2007–2025 | 0% |
| 97 | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Farmacêuticos (mil habitantes) | `3.c.1.D` | 2007–2025 | 0% |
| 98 | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Total (%) | `3.1.2.A` | 2001–2025 | 0% |
| 99 | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Branca (%) | `3.1.2.A` | 2001–2025 | 0% |
| 100 | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Preta (%) | `3.1.2.A` | 2001–2025 | 30% |
| 101 | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Amarela (%) | `3.1.2.A` | 2001–2025 | 74% |
| 102 | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Parda (%) | `3.1.2.A` | 2001–2025 | 6% |
| 103 | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Indígena (%) | `3.1.2.A` | 2001–2025 | 84% |
| 104 | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Total (%) | `3.3.1.A` | 2000–2024 | 60% |
| 105 | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Branca (%) | `3.3.1.A` | 2000–2024 | 65% |
| 106 | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Preta (%) | `3.3.1.A` | 2000–2024 | 91% |
| 107 | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Amarela (%) | `3.3.1.A` | 2000–2024 | 97% |
| 108 | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Parda (%) | `3.3.1.A` | 2000–2024 | 83% |
| 109 | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Indígena (%) | `3.3.1.A` | 2000–2024 | 99% |
| 110 | 3 | Taxa de Incidência de AIDS por ano de Diagnóstico | Taxa de Incidência de AIDS por ano de Diagnóstico (mil habitantes) | `3.3.1` | 1997–2024 | 0% |
| 111 | 3 | Taxa de Incidência de Hepatite B | Taxa de Incidência de Hepatite B (100 mil habitantes) | `3.3.4` | 2007–2023 | 0% |
| 112 | 3 | Taxa de Incidência de Tuberculose | Taxa de Incidência de Tuberculose (100 mil habitantes) | `3.3.2` | 2001–2025 | 0% |
| 113 | 3 | Taxa de Nascidos Vivos de Mães Adolescentes | Taxa de Nascidos Vivos de Mães Adolescentes - 10 a 14 anos de Idade (mil meninas do grupo etário) | `3.7.2` | 2011–2025 | 0% |
| 114 | 3 | Taxa de Nascidos Vivos de Mães Adolescentes | Taxa de Nascidos Vivos de Mães Adolescentes - 15 a 19 anos de Idade (mil meninas do grupo etário) | `3.7.2` | 2011–2025 | 0% |
| 115 | 3 | Taxas de Mortalidade | Taxa de Mortalidade por AIDS (100 mil habitantes) | `3.3.1.B` | 1997–2025 | 0% |
| 116 | 3 | Taxas de Mortalidade | Taxa de Mortalidade Causas Selecionadas - Tuberculose (Todas as Formas) (100 mil habitantes) | `3.3.2.A` | 1997–2025 | 0% |
| 117 | 3 | Taxas de Mortalidade | Taxa de Mortalidade Causas Externas - Lesões Autoprovocadas Intencionalmente (Suicídios) (100 mil habitantes) | `3.4.2` | 1997–2025 | 0% |
| 118 | 3 | Taxas de Mortalidade | Taxa de Mortalidade Causas Externas - Acidentes de Trânsito (Transporte) (100 mil habitantes) | `3.6.1` | 1997–2025 | 0% |
| 119 | 3 | Taxas de Mortalidade | Taxa de Mortalidade Atribuída a Fontes de Água Inseguras, Saneamento Inseguro e Falta de Higiene (100 mil habitantes) | `3.9.2` | 1997–2025 | 0% |
| 120 | 3 | Taxas de Mortalidade | Taxa de Mortalidade Atribuída a Intoxicação não Intencional (100 mil habitantes) | `3.9.3` | 1997–2025 | 0% |
| 121 | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Acesso à Eletricidade (%) | `4.a.1a` | 2015–2025 | 31% |
| 122 | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Acesso à Internet (%) | `4.a.1b` | 2015–2025 | 31% |
| 123 | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Acesso a Computadores para Fins Pedagógicos (%) | `4.a.1c` | 2015–2025 | 31% |
| 124 | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Infraestrutura Adaptada para Alunos com Deficiência (%) | `4.a.1d` | 2010–2025 | 0% |
| 125 | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Abastecimento de Água (%) | `4.a.1e` | 2015–2025 | 31% |
| 126 | 4 | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Leitura (%) | `4.1.1a` | 2014–2016 | 2% |
| 127 | 4 | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Escrita (%) | `4.1.1a` | 2014–2016 | 2% |
| 128 | 4 | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática (%) | `4.1.1a` | 2014–2016 | 2% |
| 129 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Total (%) | `4.1.1b` | 2015–2025 | 1% |
| 130 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Urbana (%) | `4.1.1b` | 2015–2025 | 2% |
| 131 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Rural (%) | `4.1.1b` | 2015–2025 | 70% |
| 132 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Total (%) | `4.1.1b` | 2015–2025 | 1% |
| 133 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Urbana (%) | `4.1.1b` | 2015–2025 | 2% |
| 134 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Rural (%) | `4.1.1b` | 2015–2025 | 70% |
| 135 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Total (%) | `4.1.1c` | 2015–2025 | 2% |
| 136 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Urbana (%) | `4.1.1c` | 2015–2025 | 2% |
| 137 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Rural (%) | `4.1.1c` | 2015–2025 | 72% |
| 138 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Total (%) | `4.1.1c` | 2015–2025 | 2% |
| 139 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Urbana (%) | `4.1.1c` | 2015–2025 | 2% |
| 140 | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Rural (%) | `4.1.1c` | 2015–2025 | 72% |
| 141 | 4 | Proporção de Pessoas de 4 a 5 anos Matriculadas na Pré-Escola | Proporção de Pessoas de 4 a 5 anos Matriculadas na Pré-Escola (%) | `4.2.2.A` | 2014–2020 | 0% |
| 142 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Total (%) | `4.c.1.A` | 2013–2025 | 0% |
| 143 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Federal (%) | `4.c.1.A` | 2013–2019 | 100% |
| 144 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 92% |
| 145 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Municipal (%) | `4.c.1.A` | 2013–2025 | 0% |
| 146 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 22% |
| 147 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Total (%) | `4.c.1.A` | 2013–2025 | 0% |
| 148 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Federal (%) | `4.c.1.A` | — | 100% |
| 149 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 92% |
| 150 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Municipal (%) | `4.c.1.A` | 2013–2025 | 0% |
| 151 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 16% |
| 152 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Total (%) | `4.c.1.A` | 2013–2025 | 0% |
| 153 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Federal (%) | `4.c.1.A` | 2013–2025 | 100% |
| 154 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 0% |
| 155 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Municipal (%) | `4.c.1.A` | 2013–2025 | 66% |
| 156 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 65% |
| 157 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Total (%) | `4.c.1.A` | 2013–2025 | 0% |
| 158 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Federal (%) | `4.c.1.A` | 2013–2025 | 94% |
| 159 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 0% |
| 160 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Municipal (%) | `4.c.1.A` | — | 100% |
| 161 | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 72% |
| 162 | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Total (%) | `5.5.1` | 2012–2024 | 0% |
| 163 | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Branca (%) | `5.5.1` | 2016–2024 | 25% |
| 164 | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Preta (%) | `5.5.1` | 2016–2024 | 79% |
| 165 | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Amarela (%) | `5.5.1` | 2016–2024 | 98% |
| 166 | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Parda (%) | `5.5.1` | 2016–2024 | 50% |
| 167 | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Indígena (%) | `5.5.1` | 2016–2024 | 99% |
| 168 | 5 | Proporção de Mulheres em Posições Gerenciais (RAIS) | Proporção de Mulheres em Posições Gerenciais (RAIS) (%) | `5.5.2.A` | 2010–2025 | 2% |
| 169 | 6 | Abastecimento de Água - Unidades Atendidas Residenciais | Abastecimento de Água - Unidades Atendidas Residenciais | `6.1.1.A` | 2010–2024 | 2% |
| 170 | 6 | Atendimento de Esgoto - Unidades Atendidas Residenciais | Atendimento de Esgoto - Unidades Atendidas Residenciais | `6.2.1.A` | 2010–2024 | 47% |
| 171 | 7 | Energia Elétrica Residencial - Consumidores | Energia Elétrica Residencial - Consumidores | `7.1.1.A` | 2010–2025 | 0% |
| 172 | 8 | Empregos (RAIS) | Empregos (RAIS) | `8.5.2.A` | 2010–2025 | 0% |
| 173 | 8 | Número de Agências Bancárias e Postos de Atendimento Eletrônico (PAE) | Número de Agências Bancárias (100 mil adultos) | `8.10.1a` | 2011–2025 | 0% |
| 174 | 8 | Número de Agências Bancárias e Postos de Atendimento Eletrônico (PAE) | Número de Postos de Atendimento Eletrônico (PAE) (100 mil adultos) | `8.10.1b` | 2011–2025 | 0% |
| 175 | 8 | Produto Interno Bruto (PIB) | Produto Interno Bruto (PIB) a Preços Correntes (R$ 1.000,00) | `8.1.1.A` | 2002–2023 | 0% |
| 176 | 8 | Produto Interno Bruto (PIB) | Produto Interno Bruto (PIB) per Capita (R$ 1,00) | `8.1.2.A` | 2002–2023 | 0% |
| 177 | 8 | Proporção de Empregos (RAIS) nas Atividades Características do Turismo | Proporção de Empregos (RAIS) nas Atividades Características do Turismo (%) | `8.9.2.A` | 2010–2023 | 0% |
| 178 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora - Masculino (R$ 1,00) | `8.5.1.A` | 2010–2025 | 0% |
| 179 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora - Feminino (R$ 1,00) | `8.5.1.A` | 2010–2025 | 0% |
| 180 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora no Comércio - Masculino (R$ 1,00) | `8.5.1.A1` | 2010–2025 | 0% |
| 181 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora no Comércio - Feminino (R$ 1,00) | `8.5.1.A1` | 2010–2025 | 0% |
| 182 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Construção Civil - Masculino (R$ 1,00) | `8.5.1.A2` | 2010–2025 | 11% |
| 183 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Construção Civil - Feminino (R$ 1,00) | `8.5.1.A2` | 2010–2025 | 36% |
| 184 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Indústria - Masculino (R$ 1,00) | `8.5.1.A3` | 2010–2025 | 2% |
| 185 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Indústria - Feminino (R$ 1,00) | `8.5.1.A3` | 2010–2025 | 3% |
| 186 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora em Serviços - Masculino (R$ 1,00) | `8.5.1.A4` | 2010–2025 | 0% |
| 187 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora em Serviços - Feminino (R$ 1,00) | `8.5.1.A4` | 2010–2025 | 0% |
| 188 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Agropecuária - Masculino (R$ 1,00) | `8.5.1.A5` | 2010–2025 | 0% |
| 189 | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Agropecuária - Feminino (R$ 1,00) | `8.5.1.A5` | 2010–2025 | 2% |
| 190 | 8 | Valor Adicionado Fiscal nas Atividades Características do Turismo | Valor Adicionado Fiscal nas Atividades Características do Turismo (R$ 1,00) | `8.9.1.A` | 2010–2024 | 0% |
| 191 | 9 | Emprego no Setor de Indústria como Percentual do Emprego Total | Emprego no Setor de Indústria como Percentual do Emprego Total (%) | `9.2.2` | 2002–2025 | 0% |
| 192 | 9 | Percentual do Valor Adicionado Bruto na Indústria sobre o PIB | Percentual do Valor Adicionado Bruto na Indústria sobre o PIB (%) | `9.2.1` | 2002–2021 | 0% |
| 193 | 13 | Número de Mortes, Pessoas Desaparecidas e Pessoas Diretamente Afetadas Atribuído a Desastres | Número de Mortes, Pessoas Desaparecidas e Pessoas Diretamente Afetadas Atribuído a Desastres (100 mil habitantes) | `13.1.1` | 2011–2025 | 0% |
| 194 | 15 | Área de Remanescente Florestal como Proporção da Área Territorial | Área de Remanescente Florestal como Proporção da Área Territorial (%) | `15.1.1A` | 2012–2025 | 0% |
| 195 | 16 | Proporção de Nascidos Vivos que Tiveram seus Nascimentos Registrados por uma Autoridade Civil | Proporção de Nascidos Vivos que Tiveram seus Nascimentos Registrados por uma Autoridade Civil (%) | `16.9.1.A` | 2015–2024 | 0% |
| 196 | 16 | Taxa de Mortalidade por Homicídios | Taxa de Mortalidade por Homicídios (100 mil habitantes) | `16.1.1` | 1997–2025 | 0% |

## 8. Armadilhas e qualidade dos dados

| # | Problema | Evidência | Impacto | Mitigação |
|---:|---|---|---|---|
| 1 | **Escalas heterogêneas** | neonatal em *mil* nascidos vivos vs materna em *100 mil*; PIB em R$ 1,00 e R$ 1.000,00 | comparação direta enganosa | exibir unidade em cada card |
| 2 | **Indicador ≠ % sempre** | `Empregos (RAIS)`, `PIB`, `Consumidores`, `Número de Óbitos` são contagens absolutas | ranking por “maior %” fica errado | flag `tipo`: `taxa` / `proporcao` / `contagem` / `moeda` |
| 3 | **Ausência codificada como texto** | 70 mil `...` + 11 mil `-` | `read_excel` traz `object`; somas silenciosamente ignoram | converter para nulo no ETL (feito) |
| 4 | **2 indicadores 100% vazios** | “Docências com Formação Superior Adequada” (2 recortes) | gráfico vazio | ocultar automaticamente quando sem dados |
| 5 | **Cobertura baixa em recortes raciais** | Amarela 74%, Indígena 84%, AIDS-Mulheres 60–99% | média distorcida, série quebrada | mostrar `n` disponível / esconder recortes com <X% |
| 6 | **RGInt só em 148/196** | ver §3.1 | agregado regional indisponível em 48 | esconder nível regional quando ausente |
| 7 | **Séries com janelas diferentes** | 1997–2025 (mortalidade) vs 2014–2016 (proficiência 3º ano) | comparação multi-indicador enganosa | eixo X sempre por ano real, nunca índice |
| 8 | **ODS 5 só em anos eleitorais** | 2012/2016/2020/2024 | linha contínua sugere interpolação | usar barras/pontos |
| 9 | **Sem população por município** | não existe coluna | impossível recalcular taxas ou ponderar médias | usar taxas já calculadas na fonte; não agregar municípios |
| 10 | **Sem código IBGE / malha** | só nome | mapa coroplético exige de-para externo | decidir em §9, Q6 |
| 11 | **2025 pode ser preliminar** | 163 indicadores com 2025 | risco de ler queda como tendência | marcar “dados sujeitos a revisão” |
| 12 | **`Assunto` redundante** | constante por arquivo | 1,6 M de strings repetidas | descartar no ETL e derivar de `dim_indicador` |

## 9. Decisões tomadas e pendências abertas

### 9.1 Tomadas (com o cliente)

1. **Polaridade** — proposta automaticamente (+1 melhor / −1 pior / 0 sem juízo); os 12 indicadores principais e as coberturas vacinais foram revisados à mão. **Pendente: validação da lista completa.**
2. **Benchmark** — Paraná + mediana dos 399 municípios + RGInt do município + posição no ranking + top 10.
3. **Agregado regional ausente** — 48 indicadores sem RGInt: o nível regional simplesmente não é exibido.
4. **Curadoria** — exibir os 194 indicadores da v1 (não reduzir para ~40 síntese).
5. **Escopo de recortes** — cor/raça, sexo, rural e urbana entram na v1.
6. **Mapa** — coroplético dos 399 municípios (malha IBGE).
7. **Série 2025** — tratada como definitiva.
8. **Zero × ausente** — `...`/`-` viram ausente (exibido como `—`); `0` é valor real e é plotado/ranqueado como tal. Em indicadores de contagem com muitos zeros simultâneos (ex.: óbitos maternos por cor/raça), a posição é substituída por “empate: N municípios”.
9. **Unidades** — cada indicador mantém a unidade oficial (por 100 mil, por mil, %); não há normalização entre bases.
10. **Último dado** — posições relativas e pontos de atenção usam o **último dado disponível de cada indicador** (o ano aparece em cada linha), não o ano de referência global.
11. **Fonte** — Open Sans empacotada localmente (`assets/fonts/`), pesos 400–600.
12. **Selo de dado antigo** — todo item mostra o ano do dado; anteriores a 2025 ganham selo âmbar (definido em 21/10/2026).
13. **Ano global** — o seletor da barra superior vale só para Explorador e Comparador; na Visão geral fica desativado (e o dado exibido é sempre o último disponível).
14. **Moeda** — exibição na unidade oficial do arquivo (“R$ mil” para `R$ 1.000,00`), sem converter para reais.
15. **Card de síntese no topo** — substitui o “último ano da base” por um **semáforo de ODS**: percentil médio do município nos indicadores comparáveis de cada ODS, com verde = acima da mediana, vermelho = abaixo e cinza = ODS sem indicador comparável.
16. **Mapa** — dois seletores rotulados (“ODS” / “Indicador”), **empilhados** com a mesma largura, só com indicadores oficiais já proporcionalizados e recorte `Total`.
17. **Layout** — barra superior de 78 px de altura, 28 px entre título/menu/seletores e 40 px até o conteúdo (definido em 21/10/2026).
18. **Cobertura desigual dos ODS** — mantida como está, sem marcação especial na tela; a cobertura aparece na contagem de cada ODS nos seletores (definido em 21/10/2026).
19. **Séries desatualizadas** — além do selo âmbar por item, o Explorador mostra um aviso destacado quando o último dado tem **3 anos ou mais** de defasagem em relação a 2025 (ex.: Proficiência 3º ano = 2016, VAB indústria = 2021).
20. **Filtros** — no Explorador, a lista é filtrada por um seletor de ODS com a descrição completa; no Comparador, ODS e indicador são dois seletores separados (o ODS reduz a lista de indicadores).

### 9.2 Abertas (aguardando definição)

1. **Validação da polaridade** — resolvido por ferramenta: a aba **Revisão** do protótipo permite marcar os 194 indicadores um a um (menor é melhor / sem juízo / maior é melhor); as escolhas ficam em `localStorage` e saem em `polaridade.json` pelo botão de exportação, que vira o padrão de `pol` em `scripts/03_build_bi.py`. Falta apenas o usuário percorrer a lista.
2. **Contagens proporcionais** — resolvido com a população do IBGE (`scripts/04_build_populacao.py` → `data/bi/populacao.js`): a contagem pode ser vista como **taxa calculada por 100 mil habitantes** no Explorador e no Comparador (seletor *Total / por 100 mil hab.\**). Vale apenas para contagens cujo numerador conta **pessoas/eventos** (óbitos, casos, matrículas, vínculos: 37 dos 40). Contagens de outra natureza — *unidades atendidas* (água/esgoto), *consumidores* (energia) — ficam **no absoluto**, sem taxa calculada (definido pelo usuário em 21/10/2026). Por isso o mapa e os cartões de ODS continuam só com indicadores oficiais já proporcionalizados; ODS 6 e 7 não têm mapa.
3. **Contagens em destaques** — permanecem fora de “melhores posições / pontos de atenção” (definido pelo usuário em 21/10/2026): volume absoluto não tem juízo bom/ruim e a taxa seria dado calculado.
4. **Cobertura desigual dos ODS** — resolvido: fica como está, com a contagem visível em cada ODS nos seletores (decidido em 21/10/2026).
5. **Rótulos curtos** (`gcurto`, 38 temas) — aprovados em 21/10/2026.
6. **Dados desatualizados** — resolvido: ano visível em todos os itens, selo âmbar quando anterior a 2025 e aviso destacado no Explorador a partir de 3 anos de defasagem.
7. **Ano global** — resolvido: o seletor da barra superior vale só para Explorador e Comparador (fica oculto em Visão geral); quando o ano escolhido não tem dado, o BI usa o último anterior e sinaliza com selo âmbar.
8. **Moeda** — resolvido: exibição na unidade oficial do arquivo (“R$ mil” para `R$ 1.000,00`), sem converter para reais.
9. **Mapa** — recorte (`Total`/`Urbana`/`Rural` e cor/raça) fica fora do coroplético: só `Total` (definido pelo usuário em 21/10/2026). Os recortes seguem disponíveis no Explorador e no Comparador.

### 9.3 População usada como denominador

`data/bi/populacao.js` (58 KB) traz `BI.pop = {anos, valores}` na mesma ordem de `BI.indice.localidades`, achatado por `[localidade × 26 anos + ano]`:

| Fonte | Anos | Observação |
| --- | --- | --- |
| IBGE agregado 6579 / variável 9324 (estimativas) | 2001–2006, 2008, 2009, 2011–2021, 2024–2026 | publicados pelo IBGE |
| IBGE agregado 4714 / variável 93 (Censo 2022) | 2022 | 11.444.380 no Paraná, confere com o Censo |
| interpolação linear entre vizinhos | 2007, 2010, 2023 | anos sem publicação |

Estado e RGInt são a **soma dos municípios** que os compõem (RGInt: Londrina 94, Curitiba 45, Maringá 115, Cascavel 100, Ponta Grossa 26, Guarapuava 19).
