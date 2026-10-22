# DECISÕES — Painel ODS · Paraná

> Documento **curado à mão** — decisões do projeto, com o cliente, e a metodologia aplicada.
> Não é gerado por script: `scripts/02_gen_schema.py` gera apenas `DATA_SCHEMA.md`
> (inventário e catálogo) e **nunca sobrescreve este arquivo**.
>
> Última atualização: **21/10/2026** · Build do payload: ver `DATA_SCHEMA.md` §1.

---

## 1. Decisões fechadas com o cliente

| # | Tema | Decisão |
|---|---|---|
| 1 | **Polaridade** | Proposta automaticamente (+1 melhor / −1 pior / 0 sem juízo) e revisada um a um na aba **Revisão**; as escolhas são exportadas em `polaridade.json`, **indexado pela chave de negócio** (nome da coluna de origem), nunca por posição |
| 2 | **Benchmark** | Paraná + mediana dos 399 municípios + RGInt do município + posição no ranking + top 10 |
| 3 | **Agregado regional ausente** | Quando o dado não existe no nível regional, o nível regional não é exibido (sem inventar agregação) |
| 4 | **Curadoria** | Exibir os 194 indicadores com dados (não reduzir a uma síntese de ~40) |
| 5 | **Escopo de recortes** | Cor/raça, sexo, rural e urbana entram na v1 |
| 6 | **Mapa** | Coroplético dos 399 municípios (malha IBGE), com **dois filtros** (ODS + indicador), rótulo “pior/melhor” ou “menor/maior” conforme o indicador tenha juízo de valor |
| 7 | **Série 2025** | Tratada como definitiva |
| 8 | **Zero × ausente** | `...`, `-`, `..` e vazio viram ausente (`—`); `0` é valor real e é plotado e ranqueado como tal. Em contagens com muitos zeros simultâneos, a posição vira “empate: N municípios” |
| 9 | **Unidades** | Cada indicador mantém a unidade oficial (por 100 mil, por mil, %); **nunca** há conversão entre bases; moeda é exibida na unidade do arquivo (“R$ mil”) |
| 10 | **Último dado** | Posições relativas, destaques e mapa usam o **último dado disponível** de cada indicador; o ano aparece em todos os itens e anteriores a 2025 ganham **selo âmbar**; a partir de 3 anos de defasagem o Explorador mostra **aviso de série desatualizada** |
| 11 | **Fonte** | Open Sans empacotada localmente (`assets/fonts/`), pesos 400–600 |
| 12 | **Contagens** | Volume absoluto **não** tem juízo bom/ruim: fica fora de “melhores posições / pontos de atenção” e do mapa |
| 13 | **Taxa derivada (por 100 mil hab.)** | Só para contagens cujo numerador conta **pessoas/eventos** (óbitos, vínculos de emprego): 37 das 40 contagens. “Unidades atendidas” (água/esgoto) e “consumidores” (energia) **não** são pessoas → ficam no absoluto |
| 14 | **Recortes no mapa** | Só `Total` (os recortes ficam no Explorador e no Comparador) |
| 15 | **Cobertura desigual dos ODS** | Manter como está; a contagem de indicadores por ODS fica visível nos seletores |
| 16 | **Ano global** | O seletor da barra superior vale só para Explorador e Comparador (na Visão geral aparece desativado); quando o ano escolhido não tem dado, usa-se o último anterior, com aviso |
| 17 | **Card de síntese** | “Semáforo de ODS”: percentil médio do município nos indicadores comparáveis de cada ODS (verde = acima da mediana, vermelho = abaixo, cinza = ODS sem indicador comparável) |
| 18 | **Layout** | Barra superior de 78 px, 28 px entre título/menu/seletores, 40 px até o conteúdo; seletores do mapa empilhados, com rótulo e mesma largura |
| 19 | **Filtros** | Explorador: seletor de ODS com descrição e contagem. Comparador: ODS e indicador em seletores separados |
| 20 | **Proveniência** | Arquivo de origem e data de atualização da fonte ficam visíveis no painel |

---

## 2. Metodologia das posições (regra vigente)

Esta seção define **como** o painel calcula posições e sínteses. Ela é aplicada por
`core.js` e verificada por `scripts/06_test_core.js`.

### 2.1 Ranking (posição competitiva)

- Posição = 1 + número de municípios **melhores** que o município.
- Empates **dividem** a colocação (padrão de competição).
- Se o maior grupo de empate passa de 30% dos municípios, a tela mostra
  “empate: N municípios” em vez de uma posição falsa.

### 2.2 Percentil (mid-rank, ciente de empates)

- Percentil = posição média do grupo de empate, normalizada pelos 399 municípios com dado.
- **Motivo:** com a definição “competitiva”, 354 municípios com 0 óbitos-mortais recebiam
  100% — número sem informação. Com mid-rank, o grupo recebe o percentil que realmente ocupa.

### 2.3 Regra de elegibilidade para síntese (hero, semáforo, destaques)

Um indicador **só** entra em síntese (card de capa, semáforo de ODS, “melhores posições /
pontos de atenção”) se cumprir **as três** condições:

| Condição | Limiar | Motivo |
|---|---|---|
| `n` (municípios com dado) | ≥ 30 | posição sem base de comparação não é posição |
| `empateFrac` (maior grupo de empate) | ≤ 0,30 | indicador que não discrimina não informa |
| `distintos` (valores distintos) | ≥ 5 | mesma razão, olhando o outro lado |

