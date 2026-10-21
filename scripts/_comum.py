"""
Funcoes compartilhadas entre as etapas do pipeline (00 -> 01 -> 02 -> 04 -> 03).

Concentra o que precisa ser identico em mais de um script:
  - normalizacao de texto (de-para por nome);
  - a lista de localidades (estado -> RGInt -> municipios), que define o layout
    achatado dos valores e portanto PRECISA ser identica em 03 e 04;
  - a chave de negocio estavel dos indicadores (independente da ordem do catalogo).
"""

from __future__ import annotations

import hashlib
import unicodedata


def norm(s: str) -> str:
    """Normaliza texto para de-para por nome (sem acento, minusculo, sem espacos nas bordas)."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def localidades(long, ibge) -> list:
    """Ordem canonica das localidades: Estado -> RGInt -> municipios (alfabetico).

    long : DataFrame com a coluna 'localidade'
    ibge : lista de dicts {cod, nome, rgint}

    O indice de cada localidade e o que addressa os valores achatados
    (idx = localidade_idx * n_anos + ano_idx) em 03 e 04.
    """
    cod_por_nome = {norm(m["nome"]): m["cod"] for m in ibge}
    reg_por_nome = {norm(m["nome"]): m.get("rgint") for m in ibge}

    todos = set(long["localidade"].unique())
    muns = sorted(l for l in todos if not l.startswith("RGInt") and l != "Estado do Paraná")
    regs = sorted(l for l in todos if l.startswith("RGInt"))

    out = []
    for l in ["Estado do Paraná"] + regs + muns:
        if l == "Estado do Paraná":
            out.append({"n": l, "t": "estado"})
        elif l.startswith("RGInt"):
            out.append({"n": l, "t": "regiao", "reg": l.replace("RGInt de ", "")})
        else:
            out.append({"n": l, "t": "municipio",
                        "cod": cod_por_nome.get(norm(l)),
                        "reg": reg_por_nome.get(norm(l))})

    sem_cod = [l["n"] for l in out if l["t"] == "municipio" and not l["cod"]]
    sem_reg = [l["n"] for l in out if l["t"] == "municipio" and not l["reg"]]
    if sem_cod or sem_reg:
        raise ValueError("de-para com o IBGE falhou: sem cod=%s sem rgint=%s"
                         % (sem_cod[:5], sem_reg[:5]))
    return out


def chave_negocio(nome: str) -> str:
    """Chave estavel do indicador: o proprio nome da coluna de origem.

    E estavel porque nao depende da ordem do catalogo nem da ordem das planilhas,
    e e unica (verificada em 194/194). E o que deve ser usado em polaridade.json.
    """
    return str(nome).strip()


def id_curto(chave: str) -> str:
    """Identificador curto e estavel (hash do nome de origem) para uso em DOM/JS."""
    return hashlib.sha1(chave.encode("utf-8")).hexdigest()[:8]
