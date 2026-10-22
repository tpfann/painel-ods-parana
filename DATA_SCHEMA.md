# DATA_SCHEMA — Painel ODS · Paraná

> Documento **gerado** por `scripts/02_gen_schema.py` a partir de `scripts/01_build_catalog.py` e `scripts/03_build_bi.py`. Não editar à mão.
> As decisões do projeto (com o cliente) estão em **[DECISOES.md](DECISOES.md)** — esse arquivo é curado à mão e não é sobrescrito por este script.

| Build | Gerado em | Regras |
|---|---|---|
| `e899e18ea4f9` | 2026-10-22 11:07 | 2026-10-21 |

## 1. Inventário

| Item | Valor |
|---|---|
| Planilhas de dados | **38** `.xlsx` (pasta `Base de Dados/`) |
| Dicionário | 1 `.xlsx` (pasta `Dicionário/`) — **196** variáveis |
| Indicadores na base | **196** (dos quais **198** têm dados e entram no BI) |
| Observações com valor | **1,283,762** de 1,622,676 células (79.1% de preenchimento) |
| Localidades | **406** → 399 municípios + `Estado do Paraná` + 6 `RGInt de …` |
| Período | **1997 – 2025** (varia por indicador) |
| Indicadores com dado em 2025 | 164 de 198 |
| Unidade territorial | Estado do Paraná (foco: **Guarapuava**) |

## 2. Formato canônico de todas as planilhas

```
A1: Assunto | B1: Localidade | C1: Ano | D..N1: <nome do indicador>   (1 a 36 colunas)
A2..: texto  | nome do local | 2010 (numérico) | valor (numérico)
```

- Formato **longo**: uma linha por `localidade × ano`.
- A coluna `Assunto` é constante dentro do arquivo.
- As colunas `D..N` são **indicadores distintos** (não medidas repetidas).
- Não existe coluna de população, território ou região — a população vem do IBGE (§8).

### 2.1 Códigos de ausência

| Código | Onde aparece | Tratamento |
|---|---|---|
| `...` | saúde, vacinação, AIDS | nulo |
| `-` | RAIS, educação, PIB | nulo |
| `..` | idem | nulo |
| célula vazia | casos isolados | nulo |

Não há `0` usado como ausente: zeros são **valores reais** (ex.: 0 óbitos). Isso é crítico para séries de mortalidade — 0 deve ser plotado, `...` deve virar lacuna.

## 3. Dimensões

### 3.1 `Localidade`

| Tipo | Quantidade | Papel no BI |
|---|---:|---|
| Estado | 1 | benchmark estadual |
| Região Geográfica Intermediária | 6 | agregação regional |
| Município | 399 | nível de análise principal |

As RGInt são exatamente as **Regiões Geográficas Intermediárias** do IBGE (de-para confirmado por `scripts/00_build_geo.py`, com asserção): Cascavel, Curitiba, Guarapuava, Londrina, Maringá, Ponta Grossa.

Os agregados regionais são **pré-calculados na fonte** e existem apenas em parte dos indicadores; nos demais o nível regional simplesmente não é exibido.

### 3.2 `Ano`

- Inteiro, 1997–2025. **Não é uma série contínua por indicador** — cada um tem sua janela.
- Séries com anos faltantes (ex.: ODS 5 só em anos eleitorais) **não** podem ser lidas como linha contínua: o app desenha pontos em anos sem vizinho.

### 3.3 `Assunto`

Constante por arquivo. Equivale a `ODS N - <tema>` e serve de rótulo de seção. Não é uma dimensão analítica — o agrupamento real está em §4.

## 4. Modelo dos indicadores

```
ODS - Objetivo <N> - <GRUPO> - <MEDIDA> - <RECORTE> (<UNIDADE>)
```

| Campo | Exemplo | Uso no BI |
|---|---|---|
| `ods` | `3` | filtro de objetivo |
| `grupo` | `Mortalidade Neonatal` | seção / cartão |
| `medida` | `Taxa de Mortalidade Neonatal` vs `Número de Óbitos Neonatais` | métrica vs volume |
| `recorte` | `Total`, `Cor/Raça Branca`, `Masculino`, `Urbano` | desagregação |
| `unidade` | `%`, `100 mil hab.`, `mil nascidos vivos`, `R$` | formatação |

**`Total` é o indicador-síntese**; as demais colunas são o mesmo fenômeno quebrado por cor/raça, sexo ou área. O BI mostra o `Total` e oferece o recorte como detalhe — nunca soma recorte com Total.

Distribuição do campo `recorte` nos indicadores do BI:

