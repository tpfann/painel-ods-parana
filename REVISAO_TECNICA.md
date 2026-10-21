# Revisão técnica e crítica — Painel ODS · Paraná

**Data:** 21/10/2026 · **Escopo:** `prototipo.html`, `prototipo.css`, `prototipo.js`, `core.js`, `scripts/00–06`, `data/bi/*`, `data/geo/*`, `DATA_SCHEMA.md`, `DECISOES.md`
**Natureza:** diagnóstico e proposta. **Nada foi implementado** — este documento é o insumo para a próxima rodada de trabalho.

> **Atualização de 21/10/2026 (tarde):** as recomendações foram **implementadas**.
> Estado de cada item: §3.1 (P0) — G1 ✅, G2 ✅, G3 ✅, E1 ✅, E2 ✅, E3 ✅, E4 ✅ ·
> §3.2 (P1) — P1.1 ✅, P1.2 ✅, P1.3 ✅, P1.4/1.5 ✅, P1.6 ✅, P1.7 ✅ ·
> §3.3 (P2) — P2.0 ✅ (primeiro commit + `.gitignore`), P2.1 ✅, P2.2 ✅, P2.3 ✅,
> P2.4 ✅, P2.5 ✅ (`scripts/06_test_core.js`, 54 asserções), P2.6 ✅ (intermediários fora
> do versionamento), P2.7 ✅, P2.8 ✅, P2.9 ✅ (Censo 2010 oficial), P2.10 ✅ (`README.md`),
> P2.11 ✅ (rodapé com build), P2.12 ✅ (projeção com correção de latitude).
> A metodologia nova está em **`DECISOES.md` §2**; o catálogo de dados gerado ficou em
> **`DATA_SCHEMA.md`** (números calculados) e as decisões curadas à mão em **`DECISOES.md`**.
> Efeito de E1 medido: “acima da mediana” passou de 30/75 para **26/53** e o semáforo
> de **5/10** para **5/8** ODS.

---

## 1. Resumo executivo

O protótipo é **funcional, coerente e honesto**: os dados conferem (399 municípios, join 1:1 com a malha, zero duplicatas, zero perda no de-para com o dicionário), a performance de render é de 10–40 ms, o tratamento de zero × ausente é consistente, e as decisões fechadas com o cliente estão documentadas.

O risco **não está no protótipo** — está no que acontece no dia em que a base for atualizada. Três defeitos de governança podem produzir **número errado em tela, sem erro, sem aviso**:

| # | Defeito | Consequência se a base mudar |
|---|---|---|
| **G1** | Identificadores de indicador são **posicionais** (`i0…i195`, por ordem do catálogo) | A revisão de polaridade (que é exportada em JSON keyed por `i12`) passa a ser aplicada ao **indicador errado**, em massa |
| **G2** | `scripts/02_gen_schema.py` **reescreve `DATA_SCHEMA.md` do zero** | Rodar `01`→`02` **apaga as 20 decisões registradas em §9** (o próprio arquivo diz "não editar à mão", mas §9 é manual) |
| **G3** | Não há **manifesto/build-id** entre `indice.js` e `val_odsN.js` | Um rebuild parcial (ou `data/bi/` compartilhado entre duas pessoas) desloca todos os ids e exibe **valores de um indicador no lugar de outro**, sem erro de console |

E há um defeito de **método estatístico** que já afeta a leitura de hoje: a métrica-âncora (percentil) não controla **empates massivos** — 25 dos 80 indicadores elegíveis têm mais de 30% dos municípios com o mesmo valor. O número de capa "30/75 acima da mediana" e o semáforo de ODS são **inflados por indicadores degenerados** (o caso extremo: *Mortalidade materna*, 354 de 399 municípios com o mesmo valor).

**Ordem sugerida:** G1–G3 → método do percentil → proveniência → UX do mapa/ranking → engenharia.

