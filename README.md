# Painel ODS · Paraná

Painel de indicadores dos Objetivos de Desenvolvimento Sustentável (ODS) para os
**399 municípios do Paraná**, com foco em Guarapuava. É um site estático: roda
abrindo o `prototipo.html` direto no navegador, sem servidor e sem internet.

```
prototipo.html          o painel (4 visões)
prototipo.js            aplicação (interface, navegação, estado)
prototipo.css           design system
core.js                 núcleo de cálculo (estatística) — testável fora do navegador
scripts/                pipeline de dados (Python) e testes
data/bi/                payload gerado (o que o navegador carrega)
data/geo/               malha dos municípios e de-para com o IBGE
DECISOES.md             decisões do projeto + metodologia (curado à mão)
DATA_SCHEMA.md          dicionário de dados (gerado)
REVISAO_TECNICA.md      diagnóstico técnico e recomendações
```

---

## 1. Como usar

**Abrir o painel:** dê duplo clique em `prototipo.html` (funciona em `file://`).

**Para desenvolver** (recarregamento sem cache e recarga de tela):

```bash
python scripts/serve.py 8777     # http://127.0.0.1:8777/prototipo.html
```

**Visões:** Visão geral · Explorador · Comparador · Revisão.
O estado da tela (município, indicador, ano) fica na URL — dá para mandar um link
com a tela já aberta. O botão **Imprimir** gera a versão para PDF.

---

## 2. Pipeline de dados

Os dados de origem ficam em `Base de Dados/` (38 planilhas) e `Dicionário/`
(1 planilha). **Ordem obrigatória** (a saída de uma etapa é entrada da outra):

```bash
python scripts/00_build_geo.py       # de-para município -> IBGE (código + RGInt)
python scripts/01_build_catalog.py   # lê as 38 planilhas -> catalog.json + long.csv.gz
python scripts/04_build_populacao.py # população do IBGE (estimativas + censos)
python scripts/03_build_bi.py        # monta o payload do navegador (data/bi/)
python scripts/02_gen_schema.py      # gera DATA_SCHEMA.md (numeros calculados)
```

Regras do pipeline:

- cada etapa tem **checagens de contrato** que falham alto (assert), não apenas avisos;
- `03_build_bi.py` grava um **manifesto** (`BI.build.id`) em todos os arquivos do
  payload e **sincroniza o `prototipo.html`** com a versão do build;
- o app confere a integridade no boot: se os arquivos forem de gerações
  diferentes, ele **recusa renderizar** em vez de mostrar dados trocados;
- `02_gen_schema.py` **nunca** sobrescreve `DECISOES.md` (as decisões são curadas à mão).

**Testes:**

```bash
node scripts/06_test_core.js    # 54 asserções sobre estatística, chaves e contrato do payload
```

---

## 3. Identidade dos dados (o ponto mais importante)

| Chave | Onde | Quando usar |
|---|---|---|
| `chave` | nome original da coluna de origem | em qualquer artefato versionado (ex.: `polaridade.json`) — **estável entre versões da base** |
| `id` | hash curto de 8 caracteres da `chave` | dentro do app (DOM, chaves de objeto) |
| `BI.build.id` | manifesto do payload | para conferir que índice e valores são da mesma geração |

> Não use ids posicionais (a ordem do catálogo) em nada que atravesse versões:
> uma planilha nova desloca tudo e a decisão do revisor cairia no indicador errado.

---

## 4. Onde mexer em cada coisa

| Assunto | Arquivo |
|---|---|
| Metodologia (percentil, ranking, regra de síntese) | `core.js` + `DECISOES.md` §2 |
| Rótulos curtos, indicador principal de cada ODS, elegibilidade da taxa | `scripts/03_build_bi.py` (`GRUPOS_CURTOS`, `PRINCIPAL_POR_ODS`, `UNIDADES_PROPORCIONAIS`) |
| Justificativa da polaridade automática | `scripts/03_build_bi.py` (`polaridade()`) |
| Parsing dos valores, ausência de dados | `scripts/01_build_catalog.py` (`clean()`, `NULL_TOKENS`) |
| População (denominador das taxas calculadas) | `scripts/04_build_populacao.py` |
| Interface, navegação, mapa, gráficos | `prototipo.js` + `prototipo.css` |

---

## 5. Regras que o painel não pode violar

1. **Zero não é ausente** — nem no ETL, nem no mapa, nem no ranking.
2. **Unidade oficial sempre visível** — nenhuma conversão (a taxa derivada é marcada com `*`).
3. **Recorte nunca soma com Total.**
4. **Nenhuma média simples onde falta denominador.**
5. **Juízo bom/ruim só com polaridade declarada** — “sem juízo” é resposta legítima.
6. **Dado antigo é sinalizado, nunca escondido.**
7. **Fórmula derivada é rotulada como derivada.**

---

## 6. Pendência aberta

A **revisão de polaridade dos 194 indicadores** (aba Revisão): marcar um a um
“menor é melhor / sem juízo / maior é melhor” e exportar o JSON. O arquivo sai
indexado pela `chave` e vira o padrão de `pol` no gerador — assim a decisão
passa a valer para todo mundo, não só para quem revisou no navegador.
