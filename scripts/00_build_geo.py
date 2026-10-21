"""
Etapa 00 do pipeline: baixa a lista de municipalities do Paraná (IBGE) e monta o
de-para município -> codigo IBGE + RGInt (Regiao Geografica Intermediaria).

Entradas : API IBGE (sem autenticacao)
Saidas   : data/geo/ibge_municipios.json
          [{cod, nome, rgint, rgint_id, rgint_imediata}, ...]  (399 municipios)

Uso: python scripts/00_build_geo.py
"""

from __future__ import annotations

import gzip
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "geo")
URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/41/municipios"
UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / ETL)", "Accept-Encoding": "gzip"}

# as 6 RGInt que aparecem no painel (confere com as intermediarias do IBGE)
EXPECTED_RGINT = {
    "Cascavel", "Curitiba", "Guarapuava", "Londrina", "Maringá", "Ponta Grossa",
}


def get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        bruto = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or bruto[:2] == b"\x1f\x8b":
            bruto = gzip.decompress(bruto)
    return json.loads(bruto.decode("utf-8"))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    dados = get(URL)

    saida = []
    for m in dados:
        imediata = m.get("regiao-imediata") or {}
        inter = (imediata.get("regiao-intermediaria") or {})
        saida.append({
            "cod": str(m["id"]),
            "nome": m["nome"],
            "rgint": inter.get("nome"),
            "rgint_id": str(inter.get("id")) if inter.get("id") else None,
            "rgint_imediata": imediata.get("nome"),
        })

    caminho = os.path.join(OUT, "ibge_municipios.json")
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)

    # --- verificacoes (falha ruidosa, nao apenas print) ---
    assert len(saida) == 399, f"esperados 399 municipios, vieram {len(saida)}"
    assert len({m["cod"] for m in saida}) == 399, "codigo IBGE duplicado"
    assert all(m["rgint"] for m in saida), "municipio sem RGInt"
    achados = {m["rgint"] for m in saida}
    assert achados == EXPECTED_RGINT, f"RGInt inesperadas: {sorted(achados ^ EXPECTED_RGINT)}"

    print("municipios: %d | RGInt distintas: %d | %s" % (
        len(saida), len(achados), ", ".join(sorted(achados))))
    print("escrito:", caminho)


if __name__ == "__main__":
    main()