> Observação de contexto: o repositório **não tem nenhum commit** (todos os arquivos estão untracked, sem `.gitignore`). Não há, portanto, forma de saber qual versão da base produziu uma captura, uma decisão ou um `polaridade.json` — o que amplia o impacto de G1 e G3.

---

## 2. Método e evidências

Leitura integral de `prototipo.js` (1.313 linhas), `prototipo.css`, `prototipo.html`, `scripts/01–04`, `DATA_SCHEMA.md`. Verificações empíricas executadas sobre os dados e sobre a aplicação em execução:

- integridade do catálogo (196 indicadores, duplicatas, metadados);
- de-para município↔IBGE↔malha (399/399, 1:1, sem órfãos);
- sanitização do payload (busca por `<`, `>`, `"` nos metadados);
- recálculo independente de percentis, ranking e semáforo (em JS, fora do código do app) para separar "o que a tela mostra" de "o que o método deveria mostrar";
- cobertura por indicador (n de municípios com dado), empates, lacunas temporais;
- medição de carga, memória e tempo de render.

Números citados são medidos, não estimados.

---

## 3. Achados

### 3.1 Severidade P0 — bloqueiam uso institucional

#### G1. Identificadores posicionais tornam a revisão de polaridade insegura

- **Evidência:** `scripts/03_build_bi.py:208` → `"id": f"i{i}"`, onde `i` é o índice do indicador no catálogo (`enumerate(catalogo)`). O catálogo é ordenado por arquivo (`glob` + `sorted`), logo **basta uma planilha nova alphabetically anterior para deslocar todos os ids**.
- **Verificado:** `codigo_ods` (código do dicionário) **não** é chave — são 61 códigos distintos para 194 indicadores, com repetição de até 12× (os recortes compartilham o código do conceito). Já a chave `codigo|medida|recorte` é **única em 194/194**, e o `nome` original da coluna também é **único em 194/194**.
- **Impacto:** `prototipo.js:1031-1040` (`aplicarPolaridade`) aplica o JSON salvo por id sem nenhuma verificação de identidade. Se a base mudar, **as decisões do revisor entram no indicador errado** — e o painel continua "funcionando".
- **Proposta:**
  1. chave de negócio estável no catálogo: `id = slug(codigo_ods + medida + recorte)` (ou hash do `nome` da coluna de origem);
  2. `polaridade.json` passa a ser `{ "chave": -1, ... }` e o gerador valida que **toda** chave do JSON existe no catálogo (falha ruidosa se não);
  3. a aba Revisão mostra a chave ao lado do nome, para o revisor conferir.
- **Critério de aceite:** rodar `01` com uma planilha nova **alphabeticalmente anterior** não altera a associação indicador↔decisão; o JSON com uma chave inexistente é rejeitado com mensagem clara.

#### G2. O gerador de documentação apaga as decisões

- **Evidência:** `scripts/02_gen_schema.py:271-272` abre `DATA_SCHEMA.md` em modo `"w"` e escreve a lista montada do zero. O cabeçalho do arquivo gerado diz *"Não editar à mão"* — mas **§9.1/§9.2/§9.3 (20 decisões fechadas com o cliente) são manuais**. Hoje o arquivo está, inclusive, **internamente inconsistente**: §9.2 reescrito à mão ("§9.2 Abertas") convive com o §9 antigo ("9. Decisões pendentes") que o gerador escreveria por cima.
- **Proposta:** separar o documento em dois artefatos — `DATA_SCHEMA.md` (gerado: inventário, catálogo, armadilhas) e `DECISOES.md` (curado: decisões, pendências, metodologia) — com o gerador apenas **linkando** o segundo. Alternativa: o gerador lê o bloco §9 existente e o reinsere (marcador `<!-- INICIO DECISOES -->`).
- **Critério de aceite:** rodar `01`→`02` não altera uma linha de `DECISOES.md`.

#### G3. Não há contrato entre metadados e valores