Indicadores fora da regra **continuam** acessíveis no Explorador e no mapa, e a tela
informa **quantos** e **por quê** ficaram de fora.

> **Impacto medido em Guarapuava (21/10/2026):** “acima da mediana” vai de 30/75 para 26/53;
> ODS 13 e ODS 16 passam a “—” no semáforo (nenhum indicador com poder de discriminação).

### 2.4 Quando o indicador entra no mapa

- **Medida comparável** (`percentual` ou `taxa`) e recorte `Total`.
- **Julgamento é opcional:** indicador “sem juízo de valor” (polaridade 0) **continua no mapa**,
  com legenda “menor/maior” (sem verde/vermelho). Ele é apenas excluído do *ranking* e das
  *sínteses*, onde o juízo é indispensável.

### 2.5 Séries com lacunas

- O eixo X é sempre o ano real.
- Entre dois pontos com mais de 1 ano de distância **não** se traça linha: o gráfico usa
  pontos isolados (caso típico: ODS 5, só em anos eleitorais).
- A tabela “Valores por ano” é a alternativa textual completa.

### 2.6 Denominadores

- População residente do IBGE (estimativas + Censos 2010 e 2022; 2007 e 2023 interpolados).
- O Estado e as RGInt são a **soma dos municípios**.
- Taxas calculadas (÷ população × 100.000) são **dado derivado, não oficial** — a tela marca
  com `*` e explica a fórmula em “Sobre o indicador”.
- Quando o denominador vem de um ano diferente do indicador (interpolação), a tela avisa.

### 2.7 Critérios de polaridade (decididos em 21/10/2026)

A polaridade deixou de ser adivinhada por palavra-chave e passou a ter **critério
explícito**, aplicado pelo gerador e registrado por indicador (`pol_motivo`):

| Caso | Polaridade | Critério |
|---|---|---|
| Mortalidade, mortes, incidência, doença, risco, desnutrição, baixo peso | **−1** | menos é melhor |
| Volume absoluto (unidades atendidas, consumidores, formalism de empregos) | **0** | volume não mede qualidade |
| Indicador estrutural/descritivo (participação setorial, % do VAB, VAF setorial) | **0** | não mede o desempenho do município (como no ODS 9.2.1 das ONU) |
| Cobertura, acesso, renda, registro civil, matrícula, proxy ambiental | **+1** | mais é melhor |
| Equidade de gênero (cadeiras na câmara, cargos gerenciais) | **+1** | mais representação é melhor |
| Diferenças/razões entre grupos | **0** | mede um intervalo entre grupos, não o município |

Resultado: **94 indicadores "menos é melhor", 90 "mais é melhor", 14 sem juízo de
valor**. Indicadores sem juízo **continuam no mapa** (legenda "menor/maior", sem
verde/vermelho), mas ficam **fora do ranking, das sínteses e dos destaques** — e
o cartão do ODS mostra o selo neutro.

**A revisão humana tem precedência:** se existir `data/polaridade.json` (exportado
pela aba Revisão), o gerador aplica as decisões do revisor **indexadas pela chave
de negócio** e **falha alto** se alguma chave não existir na base — não é
possível aplicar parte da revisão e publicar em silêncio.

### 2.8 Espelhos (mesma série em dois ODS)

Indicadores que pertencem legitimamente a dois ODS (ex.: mortes no trânsito, que é
do ODS 3 "Saúde" e do ODS 11 "Cidades Sustentáveis") entram como **espelho**:
mesmos valores (alias em JS, sem duplicar dado), id próprio e `espelho_de`
apontando a origem. A **síntese conta a série uma vez só** e o mapa não a repete;
o cartão do ODS informa que é a mesma série.

---

## 3. Pendências em aberto

| # | Pendência | Situação |
|---|---|---|
| 1 | Revisão de polaridade dos 194 indicadores | **Critérios definidos e aplicados pelo gerador** (21/10/2026, §2.7). A aba Revisão permite sobrescrever por indicador; o JSON exportado passa a ser o padrão do gerador, com validação ruidosa. A revisão do curador ainda é bem-vinda: o que vier de `data/polaridade.json` tem precedência |
| 2 | Revisão de polaridade dos 194 indicadores | Ferramenta pronta (aba Revisão). Falta o usuário percorrer e exportar `polaridade.json`; o JSON passa a ser o padrão de `pol` no gerador |
| 2 | Confirmar se indicadores com dado de 2016 (Proficiência 3º ano) devem seguir nas posições | Decidido em 21/10/2026: seguem, com selo âmbar e aviso de série desatualizada |
| 3 | Cobertura de RGInt em 48 indicadores | Depende de nova fonte com agregado regional; não é contornável no painel |

---

## 4. Princípios que o painel não pode violar

1. **Zero não é ausente** — nem no ETL, nem no mapa, nem no ranking.
2. **Unidade oficial sempre visível** — nenhuma conversão (exceto a taxa derivada, marcada com `*`).
3. **Recorte nunca soma com Total.**
4. **Nenhuma média simples onde falta denominador** — sem ponderar, não se agrega.
5. **Juízo bom/ruim só com polaridade declarada** — “sem juízo” é uma resposta legítima.
6. **Dado antigo é sinalizado, nunca escondido.**
7. **Fórmula derivada é rotulada como derivada** — dado oficial e cálculo nunca se misturam.
