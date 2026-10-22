# Convergência com o IDSC-BR

> Gerado por `scripts/08_test_convergencia.py` em 2026-10-22 09:36. Compara os nossos valores com os publicados pelo IDSC-BR (edição 2026), município a município, no mesmo ano e com a mesma unidade.

| Indicadores do IDSC | 100 |
| Pares curados e comparados | 12 |
| Pares sem correspondência | 1 |

## Comparação por indicador

| % | Indicador (IDSC) | Painel | Concordância | Sítios | Observação |
|---|---|---|---:|---:|---|
| 4 | Professores com formação em nível superior - Ensino Fund | Formação docente adequada | 0.8% | 263 | — |
| 2 | Desnutrição infantil (%) | Crianças desnutridas (até 2 anos) | 51.0% | 349 | — |
| 11 | Mortes no trânsito (100 mil habitantes) | Mortes no trânsito | 52.0% | 3990 | mesma série (espelho do ODS 11) |
| 4 | Acesso à internet nas escolas do ensino fundamental e mé | Infraestrutura das escolas | 73.5% | 4389 | — |
| 3 | Mortalidade materna (mil nascidos vivos) | Mortalidade materna | 86.7% | 3990 | — |
| 3 | Pré-natal insuficiente (%) | Pré-natal (7+ consultas) | 88.9% | 3990 | INVERSO: o IDSC mede pré-natal insuficiente (complemento do nosso) |
| 3 | Incidência de tuberculose (100 mil habitantes) | Incidência de Tuberculose | 89.7% | 3990 | — |
| 3 | Mortalidade neonatal (crianças de 0 a 27 dias) (mil nasc | Mortalidade neonatal | 93.6% | 3990 | — |
| 16 | Taxa de homicídio (100 mil habitantes) | Homicídios | 96.3% | 3990 | — |
| 3 | Mortalidade infantil (crianças menores de 1 ano) (mil na | Mortalidade infantil (< 1 ano) | 100.0% | 3990 | — |
| 2 | Baixo peso ao nascer (%) | Baixo peso ao nascer | 100.0% | 3990 | — |
| 3 | Mortalidade por Aids (100 mil habitantes) | Mortalidade por causas específicas | 100.0% | 3990 | — |

## Onde divergimos (abaixo de 90% de concordância)

**4** — IDSC: Professores com formação em nível superior - Ensino Fundamental - rede · painel: Formação docente adequada — concordância 0.8% em 263 pontos

  - unidade IDSC: % · unidade painel: %
  - fonte IDSC: INEP/Censo Escolar
  - 4118600 em 2019: nosso 0.0 · IDSC 97.0
  - 4118600 em 2020: nosso 0.0 · IDSC 96.9
  - 4118600 em 2018: nosso 0.0 · IDSC 94.4

**2** — IDSC: Desnutrição infantil (%) · painel: Crianças desnutridas (até 2 anos) — concordância 51.0% em 349 pontos

  - unidade IDSC: % · unidade painel: %
  - fonte IDSC: SISVAN
  - 4114351 em 2015: nosso 75.0 · IDSC 2.655
  - 4112603 em 2015: nosso 40.0 · IDSC 0.0
  - 4116950 em 2015: nosso 0.53 · IDSC 13.16

**11** — IDSC: Mortes no trânsito (100 mil habitantes) · painel: Mortes no trânsito — concordância 52.0% em 3990 pontos

  - unidade IDSC: 100 mil habitantes · unidade painel: 100 mil habitantes
  - fonte IDSC: DataSUS/SIM/Óbitos por causas externas
  - mesma série (espelho do ODS 11)
  - 4103479 em 2016: nosso 46.88 · IDSC 562.6
  - 4110003 em 2015: nosso 23.39 · IDSC 187.1
  - 4110656 em 2016: nosso 0.0 · IDSC 160.8

**4** — IDSC: Acesso à internet nas escolas do ensino fundamental e médio, na rede p · painel: Infraestrutura das escolas — concordância 73.5% em 4389 pontos

  - unidade IDSC: % · unidade painel: %
  - fonte IDSC: INEP/Censo Escolar
  - 4108007 em 2024: nosso 100.0 · IDSC 37.5
  - 4124905 em 2024: nosso 100.0 · IDSC 40.0
  - 4107702 em 2024: nosso 100.0 · IDSC 42.86

**3** — IDSC: Mortalidade materna (mil nascidos vivos) · painel: Mortalidade materna — concordância 86.7% em 3990 pontos

  - unidade IDSC: mil nascidos vivos · unidade painel: 100 mil nascidos vivos
  - fonte IDSC: DataSUS/SINASC
  - 4107520 em 2017: nosso 4545.45 · IDSC 45.45
  - 4124202 em 2015: nosso 4347.83 · IDSC 43.48
  - 4128302 em 2016: nosso 4166.67 · IDSC 41.67

**3** — IDSC: Pré-natal insuficiente (%) · painel: Pré-natal (7+ consultas) — concordância 88.9% em 3990 pontos

  - unidade IDSC: % · unidade painel: %
  - fonte IDSC: DataSUS/SINASC
  - INVERSO: o IDSC mede pré-natal insuficiente (complemento do nosso)
  - 4112801 em 2016: nosso 44.59 · IDSC 27.39
  - 4123709 em 2021: nosso 30.680000000000007 · IDSC 15.91
  - 4111704 em 2021: nosso 14.290000000000006 · IDSC 3.571

**3** — IDSC: Incidência de tuberculose (100 mil habitantes) · painel: Incidência de Tuberculose — concordância 89.7% em 3990 pontos

  - unidade IDSC: 100 mil habitantes · unidade painel: 100 mil habitantes
  - fonte IDSC: DataSUS/SINAN; DataSUS/Estimativas populacionais
  - 4127957 em 2024: nosso 24.38 · IDSC 121.9
  - 4116950 em 2021: nosso 0.0 · IDSC 59.83
  - 4117008 em 2015: nosso 71.78 · IDSC 11.96

## Como ler

- **Concordância** é a percentagem de pontos (município × ano) em que o nosso valor coincide com o do IDSC dentro da tolerância (1 p.p. para percentual, 5%% para taxa).
- Divergência **não** é necessariamente erro: os dois painéis podem usar anos diferentes para o mesmo indicador, denominadores diferentes ou recortes diferentes. O relatório mostra a fonte e a unidade de cada lado para permitir o julgamento.
- O teste é uma **rede de segurança**: se uma fonte oficial mudar de método, a divergência aparece aqui antes de o painel publicar número novo.