- **Evidência:** `data/bi/indice.js` (282 KB) e `data/bi/val_odsN.js` (8 MB) são escritos em arquivos independentes; `indice.js` carrega `"gerado"` (data), mas **a UI nunca mostra** e **não há build-id, contador ou checksum** ligando os dois conjuntos.
- **Impacto:** com ids posicionais (G1), um `val_ods3.js` desatualizado ao lado de um `indice.js` novo desloca **todos** os valores — o painel mostra a série de um indicador no nome de outro, sem erro.
- **Proposta:** `BI.build = {id, gerado_em, n_indicadores, n_valores, hash}` gravado em todos os arquivos; na inicialização, o app verifica (a) que todo `ind.id` de `indice.js` tem array em `BI.valores`, (b) que `array.length == n_localidades × n_anos`, (c) que o `build.id` é igual em todos os arquivos; em caso de divergência, **exibir um aviso em tela cheia** em vez de renderizar.
- **Critério de aceite:** simular a troca de um `val_odsN.js` por uma versão antiga → o app recusa-se a renderizar com mensagem "payload inconsistente (build X vs Y)".

#### E1. A métrica-âncora não controla empates massivos

- **Evidência (recálculo independente):** dos **80** indicadores elegíveis para ranking/mapa, **25 têm mais de 30% dos municípios com o mesmo valor**. Casos extremos:
  - *Mortalidade materna* — **354 de 399** municípios com o mesmo valor;
  - *Infraestrutura das escolas* — 397/399, 382/399 e **399/399** (três recortes);
  - *Mortalidade por causas específicas* — até 386/399;
  - *Formação docente adequada* — **n = 1 município com dado** (dois indicadores).
- **Como o bug se manifesta:** `pctMap` (`prototipo.js:181-198`) usa *lowerBound/upperBound* → todos os municípios empatados recebem o **mesmo percentil extremo** (100% para o melhor valor, mesmo com 354Municipais empatados). Consequências medidas:
  - o card de capa **"30/75 acima da mediana"** vira **"26/53"** quando os indicadores massivamente empatados são excluídos;
  - o **semáforo de ODS muda**: ODS 3 de 41 → 47, ODS 5 de 41 → 27, e **ODS 13 e ODS 16 passam a "—"** (nenhum indicador com poder de discriminação) — ou seja, hoje o semáforo **diz que ODS 13 e 16 têm posição** justamente nos indicadores que a lista de "pontos de atenção" descarta;
  - indicadores com **n = 1** entram com peso 1 voto e percentil 0 ou 100.
- **Proposta (metodológica, prioridade máxima depois de G1–G3):**
  1. definir um **critério de honestidade** explícito: um indicador só é usado em síntese (hero, semáforo, destaques) se `n ≥ 30` **e** `empateFrac ≤ 0.3` **e** `distintos ≥ 5`; o motivo da exclusão passa a ser exibido ("excluído: 354 municípios empatados");
  2. o percentil passa a ser **percentil de/aws2** com correção por empates (mid-rank) ou a sintese passa a usar a **posição competitiva** (que já distingue empates) em vez do percentil bruto;
  3. o semáforo de ODS passa a ser ponderado pelo número de indicadores **com poder de discriminação** de cada ODS, e a mostrar "—" quando o ODS não tem nenhum (em vez de um número herdado de 1 indicador degenerado);
  4. publicar a regra no `DECISOES.md` (metodologia é decisão, não detalhe de implementação).
- **Critério de aceite:** o número de capa e o semáforo passam a ser reproduzíveis a partir de um cálculo documentado, e a lista de indicadores excluídos é auditável.

#### E2. Série com lacunas desenhadas como linha contínua

