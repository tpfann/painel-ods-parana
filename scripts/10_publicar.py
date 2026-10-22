"""
Etapa 10: monta a pasta de publicacao (pronta para o GitHub Pages).

Copia o painel para public/ com duas garantias:

  1. a aba de REVISAO nao existe no publicado (revisar polaridade e privilegio
     do curador; quem acessa so le);
  2. o app publicado ignora qualquer revisao salva no navegador do visitante
     (todo mundo ve os mesmos numeros).

    python scripts/10_publicar.py            # monta public/
    python scripts/10_publicar.py --abrir    # e ja abre no navegador

O conteudo publicado:
    public/prototipo.html   (versao publica)
    public/prototipo.css
    public/core.js
    public/assets/…         (fontes Open Sans)
    public/data/bi/…         (payload)
    public/DECISOES.md, DATA_SCHEMA.md, FONTES.md, CONVERGENCIA.md

Publicar no GitHub Pages: envie a pasta public/ para a branch gh-pages
(ou configure a acao .github/workflows/pages.yml, que ja faz isso).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "public")
BI = os.path.join(ROOT, "data", "bi")


def remover_revisao(html: str) -> str:
    html = re.sub(r'\s*<button data-view="revisao"[^>]*>Revisão</button>', "", html)
    html = re.sub(r'\s*<!-- =+ REVISÃO =+ -->\s*<section class="view" id="view-revisao">[\s\S]*?</section>',
                   "", html)
    html = re.sub(r'\s*<section class="view" id="view-revisao">[\s\S]*?</section>', "", html)
    return html


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abrir", action="store_true", help="abre a versao publicada no navegador")
    args = ap.parse_args()

    if os.path.isdir(PUB):
        shutil.rmtree(PUB)
    os.makedirs(PUB, exist_ok=True)

    # html publica (sem a aba de revisao)
    with open(os.path.join(ROOT, "prototipo.html"), encoding="utf-8") as fh:
        html = fh.read()
    html = remover_revisao(html)
    with open(os.path.join(PUB, "prototipo.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    # raiz do site = o painel: o link divulgado fica curto (.../painel-ods-parana/)
    with open(os.path.join(PUB, "index.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)

    for arq in ("prototipo.css", "core.js", "prototipo.js"):
        shutil.copy2(os.path.join(ROOT, arq), os.path.join(PUB, arq))

    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(PUB, "assets"))
    shutil.copytree(BI, os.path.join(PUB, "data", "bi"))

    # documentos de referencia (publicos)
    os.makedirs(os.path.join(PUB, "data"), exist_ok=True)
    for arq in ("DECISOES.md", "DATA_SCHEMA.md"):
        p = os.path.join(ROOT, arq)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(PUB, arq))
    for arq in ("FONTES.md", "CONVERGENCIA.md"):
        p = os.path.join(ROOT, "data", arq)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(PUB, "data", arq))
    # o .md de fontes aponta para o registro em CSV: precisa existir publicado
    p = os.path.join(ROOT, "data", "fontes.csv")
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(PUB, "data", "fontes.csv"))

    # a versao publica ignora revisao local (marca em todos os arquivos do payload)
    for nome in sorted(os.listdir(os.path.join(PUB, "data", "bi"))):
        if not nome.endswith(".js"):
            continue
        p = os.path.join(PUB, "data", "bi", nome)
        with open(p, encoding="utf-8") as fh:
            t = fh.read()
        if '"revisao":true' in t:
            t = t.replace('"revisao":true', '"revisao":false')
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(t)
    print("  payload publicado: revisao desativada")

    # 404.html (GitHub Pages usa para rotas desconhecidas)
    with open(os.path.join(PUB, "404.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("<!doctype html><meta charset='utf-8'><title>Painel ODS</title>"
                 "<p style='font-family:sans-serif;padding:32px'>Página não encontrada — "
                 "<a href='/'>voltar ao painel</a>.</p>\n")

    # GitHub Pages: desliga o Jekyll (serve os arquivos como estao)
    with open(os.path.join(PUB, ".nojekyll"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("")

    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(PUB) for f in fs)
    print("publicacao montada: %s (%.1f MB)" % (os.path.relpath(PUB, ROOT), total / 1e6))
    print("  aba de revisao removida: %s" % ("sim" if "revisao" not in html else "NAO"))
    print("  arquivos:", sum(len(fs) for _, _, fs in os.walk(PUB)))

    if args.abrir:
        import webbrowser
        webbrowser.open("file:///" + os.path.join(PUB, "prototipo.html").replace("\\", "/"))


if __name__ == "__main__":
    main()