| Recorte | Qtd |
|---|---:|
| `sem recorte` | 70 |
| `Total` | 28 |
| `Cor/Raça Amarela` | 16 |
| `Cor/Raça Branca` | 16 |
| `Cor/Raça Indígena` | 16 |
| `Cor/Raça Parda` | 16 |
| `Cor/Raça Preta` | 16 |
| `Feminino` | 6 |
| `Masculino` | 6 |
| `Rural` | 4 |
| `Urbana` | 4 |

### 4.1 Unidades e escalas

| Unidade | Qtd |
|---|---:|
| `%` | 86 |
| `óbitos` | 36 |
| `mil nascidos vivos` | 30 |
| `R$ 1,00` | 14 |
| `100 mil habitantes` | 11 |
| `100 mil nascidos vivos` | 6 |
| `mil habitantes` | 6 |
| `100 mil adultos` | 2 |
| `mil meninas do grupo etário` | 2 |
| `unidades` | 2 |
| `R$ 1.000,00` | 1 |
| `RAIS` | 1 |
| `consumidores` | 1 |

⚠️ **Escalas diferentes dentro do mesmo ODS 3**: mortalidade neonatal é por *mil* nascidos vivos, materna por *100 mil*. Um valor de 8,5 e outro de 60,0 não são comparáveis — o BI carrega a unidade junto do número e nunca converte.

## 5. Chaves e identidade

| Chave | Onde | Estabilidade |
|---|---|---|
| `chave` | nome original da coluna de origem (`chave` no `indice.js`) | **estável**: não depende da ordem do catálogo |
| `id` | hash curto de 8 caracteres da `chave` | estável, curto (DOM/JS) |
| `BI.build.id` | manifesto do payload | muda quando dados ou regras mudam |

A revisão de polaridade é exportada **por `chave`**, nunca por `id` posicional: assim uma atualização da base não desloca as decisões do revisor.

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

## 7. Catálogo de indicadores (BI)