- **Evidência:** ODS 5 — *Cadeiras em câmaras de vereadores* — tem dados apenas em **2012, 2016, 2020, 2024** (lacuna de 4 anos). O `lineChart` (`prototipo.js:390-407`) une os pontos com segmentos contínuos, **sugerindo interpolação entre eleições**. O próprio `DATA_SCHEMA.md` §8 item 8 define a mitigação: *"usar barras/pontos"* — **não implementada**. O mesmo vale para *Remanescente florestal* (lacuna de 3 anos) e para qualquer indicador com anos faltantes na janela.
- **Proposta:** no `lineChart`, quando houver lacuna > 1 ano entre dois pontos, desenhar **apenas marcadores** (sem segmento) ou segmento **tracejado** com aviso "sem dados entre 2012 e 2016"; alternativamente, plotar o eixo X com todos os anos da janela e deixar as lacunas vazias (o eixo já é linear no ano real — falta apenas a geometria do traço).
- **Critério de aceite:** nenhum gráfico do app sugere continuidade onde há ausência de dado.

#### E3. O mapa é um gráfico sem leitura

- **Evidência:** os 399 `<path>` do mapa **não têm `title`**, não são focáveis por teclado (`tabindex` = 0 em 0 de 399) e não há rótulo do município em foco. A leitura de um valor exige abrir o Explorador.
- **Proposta:** tooltip no hover com município, valor, unidade, ano, posição no ranking e link "abrir no Explorador"; clique no município abre-o como foco; rótulo do município em foco; camada de foco com contorno e semitransparência; foco por teclado (o SVG pode receber `tabindex` por município).
- **Critério de aceite:** hover em qualquer município devolve nome + valor + ano; `Tab` alcança os municípios.

#### E4. Falta o top 10, previsto na especificação

- **Evidência:** a conversa de requisito registra "posição no ranking + **top 10**". Hoje o card de ranking mostra **9 linhas na janela do município** (`prototipo.js:959`), sem a lista dos melhores.
- **Proposta:** alternar "janela do município" / "top 10" / "bottom 10" no card de ranking.
- **Critério de aceite:** o card permite ver o top 10 do indicador com um clique.

### 3.2 Severidade P1 — comprometem a leitura e a defendibilidade

#### P1.1. Proveniência existe e não chega à tela

- **Evidência:** `01_build_catalog.py:138` captura `atualizado_em` (datas que vão de 12/09/2019 a 30/04/2026) e `arquivo` (planilha de origem). `03_build_bi.py` **não transporta nenhum dos dois** para `indice.js`; a tela mostra só `fonte` (fonte conceitual do dicionário).
- **Impacto:** o gabinete não consegue responder "de quando é esse número?" nem "de qual planilha veio?". Para um painel institucional, isso é requisito, não item de luxo.
- **Proposta:** incluir `arquivo`, `atualizado_em`, `n_municipios`, `pct_ausente` no `indice.js` e exibir em "Sobre o indicador" + rodapé ("base gerada em DD/MM/AAAA · 38 planilhas · IBGE/Censo 2022 para denominadores").

#### P1.2. Polaridade automática sem justificativa, e polaridade implícita em contagens

- **Evidência:** `03_build_bi.py:101-110` decide por palavra-chave no nome; 96 indicadores ficam +1, 92 −1, 6 = 0. Contagens têm polaridade implícita ("Atendimento de esgoto" = +1, "Consumidores de energia" = +1 — "mais consumidores é melhor" é discutível).
- **Proposta:** gravar **o motivo** da proposta automática (`pol_motivo`: "palavra-chave 'Mortalidade'") e mostrá-lo na aba Revisão; mover a decisão para o catálogo (`pol`, `pol_motivo`, `pol_revisado_por`, `pol_revisado_em`), não para o JS do protótipo.

#### P1.3. "Sem juízo de valor" faz o indicador sumir sem aviso

- **Evidência:** `elegivelRanking` (`prototipo.js:649-652`) exclui `pol === 0` **e** tipo ≠ percentual/taxa. Hoje 7 indicadores percentuais/taxas com `pol = 0` ficam fora do mapa e fora dos destaques **sem qualquer aviso** — se o revisor marcar "sem juízo" na aba Revisão, o indicador desaparece do mapa e do ranking. O efeito colateral de uma escolha legítima (ausência de juízo) é **sumir do produto**.
- **Proposta:** separar os dois conceitos — `elegivelMapa` (tem medida comparável) de `elegivelRanking` (tem juízo) — e manter no mapa os indicadores sem juízo, com legenda "sem juízo de valor" (menor/maior) e sem cor verde/vermelha; na aba Revisão, avisar "sem juízo → fora do ranking e dos destaques".

