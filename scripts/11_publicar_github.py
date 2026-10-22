"""
Etapa 11: publica o painel no GitHub Pages pela branch gh-pages.

Metodo: a pasta public/ (versao publica, sem a aba de Revisao) vira a raiz da
branch gh-pages. Nao depende de runner do GitHub Actions — a publicacao
acontece quando voce roda este script, com o repositorio ja autenticado.

    python scripts/11_publicar_github.py            # constroi e publica
    python scripts/11_publicar_github.py --so-pasta # so monta public/ (sem publicar)

Requer: git instalado, gh autenticado e o remoto 'origin' configurado.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "public")
REPO = "tpfann/painel-ods-parana"
BRANCH = "gh-pages"


def run(cmd, cwd=ROOT, check=True):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        print("ERRO:", " ".join(cmd) if isinstance(cmd, list) else cmd)
        print((p.stdout or "") + (p.stderr or ""))
        sys.exit(1)
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-pasta", action="store_true", help="apenas monta a pasta public/")
    args = ap.parse_args()

    run([sys.executable, os.path.join(ROOT, "scripts", "10_publicar.py")])

    if args.so_pasta:
        print("pasta montada; nada foi publicado.")
        return

    # branch orfa: so a versao publica, com um unico commit por publicacao
    # (pasta temporaria unica: no Windows o git pode segurar arquivos do repo)
    tmp = tempfile.mkdtemp(prefix="painelods-pub-")
    shutil.copytree(PUB, tmp, dirs_exist_ok=True)
    for junk in (".DS_Store",):
        for r, _, fs in os.walk(tmp):
            for f in fs:
                if f == junk:
                    os.remove(os.path.join(r, f))

    print("publicando a branch", BRANCH, "…")
    run(["git", "init", "-q"], cwd=tmp)
    run(["git", "checkout", "-q", "-b", BRANCH], cwd=tmp)
    run(["git", "add", "-A"], cwd=tmp)
    run(["git", "-c", "user.name=Painel ODS", "-c", "user.email=painel@local",
         "commit", "-q", "-m", "publicacao automatica do painel ODS"], cwd=tmp)
    run(["git", "remote", "add", "origin", "https://github.com/%s.git" % REPO], cwd=tmp)
    run(["git", "push", "--force", "origin", BRANCH], cwd=tmp)
    shutil.rmtree(tmp, ignore_errors=True)   # o git pode manter arquivo preso no Windows

    # garante que o Pages usa a branch
    p = subprocess.run(["gh", "api", "-X", "PUT",
                        "repos/%s/pages" % REPO,
                        "-f", "source[branch]=%s" % BRANCH,
                        "-f", "source[path]=/"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        print("aviso: nao foi possivel ajustar a origem do Pages:", (p.stderr or "").strip()[:200])
    else:
        print("origem do Pages ajustada para a branch", BRANCH)

    print("publicado: https://%s.github.io/%s/" % (REPO.split("/")[0], REPO.split("/")[1]))


if __name__ == "__main__":
    main()
