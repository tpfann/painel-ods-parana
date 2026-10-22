# Fontes novas — especificação de ingestão

> Documento de trabalho: o que foi **verificado** nas fontes oficiais para fechar os
> ODS que faltam (10, 11, 12) e no que ainda falta. Gerado a partir de verificações
> reais (download, leitura de planilha, extração de glossário).
>
> Última verificação: **22/10/2026**.

---

## 1. Onde estamos

| ODS | Situação no painel | Fonte oficial verificada |
|---:|---|---|
| 10 (Desigualdade) | ausente | IBGE Censo 2022 (população por raça) + DataSUS (SIM/SINASC) — **nós já temos 80 indicadores com recorte racial** |
| 11 (Cidades Sustentáveis) | ausente | IBGE Censo 2022 (favelas), IBGE MUNIC (equipamentos esportivos), DataSUS/SIM (mortes no trânsito) |
| 12 (Consumo e Produção) | ausente | SINISA/Ministério das Cidades (resíduos sólidos) |

O `scripts/05_fetch_fontes.py` já mantém o registro e o lembrete dessas fontes.

---

## 2. SINISA (Ministério das Cidades) — verificado

### 2.1 Onde se pega

| Item | Endereço | Verificado |
|---|---|---|
| Página de resultados (estável) | `gov.br/cidades/.../saneamento/sinisa/resultados-sinisa` | 200 |
| ZIP de resultados (muda por ano) | `.../sinisa/arquivos/SINISA_Resultados_Ref{ANO}.zip` | 200 — 19,9 MB |
| Planilha de gestão municipal | `.../sinisa/resultados-sinisa/SINISA_GESTAOMUNICIPAL_Informacoes_{ANO}.xlsx` | 200 — 6,9 MB |
| Glossário de indicadores (água) | `.../resultados-sinisa/INDICADORES_SINISA_ABASTECIMENTO_DE_AGUA_2024_v2.pdf` | 200 — 20 páginas |
| Glossário (esgoto) | `.../sinisa/arquivos/INDICADORES_SINISA_ESGOTAMENTOSANITRIO_2024_V2.pdf` | listado na página |
| Glossário (resíduos) | `.../resultados-sinisa/Glossario_Indicadores_SINISA_RESIDUOS.pdf` | listado na página (é o que o IDSC cita) |

**Edição 2023 disponível** (a de resíduos ainda não foi publicada como planilha de
resultados; os relatórios de 2024 estão no ar sob sigilo — "defeso").

### 2.2 Estrutura da planilha (medida)

`SINISA_AGUA_Indicadores_Base Municipal_2023.xlsx`, 5 abas:
`Atendimento`, `Estruturais e Operacionais`, `Qualidade`, `Administrativo e Financeiro`,
`Nota metodológica`. Em todas:

```
linha 0-5  cabeçalho institucional (ano de referência na linha 4, data de geração na 5)
linha 7    cabeçalho: "Codigo do IBGE | Macrorregião | Município | UF | ..."
linha 8    UNIDADE do indicador (Percentual, m/ligação, l/hab/dia, horas/reparo...)
linha 9    CÓDIGO do indicador (IAG0001, IAG2013, CAD0002...)
linha 10+  dados: uma linha por PRESTADOR de serviço (não por município)
```

### 2.3 ⚠️ O ponto que trava a ingestão simples

A base municipal tem **uma linha por prestador** (sistema de abastecimento), não
por município: o município de Ariquemes (RO) aparece 2 vezes na aba Qualidade.
O indicador do município **não é a média das linhas** — é a razão dos componentes
somados, como o próprio glossário define:

> `IAG0001 População atendida com rede de abastecimento de água (Percentual)`
> `[(GTA0001 + GTA0002) / DFE0001] × 100` — população urbana atendida + rural atendida
> sobre domicílios totais.

Logo, para fechar o indicador no nível municipal é preciso:

1. ler as **3 planilhas** (Indicadores + Gestão Técnica + Administrativo e Financeiro),
   que trazem os componentes `GTA*`, `DFE*` e `OGM*`;
2. juntar por **CNPJ do prestador** (coluna "Nome do Prestador" / "Sigla");
3. somar os componentes de todos os prestadores do município;
4. aplicar a fórmula do glossário.

Sem o passo 1, qualquer número publicado seria errado. **Este é o trabalho que
falta** — e ele é o mesmo para água, esgoto e resíduos.

### 2.4 IndicadoresWater úteis (extraídos do glossário oficial)

| Código | Indicador | Unidade | Serve para |
|---|---|---|---|
| IAG0001 | Atendimento da população total com rede de abastecimento de água | % | ODS 6 (cobertura) |
| IAG0002 / IAG0003 | População urbana / rural atendida com rede | % | ODS 6 (desigualdade territorial) |
| IAG0004 | Atendimento dos domicílios totais com rede | % | ODS 6 (cobertura) |
| IAG2006 / IAG2007 | Consumo total / residencial médio per capita | l/hab/dia | ODS 6 (eficiência) |
| IAG2013 | Perdas totais de água na distribuição | % | ODS 6 (eficiência) |
| IAG2014 / IAG2015 | Perdas lineares / por ligação | m/km/dia, l/lig/dia | ODS 6 (eficiência) |
| IAG3001 / IAG3002 | Economias atingidas por paralisações / interrupções | economias | ODS 6 (continuidade) |
| IAG3003 | Tempo médio de reparo de vazamentos | horas/reparo | ODS 6 (continuidade) |
| IAG3007 | Incidência de economias atingidas por intermitências | % | ODS 6 (continuidade) |
| IAG3008 | Reclamações de falta de água e vazamentos por economia | % | ODS 6 (continuidade) |