#### P1.4. Regras de negócio duplicadas em Python e JavaScript

- **Evidência:** o "indicador principal de cada ODS" existe em dois lugares com duas lógicas diferentes: `PRINCIPAL` no `prototipo.js:598-611` (busca por *substring* em `nome`, ex.: `"per Capita"` para o ODS 8) e a seleção equivalente dentro de `03_build_bi.py` (por `GRUPOS_CURTOS`). `GRUPOS_CURTOS` (38 chaves) também é duplicado entre o gerador e o texto do `DATA_SCHEMA`.
- **Risco:** a busca por substring pode escolher o indicador errado se a ordem do catálogo mudar (ex.: outro indicador contendo "per Capita" antes).
- **Proposta:** `principal_ods` como **campo do catálogo** (id explícito), consumido pelo app; um único lugar de verdade.

#### P1.5. Regex de elegibilidade para taxa derivada mora no front-end

- **Evidência:** `UNIDADE_NAO_PESSOAL` (`prototipo.js:88`) decide por regex se uma contagem pode virar taxa por 100 mil — uma **regra de negócio** (definida com o cliente) dentro da camada de apresentação.
- **Proposta:** mover para o catálogo (`proporcional: true|false` + justificativa), como se fez com `pol`.

#### P1.6. Acessibilidade e canal de cor

- **Evidência:** cor de texto secundário `#7C889B` sobre branco = **3,59:1** (abaixo de AA 4,5:1) em textos de 10,5–11 px (ano, notas, legendas); o mapa **só** codifica por cor, sem valores numéricos; as abas não têm `role="tablist"/"tab"`; o gráfico depende de hover (mouse) para ler valores; a tabela "Valores por ano" é a única alternativa textual ✓ (esse ponto está bom).
- **Proposta:** escurecer o secundário para ≥ 4,5:1 (ex.: `#5A6678`), tipografia mínima 11 px, rótulos numéricos nas faixas do mapa ou padrão de textura/hachura para daltonismo, `role`/`aria-selected` nas abas, e tabela equivalente ao gráfico (a tabela "Valores por ano" já existe), navegação por teclado no mapa.

#### P1.7. Estado compartilhável e material de levamento

- **Evidência:** não há URL/estado compartilhável (o gabinete não consegue mandar "olha o indicador X do município Y" por link) nem exportação (PDF/PNG/impressão) para ata de reunião.
- **Proposta:** serializar `state` no `location.hash` (município, indicador, ano, modo, abas) e um botão "Imprimir/PDF" com folha de estilo de impressão (o layout é responsivo e já imprime razoavelmente, mas sem ajuste).

### 3.3 Severidade P2 — engenharia, robustez e higiene