| # | id | ODS | Grupo | Indicador | Código | Anos | Fonte |
|---:|---|---|---|---|---|---|---|
| 1 | `1cbfe757` | 1 | Proporção do Total das Despesas Públicas Municipais com Educação e Seguridade Social | Proporção do Total das Despesas Públicas Municipais com Educação e Seguridade Social (%) | `1.a.2.A` | 2010–2025 | 2026-09-15 |
| 2 | `414c2b43` | 2 | Proporção de Crianças Desnutridas com até dois Anos de Idade | Proporção de Crianças Desnutridas com até dois Anos de Idade (%) | `2.1.1.A` | 1998–2015 | 2019-09-17 |
| 3 | `d031e7ee` | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Total (%) | `2.2.2.A` | 2000–2025 | 2026-08-24 |
| 4 | `668bfdbd` | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Branca (%) | `2.2.2.A` | 2000–2025 | 2026-08-24 |
| 5 | `86bdac62` | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Preta (%) | `2.2.2.A` | 2000–2025 | 2026-08-24 |
| 6 | `c195aeb2` | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Amarela (%) | `2.2.2.A` | 2000–2025 | 2026-08-24 |
| 7 | `9d333cbf` | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Parda (%) | `2.2.2.A` | 2000–2025 | 2026-08-24 |
| 8 | `c83a89c6` | 2 | Proporção de Nascidos Vivos com Baixo Peso ao Nascer | Proporção de Nascidos Vivos com Baixo Peso ao Nascer - Cor/Raça Indígena (%) | `2.2.2.A` | 2000–2025 | 2026-08-24 |
| 9 | `32b6d195` | 3 | Cobertura Vacinal | Cobertura Vacinal - BCG (Tuberculose) (%) | `3.b.1` | 1997–2025 | 2026-09-04 |
| 10 | `270d1e4e` | 3 | Cobertura Vacinal | Cobertura Vacinal - Hepatite A (HA) (%) | `3.b.1` | 2014–2025 | 2026-09-04 |
| 11 | `de110c2f` | 3 | Cobertura Vacinal | Cobertura Vacinal - Hepatite B (HB) (%) | `3.b.1` | 1997–2024 | 2026-09-04 |
| 12 | `cb3bfae4` | 3 | Cobertura Vacinal | Cobertura Vacinal - Hepatite B em Menores de 1 mês (HB < 1m) (%) | `3.b.1` | 2014–2025 | 2026-09-04 |
| 13 | `97682e6d` | 3 | Cobertura Vacinal | Cobertura Vacinal - Rotavírus Humano (VORH) (%) | `3.b.1` | 2006–2025 | 2026-09-04 |
| 14 | `dc585f57` | 3 | Cobertura Vacinal | Cobertura Vacinal - Meningocócica Conjugada (Men C) (%) | `3.b.1` | 2010–2025 | 2026-09-04 |
| 15 | `f3f74e32` | 3 | Cobertura Vacinal | Cobertura Vacinal - Penta Bacteriana (Pentavalente) (DTP+Hib+HB) (PENTA) (%) | `3.b.1` | 2012–2025 | 2026-09-04 |
| 16 | `705f5b02` | 3 | Cobertura Vacinal | Cobertura Vacinal - Pneumocócica 10V (Pncc10V) (%) | `3.b.1` | 2010–2025 | 2026-09-04 |
| 17 | `c7da0ea4` | 3 | Cobertura Vacinal | Cobertura Vacinal - Poliomielite (VOP) (%) | `3.b.1` | 1997–2024 | 2026-09-04 |
| 18 | `5eb4f91d` | 3 | Cobertura Vacinal | Cobertura Vacinal - Tríplice Viral (SCR) (%) | `3.b.1` | 2000–2025 | 2026-09-04 |
| 19 | `487b0ce9` | 3 | Cobertura Vacinal | Cobertura Vacinal - Tetra Viral (SCR+VZ) (%) | `3.b.1` | 2013–2022 | 2026-09-04 |
| 20 | `c8b11256` | 3 | Cobertura Vacinal | Cobertura Vacinal - Tríplice Acelular Gestante (dTpa) (%) | `3.b.1` | 2013–2025 | 2026-09-04 |
| 21 | `228a83cd` | 3 | Mortalidade Materna | Número de Óbitos Maternos - Total | `3.1.1` | 2000–2025 | 2026-08-24 |
| 22 | `7c56a1b8` | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Branca | `3.1.1` | 2000–2025 | 2026-08-24 |
| 23 | `2eaa6f8a` | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Preta | `3.1.1` | 2000–2025 | 2026-08-24 |
| 24 | `50501e27` | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Amarela | `3.1.1` | 2000–2025 | 2026-08-24 |
| 25 | `c8616b8d` | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Parda | `3.1.1` | 2000–2025 | 2026-08-24 |
| 26 | `5697bf94` | 3 | Mortalidade Materna | Número de Óbitos Maternos - Cor/Raça Indígena | `3.1.1` | 2000–2025 | 2026-08-24 |
| 27 | `98c4c044` | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Total (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 2026-08-24 |
| 28 | `ed87fe32` | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Branca (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 2026-08-24 |
| 29 | `cff7be3b` | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Preta (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 2026-08-24 |
| 30 | `57ad88e5` | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Amarela (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 2026-08-24 |
| 31 | `afd5fd70` | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Parda (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 2026-08-24 |
| 32 | `4ffaa0e6` | 3 | Mortalidade Materna | Taxa de Mortalidade Materna - Cor/Raça Indígena (100 mil nascidos vivos) | `3.1.1` | 2000–2025 | 2026-08-24 |
| 33 | `df7f338f` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Total | `3.2.2` | 2000–2025 | 2026-08-24 |
| 34 | `7113c4c1` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Branca | `3.2.2` | 2000–2025 | 2026-08-24 |
| 35 | `800c41e4` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Preta | `3.2.2` | 2000–2025 | 2026-08-24 |
| 36 | `1a96b7e2` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Amarela | `3.2.2` | 2000–2025 | 2026-08-24 |
| 37 | `d2331607` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Parda | `3.2.2` | 2000–2025 | 2026-08-24 |
| 38 | `752b6897` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais - Cor/Raça Indígena | `3.2.2` | 2000–2025 | 2026-08-24 |
| 39 | `02731bee` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Total (mil nascidos vivos) | `3.2.2` | 2000–2025 | 2026-08-24 |
| 40 | `87ae5145` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Branca (mil nascidos vivos) | `3.2.2` | 2000–2025 | 2026-08-24 |
| 41 | `84703cc8` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Preta (mil nascidos vivos) | `3.2.2` | 2000–2025 | 2026-08-24 |
| 42 | `f01daafa` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Amarela (mil nascidos vivos) | `3.2.2` | 2000–2025 | 2026-08-24 |
| 43 | `f7db0b51` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Parda (mil nascidos vivos) | `3.2.2` | 2000–2025 | 2026-08-24 |
| 44 | `e851ca30` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal - Cor/Raça Indígena (mil nascidos vivos) | `3.2.2` | 2000–2025 | 2026-08-24 |
| 45 | `05ee4835` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Total | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 46 | `c7650158` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Branca | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 47 | `1e02947d` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Preta | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 48 | `4501e58d` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Amarela | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 49 | `93a0ccdf` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Parda | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 50 | `be3803f7` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Precoces - Cor/Raça Indígena | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 51 | `3ca6ac40` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Total (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 52 | `b3b21a84` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Branca (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 53 | `c9e3d095` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Preta (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 54 | `0dae82ee` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Amarela (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 55 | `063dcf85` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Parda (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 56 | `9980603c` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Precoce - Cor/Raça Indígena (mil nascidos vivos) | `3.2.2.A` | 2000–2025 | 2026-08-24 |
| 57 | `705e5576` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Total | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 58 | `b3c6f97f` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Branca | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 59 | `a56c04d8` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Preta | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 60 | `430b3735` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Amarela | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 61 | `baaa53a4` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Parda | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 62 | `2c24610b` | 3 | Mortalidade Neonatal | Número de Óbitos Neonatais Tardios - Cor/Raça Indígena | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 63 | `f478d300` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Total (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 64 | `6aa470ae` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Branca (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 65 | `539a5678` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Preta (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 66 | `97980fc1` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Amarela (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 67 | `840c7513` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Parda (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 68 | `6d5d8f24` | 3 | Mortalidade Neonatal | Taxa de Mortalidade Neonatal Tardia - Cor/Raça Indígena (mil nascidos vivos) | `3.2.2.B` | 2000–2025 | 2026-08-24 |
| 69 | `9a0e0eab` | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Total | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 70 | `51c994ae` | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Branca | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 71 | `30ba67d6` | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Preta | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 72 | `3686ecd8` | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Amarela | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 73 | `5e892c4f` | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Parda | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 74 | `6d9ce0c5` | 3 | Mortalidade em Menores de 1 ano de Idade | Número de Óbitos em Menores de 1 ano de Idade - Cor/Raça Indígena | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 75 | `d57b6d96` | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Total (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 76 | `9598aa92` | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Branca (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 77 | `cdabe227` | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Preta (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 78 | `c754c50f` | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Amarela (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 79 | `0002ca5f` | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Parda (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 80 | `9d725b8a` | 3 | Mortalidade em Menores de 1 ano de Idade | Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Cor/Raça Indígena (mil nascidos vivos) | `3.2.1.A` | 2000–2025 | 2026-08-24 |
| 81 | `b59ac157` | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Total | `3.2.1` | 2000–2025 | 2026-08-24 |
| 82 | `1faf82b2` | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Branca | `3.2.1` | 2000–2025 | 2026-08-24 |
| 83 | `998d50c7` | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Preta | `3.2.1` | 2000–2025 | 2026-08-24 |
| 84 | `bdce32d3` | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Amarela | `3.2.1` | 2000–2025 | 2026-08-24 |
| 85 | `fb0e99e6` | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Parda | `3.2.1` | 2000–2025 | 2026-08-24 |
| 86 | `a52ac35d` | 3 | Mortalidade em Menores de 5 Anos de Idade | Número de Óbitos em Menores de 5 anos de Idade - Cor/Raça Indígena | `3.2.1` | 2000–2025 | 2026-08-24 |
| 87 | `50555852` | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Total (mil nascidos vivos) | `3.2.1` | 2000–2025 | 2026-08-24 |
| 88 | `a9e5c5a7` | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Branca (mil nascidos vivos) | `3.2.1` | 2000–2025 | 2026-08-24 |
| 89 | `02782bcf` | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Preta (mil nascidos vivos) | `3.2.1` | 2000–2025 | 2026-08-24 |
| 90 | `bb57ce01` | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Amarela (mil nascidos vivos) | `3.2.1` | 2000–2025 | 2026-08-24 |
| 91 | `d9049e79` | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Parda (mil nascidos vivos) | `3.2.1` | 2000–2025 | 2026-08-24 |
| 92 | `f0b5eae4` | 3 | Mortalidade em Menores de 5 Anos de Idade | Taxa de Mortalidade em Menores de 5 anos de Idade - Cor/Raça Indígena (mil nascidos vivos) | `3.2.1` | 2000–2025 | 2026-08-24 |
| 93 | `6bad7f46` | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Total (mil habitantes) | `3.c.1` | 2007–2025 | 2026-04-07 |
| 94 | `a27ce5b4` | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Médicos (mil habitantes) | `3.c.1.A` | 2007–2025 | 2026-04-07 |
| 95 | `d0112684` | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Enfermeiros (mil habitantes) | `3.c.1.B` | 2007–2025 | 2026-04-07 |
| 96 | `ca71174c` | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Dentistas (mil habitantes) | `3.c.1.C` | 2007–2025 | 2026-04-07 |
| 97 | `e497198b` | 3 | Número de Profissionais de Saúde | Número de Profissionais de Saúde - Farmacêuticos (mil habitantes) | `3.c.1.D` | 2007–2025 | 2026-04-07 |
| 98 | `5accbde2` | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Total (%) | `3.1.2.A` | 2001–2025 | 2026-08-24 |
| 99 | `7221dcca` | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Branca (%) | `3.1.2.A` | 2001–2025 | 2026-08-24 |
| 100 | `403e19a5` | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Preta (%) | `3.1.2.A` | 2001–2025 | 2026-08-24 |
| 101 | `ca853ba8` | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Amarela (%) | `3.1.2.A` | 2001–2025 | 2026-08-24 |
| 102 | `a087332c` | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Parda (%) | `3.1.2.A` | 2001–2025 | 2026-08-24 |
| 103 | `acbd7dbb` | 3 | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal | Proporção de Nascidos Vivos com 7 ou mais Consultas Pré-Natal - Cor/Raça Indígena (%) | `3.1.2.A` | 2001–2025 | 2026-08-24 |
| 104 | `e8c20578` | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Total (%) | `3.3.1.A` | 2000–2024 | 2026-05-26 |
| 105 | `4c7c8deb` | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Branca (%) | `3.3.1.A` | 2000–2024 | 2026-05-26 |
| 106 | `9358542c` | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Preta (%) | `3.3.1.A` | 2000–2024 | 2026-05-26 |
| 107 | `0259c089` | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Amarela (%) | `3.3.1.A` | 2000–2024 | 2026-05-26 |
| 108 | `4486ed57` | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Parda (%) | `3.3.1.A` | 2000–2024 | 2026-05-26 |
| 109 | `cbaf7053` | 3 | Proporção dos Casos de AIDS entre Mulheres | Proporção dos Casos de AIDS entre Mulheres - Cor/Raça Indígena (%) | `3.3.1.A` | 2000–2024 | 2026-05-26 |
| 110 | `bb398266` | 3 | Taxa de Incidência de AIDS por ano de Diagnóstico | Taxa de Incidência de AIDS por ano de Diagnóstico (mil habitantes) | `3.3.1` | 1997–2024 | 2025-12-15 |
| 111 | `56d44875` | 3 | Taxa de Incidência de Hepatite B | Taxa de Incidência de Hepatite B (100 mil habitantes) | `3.3.4` | 2007–2023 | 2025-05-06 |
| 112 | `c4080204` | 3 | Taxa de Incidência de Tuberculose | Taxa de Incidência de Tuberculose (100 mil habitantes) | `3.3.2` | 2001–2025 | 2026-09-04 |
| 113 | `d0bbb247` | 3 | Taxa de Nascidos Vivos de Mães Adolescentes | Taxa de Nascidos Vivos de Mães Adolescentes - 10 a 14 anos de Idade (mil meninas do grupo etário) | `3.7.2` | 2011–2025 | 2026-08-24 |
| 114 | `55c95e92` | 3 | Taxa de Nascidos Vivos de Mães Adolescentes | Taxa de Nascidos Vivos de Mães Adolescentes - 15 a 19 anos de Idade (mil meninas do grupo etário) | `3.7.2` | 2011–2025 | 2026-08-24 |
| 115 | `8f2afa29` | 3 | Taxas de Mortalidade | Taxa de Mortalidade por AIDS (100 mil habitantes) | `3.3.1.B` | 1997–2025 | 2026-08-24 |
| 116 | `0d92d675` | 3 | Taxas de Mortalidade | Taxa de Mortalidade Causas Selecionadas - Tuberculose (Todas as Formas) (100 mil habitantes) | `3.3.2.A` | 1997–2025 | 2026-08-24 |
| 117 | `378a6343` | 3 | Taxas de Mortalidade | Taxa de Mortalidade Causas Externas - Lesões Autoprovocadas Intencionalmente (Suicídios) (100 mil habitantes) | `3.4.2` | 1997–2025 | 2026-08-24 |
| 118 | `45f57026` | 3 | Taxas de Mortalidade | Taxa de Mortalidade Causas Externas - Acidentes de Trânsito (Transporte) (100 mil habitantes) | `3.6.1` | 1997–2025 | 2026-08-24 |
| 119 | `0b517daa` | 3 | Taxas de Mortalidade | Taxa de Mortalidade Atribuída a Fontes de Água Inseguras, Saneamento Inseguro e Falta de Higiene (100 mil habitantes) | `3.9.2` | 1997–2025 | 2026-08-24 |
| 120 | `8907d706` | 3 | Taxas de Mortalidade | Taxa de Mortalidade Atribuída a Intoxicação não Intencional (100 mil habitantes) | `3.9.3` | 1997–2025 | 2026-08-24 |
| 121 | `8687dcaa` | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Acesso à Eletricidade (%) | `4.a.1a` | 2015–2025 | 2026-04-07 |
| 122 | `50f25f17` | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Acesso à Internet (%) | `4.a.1b` | 2015–2025 | 2026-04-07 |
| 123 | `1087be9e` | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Acesso a Computadores para Fins Pedagógicos (%) | `4.a.1c` | 2015–2025 | 2026-04-07 |
| 124 | `b2103205` | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Infraestrutura Adaptada para Alunos com Deficiência (%) | `4.a.1d` | 2010–2025 | 2026-04-07 |
| 125 | `819c0873` | 4 | Infraestrutura nas Escolas | Proporção de Escolas com Abastecimento de Água (%) | `4.a.1e` | 2015–2025 | 2026-04-07 |
| 126 | `2fdeddf2` | 4 | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Leitura (%) | `4.1.1a` | 2014–2016 | 2019-09-12 |
| 127 | `409119f3` | 4 | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Escrita (%) | `4.1.1a` | 2014–2016 | 2019-09-12 |
| 128 | `430e2121` | 4 | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes do Terceiro Ano do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática (%) | `4.1.1a` | 2014–2016 | 2019-09-12 |
| 129 | `bd236647` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Total (%) | `4.1.1b` | 2015–2025 | 2026-08-24 |
| 130 | `77fc6202` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Urbana (%) | `4.1.1b` | 2015–2025 | 2026-08-24 |
| 131 | `d1a57a3d` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Rural (%) | `4.1.1b` | 2015–2025 | 2026-08-24 |
| 132 | `a9c8290e` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Total (%) | `4.1.1b` | 2015–2025 | 2026-08-24 |
| 133 | `4c2d69ac` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Urbana (%) | `4.1.1b` | 2015–2025 | 2026-08-24 |
| 134 | `570d7a19` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Rural (%) | `4.1.1b` | 2015–2025 | 2026-08-24 |
| 135 | `05d5bfa4` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Total (%) | `4.1.1c` | 2015–2025 | 2026-08-24 |
| 136 | `390eff64` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Urbana (%) | `4.1.1c` | 2015–2025 | 2026-08-24 |
| 137 | `5deb974c` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Rural (%) | `4.1.1c` | 2015–2025 | 2026-08-24 |
| 138 | `3b5c4f9c` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Total (%) | `4.1.1c` | 2015–2025 | 2026-08-24 |
| 139 | `de60ee22` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Urbana (%) | `4.1.1c` | 2015–2025 | 2026-08-24 |
| 140 | `5480ecf8` | 4 | Proporção de Estudantes do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência | Proporção de Estudantes no Final dos Anos Finais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Matemática - Rural (%) | `4.1.1c` | 2015–2025 | 2026-08-24 |
| 141 | `0652f604` | 4 | Proporção de Pessoas de 4 a 5 anos Matriculadas na Pré-Escola | Proporção de Pessoas de 4 a 5 anos Matriculadas na Pré-Escola (%) | `4.2.2.A` | 2014–2020 | 2021-06-14 |
| 142 | `86dcfcd8` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Total (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 143 | `c54e370b` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Federal (%) | `4.c.1.A` | 2013–2019 | 2026-08-24 |
| 144 | `d57708a0` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 145 | `2db86648` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Municipal (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 146 | `1040c064` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Educação Infantil - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 147 | `262461e8` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Total (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 148 | `80eada01` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 149 | `b23c9aee` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Municipal (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 150 | `b616865a` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Iniciais - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 151 | `0a591407` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Total (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 152 | `7a7b4b18` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Federal (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 153 | `80fc42fd` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 154 | `b29eef2f` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Municipal (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 155 | `835d77d8` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Fundamental - Anos Finais - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 156 | `d4cb0b54` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Total (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 157 | `f0af83d8` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Federal (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 158 | `fd301ba4` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Estadual (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 159 | `1f87e06e` | 4 | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam | Proporção de Docências com Professores cuja Formação Superior está Adequada à Área de Conhecimento que Lecionam - Ensino Médio - Rede Particular (%) | `4.c.1.A` | 2013–2025 | 2026-08-24 |
| 160 | `b2af7a5b` | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Total (%) | `5.5.1` | 2012–2024 | 2026-05-26 |
| 161 | `cbabcced` | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Branca (%) | `5.5.1` | 2016–2024 | 2026-05-26 |
| 162 | `e390841c` | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Preta (%) | `5.5.1` | 2016–2024 | 2026-05-26 |
| 163 | `1971de03` | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Amarela (%) | `5.5.1` | 2016–2024 | 2026-05-26 |
| 164 | `2e307941` | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Parda (%) | `5.5.1` | 2016–2024 | 2026-05-26 |
| 165 | `e89a4493` | 5 | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores | Proporção de Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Cor/Raça Indígena (%) | `5.5.1` | 2016–2024 | 2026-05-26 |
| 166 | `37b6395c` | 5 | Proporção de Mulheres em Posições Gerenciais (RAIS) | Proporção de Mulheres em Posições Gerenciais (RAIS) (%) | `5.5.2.A` | 2010–2025 | 2026-05-28 |
| 167 | `a01adf32` | 6 | Abastecimento de Água - Unidades Atendidas Residenciais | Abastecimento de Água - Unidades Atendidas Residenciais | `6.1.1.A` | 2010–2024 | 2026-02-12 |
| 168 | `bf8d2d7f` | 6 | Atendimento de Esgoto - Unidades Atendidas Residenciais | Atendimento de Esgoto - Unidades Atendidas Residenciais | `6.2.1.A` | 2010–2024 | 2026-02-12 |
| 169 | `e31dbde3` | 7 | Energia Elétrica Residencial - Consumidores | Energia Elétrica Residencial - Consumidores | `7.1.1.A` | 2010–2025 | 2026-08-24 |
| 170 | `3e3e7cab` | 8 | Empregos (RAIS) | Empregos (RAIS) | `8.5.2.A` | 2010–2025 | 2026-05-28 |
| 171 | `c7a270cd` | 8 | Número de Agências Bancárias e Postos de Atendimento Eletrônico (PAE) | Número de Agências Bancárias (100 mil adultos) | `8.10.1a` | 2011–2025 | 2026-02-26 |
| 172 | `cbf9aa48` | 8 | Número de Agências Bancárias e Postos de Atendimento Eletrônico (PAE) | Número de Postos de Atendimento Eletrônico (PAE) (100 mil adultos) | `8.10.1b` | 2011–2025 | 2026-02-26 |
| 173 | `dfde04b7` | 8 | Produto Interno Bruto (PIB) | Produto Interno Bruto (PIB) a Preços Correntes (R$ 1.000,00) | `8.1.1.A` | 2002–2023 | 2026-02-12 |
| 174 | `c0cd13ae` | 8 | Produto Interno Bruto (PIB) | Produto Interno Bruto (PIB) per Capita (R$ 1,00) | `8.1.2.A` | 2002–2023 | 2026-02-12 |
| 175 | `2616f83c` | 8 | Proporção de Empregos (RAIS) nas Atividades Características do Turismo | Proporção de Empregos (RAIS) nas Atividades Características do Turismo (%) | `8.9.2.A` | 2010–2023 | 2025-11-04 |
| 176 | `c34d7343` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora - Masculino (R$ 1,00) | `8.5.1.A` | 2010–2025 | 2026-05-28 |
| 177 | `06a1a683` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora - Feminino (R$ 1,00) | `8.5.1.A` | 2010–2025 | 2026-05-28 |
| 178 | `0f1aa322` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora no Comércio - Masculino (R$ 1,00) | `8.5.1.A1` | 2010–2025 | 2026-05-28 |
| 179 | `4b2eaaed` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora no Comércio - Feminino (R$ 1,00) | `8.5.1.A1` | 2010–2025 | 2026-05-28 |
| 180 | `b1dbe1b2` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Construção Civil - Masculino (R$ 1,00) | `8.5.1.A2` | 2010–2025 | 2026-05-28 |
| 181 | `cef55550` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Construção Civil - Feminino (R$ 1,00) | `8.5.1.A2` | 2010–2025 | 2026-05-28 |
| 182 | `bd177576` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Indústria - Masculino (R$ 1,00) | `8.5.1.A3` | 2010–2025 | 2026-05-28 |
| 183 | `e5851877` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Indústria - Feminino (R$ 1,00) | `8.5.1.A3` | 2010–2025 | 2026-05-28 |
| 184 | `8ef0bdad` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora em Serviços - Masculino (R$ 1,00) | `8.5.1.A4` | 2010–2025 | 2026-05-28 |
| 185 | `8f7ad093` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora em Serviços - Feminino (R$ 1,00) | `8.5.1.A4` | 2010–2025 | 2026-05-28 |
| 186 | `5fe9386e` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Agropecuária - Masculino (R$ 1,00) | `8.5.1.A5` | 2010–2025 | 2026-05-28 |
| 187 | `c33b7328` | 8 | Rendimento Nominal Médio por Hora | Rendimento Nominal Médio por Hora na Agropecuária - Feminino (R$ 1,00) | `8.5.1.A5` | 2010–2025 | 2026-05-28 |
| 188 | `e0183922` | 8 | Valor Adicionado Fiscal nas Atividades Características do Turismo | Valor Adicionado Fiscal nas Atividades Características do Turismo (R$ 1,00) | `8.9.1.A` | 2010–2024 | 2026-03-06 |
| 189 | `ba998cc1` | 9 | Emprego no Setor de Indústria como Percentual do Emprego Total | Emprego no Setor de Indústria como Percentual do Emprego Total (%) | `9.2.2` | 2002–2025 | 2026-05-28 |
| 190 | `be35670d` | 9 | Percentual do Valor Adicionado Bruto na Indústria sobre o PIB | Percentual do Valor Adicionado Bruto na Indústria sobre o PIB (%) | `9.2.1` | 2002–2021 | 2024-11-12 |
| 191 | `6c40b6f5` | 13 | Número de Mortes, Pessoas Desaparecidas e Pessoas Diretamente Afetadas Atribuído a Desastres | Número de Mortes, Pessoas Desaparecidas e Pessoas Diretamente Afetadas Atribuído a Desastres (100 mil habitantes) | `13.1.1` | 2011–2025 | 2026-04-30 |
| 192 | `5ba84b67` | 15 | Área de Remanescente Florestal como Proporção da Área Territorial | Área de Remanescente Florestal como Proporção da Área Territorial (%) | `15.1.1A` | 2012–2025 | 2026-09-04 |
| 193 | `8ec34e57` | 16 | Proporção de Nascidos Vivos que Tiveram seus Nascimentos Registrados por uma Autoridade Civil | Proporção de Nascidos Vivos que Tiveram seus Nascimentos Registrados por uma Autoridade Civil (%) | `16.9.1.A` | 2015–2024 | 2026-08-24 |
| 194 | `9f473c78` | 16 | Taxa de Mortalidade por Homicídios | Taxa de Mortalidade por Homicídios (100 mil habitantes) | `16.1.1` | 1997–2025 | 2026-08-24 |
| 195 | `sinisa_iag0001` | 6 | Abastecimento de água (SINISA) | Atendimento da população total com rede de abastecimento de água | `IAG0001` | 2023–2023 | 2023-12-31 |
| 196 | `sinisa_iag0002` | 6 | Abastecimento de água (SINISA) | Atendimento da população urbana com rede de abastecimento de água | `IAG0002` | 2023–2023 | 2023-12-31 |
| 197 | `sinisa_iag0003` | 6 | Abastecimento de água (SINISA) | Atendimento da população rural com rede de abastecimento de água | `IAG0003` | 2023–2023 | 2023-12-31 |
| 198 | `65b78ec7` | 11 | Cidades Sustentáveis | Mortes no trânsito (100 mil habitantes) | `3.6.1` | 1997–2025 | 2026-08-24 |

## 8. Armadilhas e qualidade dos dados

| # | Problema | Impacto | Mitigação |
|---:|---|---|---|
| 1 | Escalas heterogêneas dentro do mesmo tema | comparação direta enganosa | unidade sempre visível |
| 2 | Indicador ≠ % sempre (contagens, moeda) | ranking por “maior %” fica errado | campo `tipo` por indicador |
| 3 | Ausência codificada como texto (`...`, `-`) | somas silenciosamente ignoradas | ETL converte para nulo |
| 4 | Indicadores 100% vazios | gráfico vazio | ignorados no ETL (2 de 196) |
| 5 | Cobertura baixa em recortes raciais | média distorcida, série quebrada | mostra-se o `n` disponível |
| 6 | Agregado regional ausente em parte dos indicadores | nível regional não exibido | oculto quando ausente |
| 7 | Séries com janelas diferentes | comparação multi-indicador enganosa | eixo X no ano real; lacunas desenhadas como pontos |
| 8 | ODS 5 só em anos eleitorais | linha contínua sugere interpolação | sem segmento entre anos distantes |
| 9 | Indicadores com muitos municípios empatados | percentil vira 100% para todos | regra de elegibilidade para síntese (ver DECISOES.md) |
| 10 | Indicadores com pouquíssimos municípios com dado | posição sem base de comparação | `n` exibido; fora das sínteses |
| 11 | Sem população por município na base | impossível recalcular taxas | denominador do IBGE (populate.js) |
| 12 | `Assunto` redundante | 1,2 M de strings repetidas | descartado no ETL |

## 9. População (denominador das taxas calculadas)

`data/bi/populacao.js` traz `BI.pop = {anos, valores, info}` na mesma ordem de `BI.indice.localidades`, achatado por `[localidade × n_anos + ano]`. Fontes: estimativas do IBGE (agregado 6579/9324), Censo 2022 (4714/93) e Censo 2010 (200/93). Anos sem publicação são interpolados linearmente entre os vizinhos e **marcados em `info`**. Estado e RGInt são a soma dos municípios.

