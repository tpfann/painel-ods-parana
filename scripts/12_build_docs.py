"""
Etapa 12: transforma os documentos de referencia em HTML para o painel.

Os arquivos .md (metodologia, dicionario, fontes, convergencia) nao rendem no
navegador: no GitHub Pages o .md e servido como texto/arquivo, e em file:// ele
nem abre. Aqui eles viram HTML de verdade, embutido em data/bi/docs.js, e o
painel abre num leitor proprio (mesma fonte, tabelas formatadas, sem internet).

    python scripts/12_build_docs.py

Ordem na atualizacao: 01 -> 04 -> 03 -> 02 -> 12 (depois 10 ou 11 para publicar).
"""

from __future__ import annotations

import json
import os
import re
import sys

try:
    import markdown
except ImportError:  # pragma: no cover
    sys.exit("falta a biblioteca 'markdown': python -m pip install markdown")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(ROOT, "data", "bi", "docs.js")

# id do documento -> (titulo no leitor, arquivo, descricao curta)
DOCS = [
    ("metodologia", "Metodologia e decisões", "DECISOES.md",
     "Como cada indicador é calculado, polaridade, espelhos e o que ficou de fora"),
    ("dicionario", "Dicionário de dados", "DATA_SCHEMA.md",
     "Todos os indicadores, grupos, medidas, recortes e unidades"),
    ("fontes", "Fontes oficiais", "data/FONTES.md",
     "Registro das fontes, situação de cada uma e o que está pendente"),
    ("convergencia", "Convergência com o IDSC", "data/CONVERGENCIA.md",
     "Confronto dos nossos números com o índice oficial do IDSC-BR"),
]

# links entre documentos viram abertura do leitor, nao download de .md
LINK_PARA_DOC = {
    "DECISOES.md": "metodologia",
    "DATA_SCHEMA.md": "dicionario",
    "data/FONTES.md": "fontes",
    "data/CONVERGENCIA.md": "convergencia",
    "fontes.csv": "data/fontes.csv",
}


def converte(md: str) -> str:
    html = markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    for alvo, destino in LINK_PARA_DOC.items():
        if destino.startswith("data/"):
            html = html.replace('href="%s"' % alvo, 'href="%s"' % destino)
        else:
            html = html.replace('href="%s"' % alvo, 'href="#" data-doc="%s"' % destino)
    # tabelas largas rolam na horizontal dentro do leitor
    html = html.replace("<table>", '<div class="md-tabela"><table>').replace("</table>", "</table></div>")
    return html


def main() -> None:
    saida = {}
    for ident, titulo, arquivo, descricao in DOCS:
        caminho = os.path.join(ROOT, arquivo)
        if not os.path.exists(caminho):
            sys.exit("documento ausente: %s (rode as etapas anteriores)" % arquivo)
        with open(caminho, encoding="utf-8") as fh:
            md = fh.read()
        html = converte(md)
        if "<h1" not in html:
            html = "<h1>%s</h1>%s" % (titulo, html)
        saida[ident] = {
            "titulo": titulo,
            "arquivo": arquivo.replace("\\", "/"),
            "descricao": descricao,
            "linhas": md.count("\n") + 1,
            "html": html,
        }

    with open(DESTINO, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Documentacao em HTML (gerada por scripts/12_build_docs.py) */\n")
        fh.write("window.BI = window.BI || {};\n")
        fh.write("window.BI.docs = ")
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")

    kb = os.path.getsize(DESTINO) / 1024
    print("docs.js gerado (%.0f KB): %s" % (kb, ", ".join(saida)))
    for ident, d in saida.items():
        print("  %-13s %-26s %4d linhas de .md" % (ident, d["arquivo"], d["linhas"]))


if __name__ == "__main__":
    main()