| # | Achado | Evidência | Proposta |
|---|---|---|---|
| P2.0 | **Sem histórico de versão**: o repositório não tem nenhum commit (tudo untracked), não há `.gitignore` e o payload de 11,6 MB de intermediário está no diretório de trabalho. Não existe forma de saber qual versão da base gerou uma captura de tela, uma decisão ou um `polaridade.json` | `git status` → todos os arquivos untracked | primeiro commit com `.gitignore` (planilhas, `data/long.csv.gz`, `data/catalog.json`, `_tmp_*`) e tag por versão de base; `data/bi/` versionado por release |
| P2.1 | **Injeção de HTML latente**: metadados interpolados em `innerHTML` e em atributos `title="…"` sem escape. Hoje **não quebra** (nenhum `medida`/`grupo` tem aspas; `<` só aparece como "(&lt; 1 ano)"), mas 21 definições contêm `"`/`<`/`>` — qualquer metadado novo com `<b>` ou aspas quebra o DOM silenciosamente | `prototipo.js:716, 778, 822, 884, 991-992, 1103` | helper `esc()` aplicado a todo valor vindo de dados; teste de fumaça que injere `<script>` no catálogo |
| P2.2 | **Estado global acoplado**: o seletor de ano do indicador no Explorador escreve o `state.ano` global, que também define o ano padrão do Comparador. Trocar de indicador altera o histórico exibido | `prototipo.js:1011-1015` vs `1163` | separar `anoGlobal` de `anoPorIndicador`; explicitar na UI qual vale |
| P2.3 | **Índices mágicos**: `raw(ind, 0, ano)` presume que o Estado é a localidade 0; `state.cmp = [g, 0, r]` idem; `LOC.findIndex(l => l.n === "RGInt de " + loc.reg)` faz lookup por texto | `prototipo.js:870, 1298-1300` | `LOC_ID.estado`, `LOC_ID.rgint(nome)` por id/código |
| P2.4 | **`ANO_REF` derivado do dado** (máx. dos anos presentes): se a base ganhar 2026, o limiar do selo âmbar se move sozinho, sem decisão registrada | `prototipo.js:640` | constante de política (`ANO_REF = 2025`) + `ANO_MAX_DADOS` exibido separadamente |
| P2.5 | **Sem testes**: só `node --check` (sintaxe). Nada garante que o ETL, o percentil, o ranking, os empates, o zero × ausente ou o join município↔malha continuam corretos | — | suíte mínima: (a) contrato de dados (contagens, unicidade de chaves, cobertura), (b) unitários de estatística (percentil, ranking, quintis) contra casos conhecidos, (c) golden test do `indice.js` |
| P2.6 | **Payload e repositório**: 8,28 MB de JS carregados com parser eager; `data/long.csv.gz` (11,6 MB) e `catalog.json` versionados junto com o entregável | `data/bi/*`, `data/long.csv.gz` | manter o payload (runtime medido: DCL 157 ms, 33 MB de heap, render 10–40 ms — **não é gargalo**), mas tirar os **intermediários** do versionamento e documentar `.gitignore`; opcionalmente, carregar `val_ods*.js` sob demanda (só o ODS aberto) |
| P2.7 | **Higiene**: 4 scripts temporários na raiz (`_tmp_geo.py`, `_tmp_geo2.py`, `_tmp_m.py`, `_tmp_p.py`); CSS `.chips` morto; docstring do `01` promete `long.parquet` e o código grava `long.csv.gz`; código morto (`years_ok` no `01`, `fmtAno`, `el()` com parâmetro não usado, `or "Total"` inerte no `parse()` do `03`) | raiz, `prototipo.css:237`, `01:7,120`, `03:95` | limpar e remover; um lint simples no pipeline |
| P2.8 | **ETL: `clean()` com risco latente** de "1.234" → 1,234 (separador de milhar). **Verificado: 0 divergências hoje** — as únicas células de texto são `...`/`-`. O risco é para o próximo arquivo | `01:45` |regex que só troca `.` quando há separador de milhar **e** vírgula decimal, com teste unitário; asserção (não `print`) quando `n_municipios` ≠ 399 |
| P2.9 | **População**: 2010 foi **interpolado** embora exista Censo 2010 oficial (IBGE agregado 200); 2023 interpolado; checagens são `print`, não asserção; `popDe` cai no ano mais próximo **em silêncio** | `04_build_populacao.py` | usar o censo oficial de 2010; asserção de cobertura; sinalizar na UI quando o denominador vem de ano diferente do indicador |
| P2.10 | **Sem README**: ninguém (nem o cliente) sabe a ordem de build, o que é cada script, como abrir e como publicar | — | `README.md` com: pré-requisitos, ordem de execução, o que é gerado, decisões de arquitetura, e "como publicar uma nova versão" |
| P2.11 | **Sem manifesto de versão no rodapé** | `indice.js` tem `gerado`, não exibido | rodapé com "base gerada em … · build …" |
| P2.12 | **Mapa: projeção cartográfica simplificada** (equirretangular linear, sem correção de latitude) e geometria sem simplificação (31.397 vértices, 373 KB) | `03_build_bi.py:275-296` | projeção com correção de latitude (ou Lambert) e simplificação de vértices (tolerance ~0,01°) para arquivo menor e visual mais correto |