> Nomes e unidades conferidos no glossário oficial (edição 2024) — não são
> interpretados: vêm do documento do órgão.

### 2.5 Resíduos (ODS 12) — códigos que o IDSC documenta

| Código antigo (SNIS) | Código atual (SINISA) | Indicador | Unidade |
|---|---|---|---|
| IN030 | IRS0005 | População atendida com coleta seletiva | % |
| IN028 | IRS1005 | Massa média per capita de resíduos sólidos domiciliares coletados | kg/dia/hab |
| IN031 | IRS3010 | Recuperação de resíduos recicláveis secos e orgânicos | % |

*(fonte: `Glossario_Indicadores_SINISA_RESIDUOS.pdf`, p. 1 e 3 — o mesmo glossário
citado pelo IDSC)*

---

## 3. População por raça (Censo 2022) — o que falta

É o denominador das diferenças raciais do **ODS 10**, que calculamos a partir dos
**80 indicadores com recorte racial que o painel já tem** (mortalidade materna,
neonatal, infantil, < 5 anos, baixo peso, pré-natal, AIDS, cadeiras em câmaras).

O IDSC usa exatamente esta fonte: *"Para a população total do Município por
raça/cor, utilizamos as informações do Censo 2022 (IBGE)"*.

**Não foi possível localizar a tabela via API a partir deste ambiente:**

- a busca do SIDRA (`/api/v3/pesquisas`, `/pesquisas/{id}/agregados`) dá **timeout**;
- as faixas de agregados varridas (1900–2200, 4400–5300, 5300–6700) são
  **PNAD Contínua** — o Censo 2022 aparece só com tabelas de população total
  (4709, 4714) e de domicílios (4711, 4712), **sem recorte de raça**;
- o portal `censo2022.ibge.gov.br/panorama/` responde 200, mas é **inteiramente
  renderizado por JavaScript** (sem links estáticos para as tabulações).

**Caminhos a tentar de uma máquina com acesso completo** (em ordem de custo):

1. **SIDRA**: localizar a tabela pelo nome no site `sidra.ibge.gov.br/tabela/...`
   ("População residente por cor ou raça" — Censo 2022) e trazê-la pela API
   `https://servicodados.ibge.gov.br/api/v3/agregados/{id}/periodos/2022/variaveis/{var}?localidades=N6[N3[41]]`
   (mesmo padrão já usado em `04_build_populacao.py`).
2. **Painel do Censo 2022 (Panorama)**: aba "Tabulados" → "População" → XLSX por
   município; a URL estável é `censo2022.ibge.gov.br/panorama/tabulados/`.
3. **IBGE "Censo 2022 —Avaliação Censitária"**: XLSX por município com população
   por cor/raça.

---

## 4. Demais fontes dos ODS 11 (verificadas no catálogo do IDSC)

| Fonte oficial | Conteúdo | Onde |
|---|---|---|
| IBGE — Aglomerados subnormais (2019) e Censo 2022 | População e domicílios em favelas e comunidades urbanas | IBGE (SIDRA ou XLSX de tabulações) |
| IBGE — MUNIC 2021 (Pesquisa de Informações Básicas Municipais) | Equipamentos esportivos sob gestão municipal | IBGE (XLSX) |
| IBGE — População em áreas de risco (2018) | Domicílios em áreas de risco | IBGE |
| DataSUS/SIM | Mortes no trânsito (CID10 V01–V99) por 100 mil hab. | Portal DataSUS (CSV) |
| MapBiomas, INPE/Queimadas, SEEG, AdaptaBrasil | ODS 13/15 complementares |links públicos |

**Observação de método:** o IDSC publica a *fórmula* de cada indicador, o que
permite reimplementá-lo com os dados primários. É esse o caminho que o painel
deve seguir — o IDSC entra como **método de referência e camada de validação**,
não como fonte de valores.

---

## 5. Ordem de execução sugerida

| # | Tarefa | Esforço | Dependência |
|---|---|---|---|
| 1 | Ingestão SINISA (água) com junção por CNPJ e fórmula do glossário | 3–4 dias | glossário (✓ já baixado) |
| 2 | Ingestão SINISA (resíduos) — ODS 12 | 1 dia | publicação da planilha de resíduos |
| 3 | População por raça (Censo 2022) | 1 dia | achar a tabela (ver §3) |
| 4 | ODS 10: diferenças raciais calculadas sobre os 80 indicadores existentes | 1 dia | (3) |
| 5 | ODS 11: favelas, equipamentos esportivos, mortes no trânsito | 2 dias | SIDRA + DataSUS |
| 6 | Teste de convergência com o IDSC (valores x nosso cálculo) | 1 dia | (1)–(5) |

**Regra de ouro em todas as etapas:** indicador novo entra com o **nome, a unidade e
a fórmula do órgão que o publica**, e nunca substitui um indicador existente —
convive com ele, cada um com sua fonte declarada.
