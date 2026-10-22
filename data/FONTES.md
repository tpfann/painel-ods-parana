# Status das fontes oficiais

> Gerado por `scripts/05_fetch_fontes.py` em 2026-10-22 08:35. Não editar à mão: o registro editável é [`data/fontes.csv`](fontes.csv).

| Situação | Fontes |
|---|---:|
| Ativas | 30 |
| **Pendentes (edição nova já deveria ter saído)** | **9** |
| **URL alterada** | **0** |
| Sem rede (não verificadas) | 0 |

## O que fazer

1. Abra a **página da fonte** (coluna `url_landing`) e localize a nova edição.
2. Atualize a coluna `url_direta` da fonte em `data/fontes.csv` e rode:
   ```bash
   python scripts/05_fetch_fontes.py
   ```
3. Baixe o novo arquivo para `Base de Dados/` (mesmo nome) e rode o pipeline:
   ```bash
   python scripts/01_build_catalog.py && python scripts/04_build_populacao.py \
       && python scripts/03_build_bi.py && python scripts/02_gen_schema.py
   ```
4. O histórico das trocas de URL fica no git.

| Fonte | Situação | Detalhe | Onde buscar |
|---|---|---|---|
| `f02` | pendente | a edicao 2026 ja deveria ter saido (mes 9) e a fonte esta em 2019-09-17 | https://opendatas.saude.gov.br/ |
| `f12` | pendente | a edicao 2026 ja deveria ter saido (mes 5) e a fonte esta em 2025-12-15 | https://opendatas.saude.gov.br/ |
| `f13` | pendente | a edicao 2026 ja deveria ter saido (mes 9) e a fonte esta em 2025-05-06 | https://opendatas.saude.gov.br/ |
| `f17` | pendente | a edicao 2026 ja deveria ter saido (mes 8) e a fonte esta em 2026-04-07 | https://download.inep.gov.br/ |
| `f18` | pendente | a edicao 2026 ja deveria ter saido (mes 8) e a fonte esta em 2019-09-12 | https://download.inep.gov.br/ |
| `f20` | pendente | a edicao 2026 ja deveria ter saido (mes 8) e a fonte esta em 2021-06-14 | https://download.inep.gov.br/ |
| `f30` | pendente | a edicao 2026 ja deveria ter saido (mes 5) e a fonte esta em 2025-11-04 | https://portaldadosabertos.mte.gov.br/ |
| `f34` | pendente | a edicao 2026 ja deveria ter saido (mes 2) e a fonte esta em 2024-11-12 | https://servicodados.ibge.gov.br/api/docs |
| `f39` | pendente | a edicao 2026 ja deveria ter saido (mes 3) e a fonte esta em 2023-12-31 | https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento/sinisa/resultados-sinisa |

## Inventário