---

## 4. O que está bom e deve ser preservado

Registrado para que a próxima rodada não desfaça o que está resolvido:

- **Zero × ausente** tratado de forma consistente no ETL, na escala (`0` é valor real), no mapa (cinza = sem dado) e nas notas de tela.
- **Empate explícito** no ranking ("133 municípios compartilham o mesmo valor — empates dividem a colocação"), em vez de posição falsa.
- **De-para município↔IBGE↔malha íntegro**: 399/399, 1:1, zero órfãos, zero município sem código e sem região.
- **Metadados do dicionário 100% casados** (0 definição/fórmula/fonte vazias) e **zero duplicatas** (localidade, ano).
- **Selo de dado antigo + aviso de série desatualizada** — transparência raro em painéisoprimeiro nível.
- **Aba de revisão de polaridade** com persistência, filtro e exportação — resolve a curadoria sem planilha paralela.
- **Unidade oficial preservada** (sem converter moeda, sem misturar escalas) e denominador de população versionado e checado (soma 2022 = 11.444.380 = Censo PR ✓).
- **Performance de render**: 10 ms (Visão geral) e 40 ms (Explorador) — não é gargalo.

---

## 5. Recomendações priorizadas

| Prio | # | Recomendação | Esforço | Risco se não feito |
|---|---|---|---|---|
| **P0** | G1 | Chave de negócio estável + validação da chave na revisão | M | Decisões de polaridade aplicadas ao indicador errado |
| **P0** | G2 | Separar `DATA_SCHEMA.md` (gerado) de `DECISOES.md` (curado) | P | Perda de 20 decisões documentadas |
| **P0** | G3 | Manifesto/build-id + verificação de integridade no boot | M | Dados silenciosamente errados após rebuild parcial |
| **P0** | E1 | Regra de elegibilidade para síntese (n, empates, distintos) + auditoria | M | Números de capa inflados e sem lastro metodológico |
| **P1** | E2 | Gráfico com lacunas desenhadas como pontos/tracejado | P | Leitura de tendência inexistente (eleições) |
| **P1** | E3 | Tooltip/valor no mapa + foco por teclado + rótulo do município em foco | M | Mapa não comunicável em reunião |
| **P1** | E4 | Top 10 / bottom 10 no card de ranking | P | Requisito acordado não atendido |
| **P1** | P1.1 | `arquivo` + `atualizado_em` na tela e no rodapé | M | Sem resposta para "de quando é?" |
| **P1** | P1.2 | Justificativa da polaridade automática + pol no catálogo | M | Revisão às cegas |
| **P1** | P1.3 | Separar "sem juízo" de "fora do ranking" | P | Escolha legítima faz o indicador sumir |
| **P1** | P1.4/1.5 | Regras de negócio no catálogo (principal de ODS, elegibilidade da taxa) | M | Regra duplicada em duas camadas |
| **P1** | P1.6 | Contraste, roles, teclado, alternativa textual do mapa | M | Inacessível e ilegível em projetor/TV de gabinete |
| **P2** | P2.1 | `esc()` em todo dado interpolado + teste de fumaça | P | Fragilidade silenciosa |
| **P2** | P2.5 | Suíte de testes (contrato de dados + estatística) | G | Regressão sem detecção |
| **P2** | P2.7/2.10/2.11 | Limpeza, README, rodapé de versão | P | Onboarding e auditoria comprometidos |
| **P2** | P2.2/2.3/2.4 | Estado e índices mágicos | M | Manutenção frágil |

