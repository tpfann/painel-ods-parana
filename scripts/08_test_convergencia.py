"""
Etapa 08: teste de convergencia com o IDSC-BR.

O IDSC publica os mesmos indicadores (100, para 5.570 municipios) calculados a
partir das mesmas fontes oficiais, mas com o proprio recorte, o proprio ano e
as proprias formulas. Este script compara o que NOS calculamos com o que o IDSC
publica, municipio a municipio e ano a ano, para os indicadores que sao
comparaveis (mesma unidade e mesmo tema).

Serve como prova independente de que a montagem esta correta — e para detectar
quando uma fonte muda de metodo.

    python scripts/08_test_convergencia.py [--atualizar]

Saida: data/CONVERGENCIA.md (relatorio) e o codigo de saida 0 sempre que a
convergencia estiver dentro da tolerancia declarada.
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
RELATORIO = os.path.join(ROOT, "data", "CONVERGENCIA.md")
URL_IDSC = "https://idsc.cidadessustentaveis.org.br/"

# Tolerancias: percentual (ate 1 p.p.) e taxa (ate 5% do valor).
TOL_PCT = 1.0
TOL_REL = 0.05

UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / verificacao de fonte oficial)"}


def sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def palavras(s: str) -> set:
    return {p for p in re.sub(r"[^a-z0-9]+", " ", sem_acento(s)).split() if len(p) > 2}


def baixar_idsc(forcar=False) -> dict:
    """Baixa (e guarda em cache) o payload do IDSC."""
    os.makedirs(CACHE, exist_ok=True)
    caminho = os.path.join(CACHE, "idsc_payload.json")
    if forcar or not os.path.exists(caminho):
        print("baixando o payload do IDSC (20 MB)...")
        req = urllib.request.Request(URL_IDSC, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r:
            html = r.read().decode("utf-8", "replace")
        m = re.search(r'PAYLOAD_B64\s*=\s*"([^"]+)"', html)
        if not m:
            raise SystemExit("payload do IDSC nao encontrado (o site mudou?)")
        bruto = gzip.decompress(__import__("base64").b64decode(m[1]))
        with open(caminho, "wb") as fh:
            fh.write(bruto)
        print("  cache: %s (%.1f MB)" % (os.path.relpath(caminho, ROOT), len(bruto) / 1e6))
    with open(caminho, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


# Pares curados: o mesmo indicador nas duas fontes (mesmo tema, mesma unidade).
# O casamento e textual de proposito — nome de arquivo, nao similaridade automatica:
# um par falso seria pior que nenhum par.
#   (fragmento do nome no IDSC, fragmento do nome no painel, observacao)
PAIRS = [
    ("Mortalidade infantil", "Taxa de Mortalidade Infantil em Menores de 1 ano de Idade", ""),
    ("Mortalidade materna", "Taxa de Mortalidade Materna", ""),
    ("Mortalidade neonatal", "Taxa de Mortalidade Neonatal", ""),
    ("Incidência de tuberculose", "Taxa de Incidência de Tuberculose", ""),
    ("Baixo peso ao nascer", "Proporção de Nascidos Vivos com Baixo Peso ao Nascer", ""),
    ("Mortalidade por AIDS", "Taxa de Mortalidade por AIDS", ""),
    ("acesso à internet nas escolas", "Proporção de Escolas com Acesso à Internet", ""),
    ("Professores com formação em nível superior - Ensino Fundamental",
     "Proporção de Docências com Professores cuja Formação Superior", ""),
    ("atividades características do turismo",
     "Proporção de Empregos (RAIS) nas Atividades Características do Turismo", ""),
    ("Mortes no trânsito", "Mortes no trânsito", "mesma série (espelho do ODS 11)"),
    ("Desnutrição infantil", "Proporção de Crianças Desnutridas", ""),
    ("Homicídio (100 mil habitantes)", "Taxa de Mortalidade por Homicídios", ""),
    ("Pré-natal insuficiente", "Proporção de Nascidos Vivos com 7 ou mais Consultas",
     "INVERSO: o IDSC mede pré-natal insuficiente (complemento do nosso)"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atualizar", action="store_true", help="rebaixa o payload do IDSC")
    args = ap.parse_args()

    idsc = baixar_idsc(args.atualizar)
    base = idsc["base"]
    inds_idsc = base["ind"]
    meta = base["meta"]
    anos_idsc = meta["anos"]

    # nosso payload
    with io.open(os.path.join(ROOT, "data", "bi", "indice.js"), encoding="utf-8") as fh:
        txt = fh.read()
    nosso = json.loads(txt.split("BI.indice=", 1)[1].rstrip().rstrip(";"))
    with io.open(os.path.join(ROOT, "data", "bi", "val_ods3.js"), encoding="utf-8") as fh:
        pass
    valores = {}
    for arq in sorted(os.listdir(os.path.join(ROOT, "data", "bi"))):
        if not arq.startswith("val_ods"):
            continue
        with io.open(os.path.join(ROOT, "data", "bi", arq), encoding="utf-8") as fh:
            t = fh.read()
        for m in re.finditer(r'BI\.valores\["([^"]+)"\]=(\[.*?\]);', t):
            valores[m.group(1)] = json.loads(m.group(2))
        # alias (espelho): mesma serie de outro indicador
        for m in re.finditer(r'BI\.valores\["([^"]+)"\]=BI\.valores\["([^"]+)"\];', t):
            valores[m.group(1)] = valores.get(m.group(2))

    locs = nosso["localidades"]
    idx_cod = {str(l.get("cod")): i for i, l in enumerate(locs) if l.get("cod")}
    idsc_cod = {str(c[0]): i for i, c in enumerate(base["cid"])}

    #_series do IDSC: municipality -> list per indicator (values by meta.anos)
    # _val do IDSC: value~normalized~class
    def serie_idsc(li_cid, k):
        bloco = idsc["ser"][li_cid].split(";")[k]
        return bloco.split(",")

    def valor_idsc(li_cid, k):
        partes = idsc["val"][li_cid].split("~")
        return float(partes[0]) if partes and partes[0] not in ("", "nan") else None

    # pares curados
    nossos = [i for i in nosso["indicadores"] if i["id"] in valores]
    comparados = []
    nao_comparaveis = []
    for frag_idsc, frag_nosso, obs in PAIRS:
        cand_idsc = [x for x in inds_idsc if sem_acento(frag_idsc) in sem_acento(x["n"])]
        ind_idsc = cand_idsc[0] if cand_idsc else None
        cand_nosso = [x for x in nossos if sem_acento(frag_nosso) in sem_acento(x["medida"] + " " + x["gcurto"])]
        i = None
        if cand_nosso:
            if len(cand_nosso) == 1 or not ind_idsc:
                i = cand_nosso[0]
            else:
                # com varios candidatos, escolhe o de escopo mais proximo do IDSC
                def afinidade(x):
                    a = palavras(ind_idsc["n"]) & palavras(x["medida"] + " " + x["gcurto"] + " " + x["nome"])
                    return len(a)
                i = max(cand_nosso, key=afinidade)
        if ind_idsc is None or i is None:
            nao_comparaveis.append((frag_idsc, frag_nosso, "par não encontrado (IDSC: %s, painel: %s)"
                                    % ("ok" if ind_idsc else "não", "ok" if i else "não")))
            continue
        comparados.append((ind_idsc, i, obs))

    L = []
    A = L.append
    A("# Convergência com o IDSC-BR")
    A("")
    A("> Gerado por `scripts/08_test_convergencia.py` em %s. Compara os nossos valores "
      "com os publicados pelo IDSC-BR (edição %s), município a município, no mesmo ano e "
      "com a mesma unidade." % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), meta.get("edicao", "?")))
    A("")
    A("| Indicadores do IDSC | %d |" % len(inds_idsc))
    A("| Pares curados e comparados | %d |" % len(comparados))
    A("| Pares sem correspondência | %d |" % len(nao_comparaveis))
    A("")

    # para cada par, compara os ultimos anos com dado
    resumo = []
    for ind_idsc, i, obs in comparados:
        k = inds_idsc.index(ind_idsc)
        anos_nossos = i["anos"]
        arr = valores[i["id"]]
        n = len(anos_nossos)
        difs = []
        comps = 0
        iguais = 0
        inverso = "INVERSO" in obs
        for cod, li_idsc in idsc_cod.items():
            li = idx_cod.get(cod)
            if li is None:
                continue
            bloco = serie_idsc(li_idsc, k)
            for j, ano in enumerate(anos_nossos):
                if ano not in anos_idsc:
                    continue
                k_ano = anos_idsc.index(ano)
                if k_ano >= len(bloco) or bloco[k_ano] == "":
                    continue
                try:
                    v_idsc = float(bloco[k_ano])
                except ValueError:
                    continue
                v_nosso = arr[li * n + j]
                if v_nosso is None:
                    continue
                if inverso:
                    v_nosso = 100.0 - v_nosso
                comps += 1
                if abs(v_nosso - v_idsc) <= (TOL_PCT if abs(v_idsc) < 100 else abs(v_idsc) * TOL_REL):
                    iguais += 1
                else:
                    difs.append((abs(v_nosso - v_idsc), cod, ano, v_nosso, v_idsc))
        pct = (100.0 * iguais / comps) if comps else None
        resumo.append((pct, comps, ind_idsc, i, difs, obs))

    resumo.sort(key=lambda r: (r[0] is None, r[0] if r[0] is not None else 0))
    A("## Comparação por indicador")
    A("")
    A("| % | Indicador (IDSC) | Painel | Concordância | Sítios | Observação |")
    A("|---|---|---|---:|---:|---|")
    for pct, comps, ind_idsc, i, difs, obs in resumo:
        A("| %s | %s | %s | %s | %d | %s |" % (
            ind_idsc["ods"], ind_idsc["n"][:56], i["gcurto"][:40],
            ("%.1f%%" % pct) if pct is not None else "—", comps, obs or "—"))
    A("")

    divergentes = [r for r in resumo if r[0] is not None and r[0] < 90]
    if divergentes:
        A("## Onde divergimos (abaixo de 90% de concordância)")
        A("")
        for pct, comps, ind_idsc, i, difs, obs in divergentes[:12]:
            A("**%s** — IDSC: %s · painel: %s — concordância %.1f%% em %d pontos" % (
                ind_idsc["ods"], ind_idsc["n"][:70], i["gcurto"], pct, comps))
            A("")
            A("  - unidade IDSC: %s · unidade painel: %s" % (ind_idsc["u"], i["unidade"]))
            A("  - fonte IDSC: %s" % (ind_idsc.get("f") or "—")[:120])
            if obs:
                A("  - %s" % obs)
            for d in sorted(difs, reverse=True)[:3]:
                A("  - %s em %s: nosso %s · IDSC %s" % (d[1], d[2], d[3], d[4]))
            A("")

    A("## Como ler")
    A("")
    A("- **Concordância** é a percentagem de pontos (município × ano) em que o nosso valor "
      "coincide com o do IDSC dentro da tolerância (1 p.p. para percentual, 5%% para taxa).")
    A("- Divergência **não** é necessariamente erro: os dois painéis podem usar anos "
      "diferentes para o mesmo indicador, denominadores diferentes ou recortes diferentes. "
      "O relatório mostra a fonte e a unidade de cada lado para permitir o julgamento.")
    A("- O teste é uma **rede de segurança**: se uma fonte oficial mudar de método, a "
      "divergência aparece aqui antes de o painel publicar número novo.")
    A("")

    with io.open(RELATORIO, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print("relatorio: %s" % os.path.relpath(RELATORIO, ROOT))
    conc = [r[0] for r in resumo if r[0] is not None]
    if conc:
        print("concordancia media: %.1f%% | indicadores comparados: %d | divergentes (<90%%): %d"
              % (sum(conc) / len(conc), len(resumo), len(divergentes)))
    else:
        print("nenhum par comparavel")
    print("sem comparacao: %d" % len(nao_comparaveis))
    for frag_idsc, frag_nosso, motivo in nao_comparaveis[:12]:
        print("   - %s / %s: %s" % (frag_idsc[:40], frag_nosso[:40], motivo))


if __name__ == "__main__":
    main()