| Fonte | Arquivo | ODS | Publicador | Acesso | Periodicidade | Espelho |
|---|---|---:|---|---|---|---|
| `f01` | O01 - Proporção de Despesas Públicas com Educa | 1 | Tesouro Nacional / SICONFI (FINBRA) | download | anual | 2026-10-21 |
| `f02` | O02 - Proporção de Crianças Desnutridas com at | 2 | Ministério do Desenvolvimento Social / | download | anual | 2026-10-21 |
| `f03` | O02 - Proporção de Nascidos Vivos com Baixo Pe | 2 | Ministério da Saúde / SINASC (nascidos | download | anual | 2026-10-21 |
| `f04` | O03 - Cobertura Vacinal.xlsx | 3 | Ministério da Saúde / PNI (vacinação) | download | anual | 2026-10-21 |
| `f05` | O03 - Mortalidade Materna.xlsx | 3 | Ministério da Saúde / SIM (óbitos) | download | anual | 2026-10-21 |
| `f06` | O03 - Mortalidade Neonatal.xlsx | 3 | Ministério da Saúde / SIM (óbitos) | download | anual | 2026-10-21 |
| `f07` | O03 - Mortalidade em Menores de 1 ano de Idade | 3 | Ministério da Saúde / SIM (óbitos) | download | anual | 2026-10-21 |
| `f08` | O03 - Mortalidade em Menores de 5 anos de Idad | 3 | Ministério da Saúde / SIM (óbitos) | download | anual | 2026-10-21 |
| `f09` | O03 - Número de Profissionais de Saúde.xlsx | 3 | Ministério da Saúde / CNES (estabeleci | download | anual | 2026-10-21 |
| `f10` | O03 - Proporção de Nascidos Vivos com 7 ou mai | 3 | Ministério da Saúde / SINASC (nascidos | download | anual | 2026-10-21 |
| `f11` | O03 - Proporção dos Casos de AIDS entre Mulher | 3 | Ministério da Saúde / SIH (AIDS) | download | anual | 2026-10-21 |
| `f12` | O03 - Taxa de Incidência de AIDS.xlsx | 3 | Ministério da Saúde / SIH (AIDS) | download | anual | 2026-10-21 |
| `f13` | O03 - Taxa de Incidência de Hepatite B.xlsx | 3 | Ministério da Saúde / SINAN (agravos) | download | anual | 2026-10-21 |
| `f14` | O03 - Taxa de Incidência de Tuberculose.xlsx | 3 | Ministério da Saúde / SINAN (agravos) | download | anual | 2026-10-21 |
| `f15` | O03 - Taxa de Nascidos Vivos de Mães Adolescen | 3 | Ministério da Saúde / SINASC (nascidos | download | anual | 2026-10-21 |
| `f16` | O03 - Taxas de Mortalidade.xlsx | 3 | Ministério da Saúde / SIM (óbitos) | download | anual | 2026-10-21 |
| `f17` | O04 - Infraestrutura nas Escolas.xlsx | 4 | Ministério da Educação / INEP | download | anual | 2026-10-21 |
| `f18` | O04 - Nível de Proficiência de Estudantes do T | 4 | Ministério da Educação / INEP | download | anual | 2026-10-21 |
| `f19` | O04 - Nível de Proficiência de Estudantes dos  | 4 | Ministério da Educação / INEP | download | anual | 2026-10-21 |
| `f20` | O04 - Proporção de Pessoas de 4 a 5 anos Matri | 4 | Ministério da Educação / INEP | download | anual | 2026-10-21 |
| `f21` | O04 - Proporção de Professores com Formação Su | 4 | Ministério da Educação / INEP | download | anual | 2026-10-21 |
| `f22` | O05 - Proporção de Cadeiras Ocupadas por Mulhe | 5 | Tribunal Superior Eleitoral | download | quadrienal | 2026-10-21 |
| `f23` | O05 - Proporção de Mulheres em Posições Gerenc | 5 | Ministério do Trabalho e Emprego / RAI | download | anual | 2026-10-21 |
| `f24` | O06 - Abastecimento de Água - Unidade Atendida | 6 | SANEPAR (e SNIS/SINISA do Ministério d | manual | anual | 2026-10-21 |
| `f25` | O06 - Atendimento de Esgoto - Unidade Atendida | 6 | SANEPAR (e SNIS/SINISA do Ministério d | manual | anual | 2026-10-21 |
| `f26` | O07 - Energia Elétrica Residencial - Consumido | 7 | COPEL, CELESC, COCOEL, CFLO, CPFL e Pa | manual | anual | 2026-10-21 |
| `f27` | O08 - Emprego (RAIS).xlsx | 8 | Ministério do Trabalho e Emprego / RAI | download | anual | 2026-10-21 |
| `f28` | O08 - Número Agências Bancárias e Postos de At | 8 | Banco Central do Brasil / IPARDES | api | anual | 2026-10-21 |
| `f29` | O08 - Produto Interno Bruto (PIB).xlsx | 8 | IPARDES / IBGE | api | anual | 2026-10-21 |
| `f30` | O08 - Proporção de Empregos nas Atividades Car | 8 | Ministério do Trabalho e Emprego / RAI | download | anual | 2026-10-21 |
| `f31` | O08 - Rendimento Nominal Médio por Hora.xlsx | 8 | Ministério do Trabalho e Emprego / RAI | download | anual | 2026-10-21 |
| `f32` | O08 - Valor Adicionado Fiscal nas Atividades C | 8 | Secretaria de Estado da Fazenda do Par | manual | anual | 2026-10-21 |
| `f33` | O09 - Emprego no Setor de Indústria como Perce | 9 | Ministério do Trabalho e Emprego / RAI | download | anual | 2026-10-21 |
| `f34` | O09 - Percentual do Valor Adicionado na Indúst | 9 | IPARDES / IBGE | api | anual | 2026-10-21 |
| `f35` | O13 - Número de Mortos, Desaparecidos e Direta | 13 | Coordenadoria Estadual de Proteção e D | manual | anual | 2026-10-21 |
| `f36` | O15 - Área de Remanescente Florestal como Prop | 15 | INPE (Programa Queimadas) / Fundação S | download | anual | 2026-10-21 |
| `f37` | O16 - Proporção de Nascidos Vivos Registrados  | 16 | Ministério da Saúde / SINASC (registro | download | anual | 2026-10-21 |
| `f38` | O16 - Taxa de Mortalidade por Homicídios.xlsx | 16 | Ministério da Saúde / SIM (óbitos) | download | anual | 2026-10-21 |
| `f39` |  | 6 | Ministério das Cidades / SINISA (abast | download | anual | — |