**Estimativas:** P = até 1 dia · M = 2–4 dias · G = mais de uma semana.

---

## 6. O que **não** fazer (armadilhas a evitar)

1. **Não usar o percentil bruto em nenhuma síntese** sem o controle de empates — o caso "354 municípios com 0 óbitos" transforma um indicador degenerado em "100% acima da mediana" e contamina qualquer média.
2. **Não reaproveitar ids posicionais em qualquer artefato versionado** (polaridade, favoritos, links) — chave de negócio antes de qualquer exportação.
3. **Não derivar taxa por 100 mil de numerador não populacional** (unidades atendidas, consumidores) — a decisão do cliente está registrada e é tecnicamente correta: a unidade não é pessoa.
4. **Não misturar escalas no mesmo cartão** (mortalidade neonatal por mil × materna por 100 mil) sem a unidade visível.
5. **Não substituir valor ausente por zero** em nenhuma agregação — e não agregar recortes com o Total.
6. **Não recalcular agregado regional por média simples** onde a fonte não traz o agregado: 48 indicadores só existem no nível municipal; recalcular sem ponderar seria inventar dado.
7. **Não deixar o semáforo ser mais fino que a evidência**: um ODS com 1 indicador degenerado não é "acima" nem "abaixo" da mediana.
8. **Não manter números "snapshot" hardcoded no gerador de documentação** (§1 e §4.2 do `DATA_SCHEMA.md` têm contagens fixas) — eles envelhecem sem erro.

---

## 7. Rastreabilidade

| Tema | Onde está |
|---|---|
| ids posicionais | `scripts/03_build_bi.py:208` |
| aplicação da revisão por id | `prototipo.js:1031-1040`, `1042-1052` |
| sobrescrita do `DATA_SCHEMA.md` | `scripts/02_gen_schema.py:258-272` |
| ausência de manifesto/build-id | `scripts/03_build_bi.py:230-272` |
| percentil e empates | `prototipo.js:181-208` (`pctMap`, `rankOf`) |
| filtro de empates nos destaques | `prototipo.js:755` (`st.empateFrac > 0.3`) |
| semáforo de ODS | `prototipo.js:660-691` |
| cobertura da regra do "acima da mediana" | `prototipo.js:662-670` |
| gráfico com lacunas | `prototipo.js:390-407` |
| mapa sem tooltip | `prototipo.js:494-524` |
| ranking de 9 linhas | `prototipo.js:958-980` |
| elegibilidade (juízo × medida) | `prototipo.js:649-652` |
| heurística de polaridade | `scripts/03_build_bi.py:101-110` |
| regex de elegibilidade da taxa | `prototipo.js:85-93` |
| `ANO_REF` derivado do dado | `prototipo.js:640` |
| estado/ano acoplado | `prototipo.js:1011-1015`, `1163` |
| índice mágico do Estado | `prototipo.js:870`, `1298-1300` |
| interpolação de população | `scripts/04_build_populacao.py:49-66` |
| `clean()` do ETL | `scripts/01_build_catalog.py:34-49` |
| projeção do mapa | `scripts/03_build_bi.py:275-322` |

---

## 8. Como validar a próxima rodada

1. `python scripts/01_build_catalog.py && python scripts/02_gen_schema.py` → **nenhuma decisão perdida** (G2) e nenhum número snapshot divergente do recálculo.
2. Adicionar uma planilha-teste **alphabeticalmente anterior** → build completo → a revisão de polaridade continua associada aos mesmos indicadores (G1).
3. Trocar `val_ods3.js` por uma versão antiga → o app **recusa** a renderizar (G3).
4. Recalcular, fora do app, percentis/empates/semáforo dos 80 elegíveis e bater com o que a tela mostra (E1).
5. Percorrer as 4 abas com teclado only, com leitor de tela e com contraste medido (P1.6).
6. Conferir que nenhum gráfico sugere continuidade sobre lacuna (E2) e que todo hover de mapa devolve valor (E3).
