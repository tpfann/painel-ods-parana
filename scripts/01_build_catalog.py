"""
Le os 38 arquivos .xlsx da pasta 'Base de Dados' e o Dicionario, sem carregar
os dados inteiros em memoria de forma desnecessaria, e gera:

  - data/catalog.json      (metadados de cada indicador + cobertura temporal)
  - data/long.csv.gz       (base normalizada em formato longo, comprimida)

Formato de origem (todas as planilhas):
    Assunto | Localidade | Ano | <coluna do indicador> (1..N colunas)

Codigos de ausencia encontrados: '...', '-', '..' e celula vazia.

Aviso de parsing: o separador de milhar brasileiro ('1.234') so e convertido
quando ha virgula decimal ('1.234,5'); senao o numero seria lido 1000x menor.
Zeros sao valores reais e nunca viram nulo.

Uso: python scripts/01_build_catalog.py
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "Base de Dados")
DICT_DIR = os.path.join(ROOT, "Dicionário")
OUT = os.path.join(ROOT, "data")

NULL_TOKENS = {"...", "-", "..", "", "NA", "nd", "s/i"}
N_MUNICIPIOS_ESPERADO = 399


def clean(v):
    """Converte para float ou None. Zero e valor real."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN do pandas/Excel
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in NULL_TOKENS:
        return None
    # numero brasileiro: 1.234,56 -> 1234.56 ; 1.234 (milhar) -> 1234
    if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d+", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    elif re.fullmatch(r"\d+,\d+", s):
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load_dictionary() -> pd.DataFrame:
    path = glob.glob(os.path.join(DICT_DIR, "*.xlsx"))[0]
    df = pd.read_excel(path, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def ods_number(filename: str) -> int:
    m = re.search(r"Objetivo\s+(\d+)", filename)
    return int(m.group(1)) if m else -1


def slug(text: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:80]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    dic = load_dictionary()
    dic_by_name = {str(r["Nome da Variável"]).strip(): r for _, r in dic.iterrows()}

    files = sorted(glob.glob(os.path.join(BASE, "*.xlsx")))
    catalog = []
    frames = []
    unmatched = []

    for path in files:
        fname = os.path.basename(path)
        raw = pd.read_excel(path, sheet_name=0)
        # remove colunas totalmente vazias (presentes em algumas planilhas)
        raw = raw.dropna(axis=1, how="all")
        cols = list(raw.columns)
        meta_cols, ind_cols = cols[:3], cols[3:]

        assert meta_cols == ["Assunto", "Localidade", "Ano"], (fname, meta_cols)

        raw["Ano"] = pd.to_numeric(raw["Ano"], errors="coerce").astype("Int64")
        raw["Localidade"] = raw["Localidade"].astype(str).str.strip()

        for col in ind_cols:
            col = str(col)
            name = col.strip()
            d = dic_by_name.get(name)
            if d is None:
                unmatched.append((fname, name))
                d = {}

            series = raw[col].map(clean)
            sub = pd.DataFrame(
                {
                    "localidade": raw["Localidade"],
                    "ano": raw["Ano"],
                    "indicador": name,
                    "valor": series,
                }
            )

            # duplicidade (localidade, ano)?
            dupes = int(sub.duplicated(["localidade", "ano"]).sum())

            sel = sub["valor"].notna()
            per_year = (
                sub[sel].groupby("ano").size().to_dict() if sel.any() else {}
            )
            # anos com pelo menos 1 valor
            years_any = sorted(int(y) for y in per_year)
            # anos com cobertura >= 80% dos municipios (399)
            n_mun = sub[~sub["localidade"].str.startswith("RGInt") & (sub["localidade"] != "Estado do Paraná")]["localidade"].nunique()
            years_full = sorted(int(y) for y, n in per_year.items() if n >= 0.8 * n_mun)

            cat = {
                "arquivo": fname,
                "ods": ods_number(fname),
                "indicador": name,
                "indicador_slug": slug(name),
                "grupo_tema": d.get("Tabela Ipardes"),
                "meta_ods": d.get("Meta"),
                "codigo_ods": d.get("Número da Variável"),
                "definicao": d.get("Definição / Notas"),
                "formula": d.get("Fórmula de Cálculo"),
                "fonte": d.get("Fonte(s)"),
                "atualizado_em": str(d.get("Última atualização")),
                "n_linhas": int(len(sub)),
                "n_localidades": int(sub["localidade"].nunique()),
                "n_municipios": int(n_mun),
                "tem_agregado_regional": bool(sub["localidade"].str.startswith("RGInt").any()),
                "ano_min": int(min(years_any)) if years_any else None,
                "ano_max": int(max(years_any)) if years_any else None,
                "anos_com_dados": years_any,
                "anos_cobertura_80": years_full,
                "pct_ausente": round(100 * (1 - sel.mean()), 1),
                "duplicados": dupes,
                "unidade": "%" if "(%)" in name or "Percentual" in name or "Propor" in name else "",
            }
            catalog.append(cat)
            frames.append(sub[sel].assign(ods=cat["ods"], arquivo=fname))

    long = pd.concat(frames, ignore_index=True)
    long.to_csv(os.path.join(OUT, "long.csv.gz"), index=False, compression="gzip")
    with open(os.path.join(OUT, "catalog.json"), "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=1)

    # ---- relatorio compacto ----
    print(f"arquivos={len(files)} indicadores={len(catalog)} linhas_longas={len(long):,}")
    print(f"colunas sem match no dicionario: {len(unmatched)}")
    for u in unmatched[:5]:
        print("   ", u)
    print(f"duplicados (localidade,ano) total: {sum(c['duplicados'] for c in catalog)}")

    locs = long["localidade"].unique()
    print(f"localidades distintas={len(locs)} | estado={('Estado do Paraná' in locs)} | "
          f"rgint={sum(1 for l in locs if l.startswith('RGInt'))}")
    print(f"anos: {long['ano'].min()}..{long['ano'].max()}")
    by_file = Counter(c["arquivo"] for c in catalog)
    for f in files:
        cs = [c for c in catalog if c["arquivo"] == os.path.basename(f)]
        c0 = cs[0]
        print(
            f"{c0['ods']:>2} | {by_file[os.path.basename(f)]:>2} cols | "
            f"{c0['ano_min']}-{c0['ano_max']} | mun={c0['n_municipios']} | "
            f"ausente={sum(x['pct_ausente'] for x in cs)/len(cs):5.1f}% | {os.path.basename(f)[:70]}"
        )

    # ---- checagens de contrato (falham alto) ----
    n_mun_total = sum(1 for l in locs if not l.startswith("RGInt") and l != "Estado do Paraná")
    assert n_mun_total == N_MUNICIPIOS_ESPERADO, (
        "esperados %d municipios, vieram %d" % (N_MUNICIPIOS_ESPERADO, n_mun_total))
    assert sum(c["duplicados"] for c in catalog) == 0, "ha duplicados (localidade, ano)"
    assert not unmatched, "colunas sem match no dicionario: %s" % unmatched[:3]
    assert len({c["indicador"] for c in catalog}) == len(catalog), "indicadores duplicados no catalogo"
    sem_dado = [c["indicador"] for c in catalog if c["ano_min"] is None]
    assert len(sem_dado) <= 2, "indicadores sem nenhum dado além do esperado: %s" % sem_dado
    if sem_dado:
        print("indicadores 100%% vazios (ignorados no BI): %s" % sem_dado)
    print("checagens de contrato: OK")


if __name__ == "__main__":
    main()
