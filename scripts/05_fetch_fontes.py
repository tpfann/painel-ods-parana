"""
Etapa 05: registro e aquisicao das fontes oficiais.

O painel nao depende de planilha nenhuma: cada arquivo de "Base de Dados/" e um
espelho local de uma fonte oficial. Este script mantem o REGISTRO dessas fontes
(data/fontes.csv), com URL, periodicidade, data da ultima aquisicao e checksum,
e avisa quando a fonte oficial ja lancou uma nova edicao (lembrete) ou quando
a URL direto deixou de responder.

    python scripts/05_fetch_fontes.py              # checa o status e atualiza o registro
    python scripts/05_fetch_fontes.py --inicializar  # cria o registro a partir do catalogo
    python scripts/05_fetch_fontes.py --estrito      # sai com codigo 1 se algo estiver pendente

Saidas:
    data/fontes.csv             registro editavel a mao (fonte de verdade das URLs)
    data/FONTES.md              relatorio de status (gerado)
    data/bi/fontes_status.json   status por fonte (consumido pelo painel)

O registro e manual de proposito: quando a URL muda, corrige-se a coluna
url_direta no CSV e o historico fica no git. O script nunca sobrescreve as
colunas curadas (tipo_acesso, url_direta, url_landing, periodicidade,
mes_esperado, observacao) -- so preenche as que estiverem vazias.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "Base de Dados")
CATALOGO = os.path.join(ROOT, "data", "catalog.json")
REGISTRO = os.path.join(ROOT, "data", "fontes.csv")
RELATORIO = os.path.join(ROOT, "data", "FONTES.md")
STATUS_JSON = os.path.join(ROOT, "data", "bi", "fontes_status.json")

UA = {"User-Agent": "Mozilla/5.0 (Painel ODS / verificacao de fontes oficiais)"}
TIMEOUT = 20

COLUNAS = [
    "id", "ods", "arquivo", "publicador", "fonte_dicionario", "tipo_acesso",
    "url_direta", "url_landing", "periodicidade", "mes_esperado",
    "edicao_fonte", "ultima_aquisicao", "sha256", "status", "observacao",
]

# perfil por publicador: como se acessa, onde procurar a nova edicao e quando ela sai.
# url_landing = pagina estavel onde a nova URL e encontrada (e onde o "lembrete" aponta).
PERFIS = {
    "STN/SICONFI": dict(
        publicador="Tesouro Nacional / SICONFI (FINBRA)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=9,
        url_landing="https://www.gov.br/fazenda/pt-br/orgaos/siconfi/dados-abertos",
        observacao="FINBRA: planilha anual por município e por ente; a URL muda a cada edição."),
    "SISVAN": dict(
        publicador="Ministério do Desenvolvimento Social / SISVAN",
        tipo_acesso="download", periodicidade="anual", mes_esperado=9,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Desnutrição infantil (VIGIANTE); no dicionário aparece como SIAB, "
                   "que é o nome antigo do mesmo sistema."),
    "SINASC": dict(
        publicador="Ministério da Saúde / SINASC (nascidos vivos)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=8,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="CSVs anuais de nascidos vivos (DataSUS)."),
    "SIH": dict(
        publicador="Ministério da Saúde / SIH (AIDS)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=5,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Base de casos de AIDS por município."),
    "SIM": dict(
        publicador="Ministério da Saúde / SIM (óbitos)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=8,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="CSVs anuais de óbitos (DataSUS), por causa e por município."),
    "SINAN": dict(
        publicador="Ministério da Saúde / SINAN (agravos)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=9,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Casos de tuberculose, hepatite B e outros agravos notificados."),
    "PNI": dict(
        publicador="Ministério da Saúde / PNI (vacinação)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=9,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Cobertura vacinal por imunizante e município (CGPNI / RNDS)."),
    "CNES": dict(
        publicador="Ministério da Saúde / CNES (estabelecimentos)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=4,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Cadastro de estabelecimentos de saúde (E-Gestor)."),
    "INEP": dict(
        publicador="Ministério da Educação / INEP",
        tipo_acesso="download", periodicidade="anual", mes_esperado=8,
        url_landing="https://download.inep.gov.br/",
        observacao="Censo Escolar, Provas e indicadores educacionais."),
    "RAIS": dict(
        publicador="Ministério do Trabalho e Emprego / RAIS",
        tipo_acesso="download", periodicidade="anual", mes_esperado=5,
        url_landing="https://portaldadosabertos.mte.gov.br/",
        observacao="Vínculos de emprego por município; a RAIS agregada sai em arquivo anual."),
    "TSE": dict(
        publicador="Tribunal Superior Eleitoral",
        tipo_acesso="download", periodicidade="quadrienal", mes_esperado=5,
        url_landing="https://dados.tse.jus.br/",
        observacao="Resultados eleitorais por município (eleições de 2024 em diante)."),
    "IBGE": dict(
        publicador="IBGE",
        tipo_acesso="api", periodicidade="anual", mes_esperado=2,
        url_direta="https://servicodados.ibge.gov.br/api/v3/agregados",
        url_landing="https://servicodados.ibge.gov.br/api/docs",
        observacao="SIDRA: acesso programável, sem chave; uma tabela por indicador."),
    "IPARDES": dict(
        publicador="IPARDES / IBGE",
        tipo_acesso="api", periodicidade="anual", mes_esperado=2,
        url_direta="https://servicodados.ibge.gov.br/api/v3/agregados",
        url_landing="https://servicodados.ibge.gov.br/api/docs",
        observacao="PIB e VAB municipal: agregados do SIDRA."),
    "BACEN": dict(
        publicador="Banco Central do Brasil / IPARDES",
        tipo_acesso="api", periodicidade="anual", mes_esperado=2,
        url_direta="https://olinda.bcb.gov.br/olinda/servico",
        url_landing="https://www3.bcb.gov.br/estabilidadefinanceira/historicocotacoes",
        observacao="SGS (agências e PAE) e série municipal do IPARDES."),
    "SANEPAR": dict(
        publicador="SANEPAR (e SNIS/SINISA do Ministério das Cidades)",
        tipo_acesso="manual", periodicidade="anual", mes_esperado=2,
        url_landing="https://www.sanepar.com.br/",
        observacao="A concessionária publica as unidades atendidas; SNIS/SINISA traz o indicador "
                   "oficial (IN028 → IRS1005). Arquivo baixado à mão, com checksum registrado."),
    "ENERGIA": dict(
        publicador="COPEL, CELESC, COCOEL, CFLO, CPFL e Pacto Energia",
        tipo_acesso="manual", periodicidade="anual", mes_esperado=8,
        url_landing="https://www.copel.com/",
        observacao="Consumidores residenciais publicados por cada distribuidora; "
                   "arquivo baixado à mão, com checksum registrado."),
    "SEFA": dict(
        publicador="Secretaria de Estado da Fazenda do Paraná (SEFA)",
        tipo_acesso="manual", periodicidade="anual", mes_esperado=3,
        url_landing="https://www.fazenda.pr.gov.br/",
        observacao="Valor adicionado fiscal do turismo; publicado em planilha anual."),
    "CEPDEC": dict(
        publicador="Coordenadoria Estadual de Proteção e Defesa Civil (PR)",
        tipo_acesso="manual", periodicidade="anual", mes_esperado=4,
        url_landing="https://www.defesacivil.pr.gov.br/",
        observacao="Mortes, desaparecidos e afetados por desastres; base estadual."),
    "INPE": dict(
        publicador="INPE (Programa Queimadas) / Fundação SOS Mata Atlântica",
        tipo_acesso="download", periodicidade="anual", mes_esperado=9,
        url_landing="https://queimadas.dgi.inpe.br/",
        observacao="Focos de queimadas e remanescente florestal."),
}

# Ajuste fino por tema do arquivo (o texto de "fonte" do dicionário cita vários órgãos,
# então o tema do próprio arquivo é o sinal mais firme). Ordem: primeiro que casar vence.
REGRAS_POR_TEMA = [
    (["DESNUTR"], "SISVAN"),
    (["TUBERCULOSE", "HEPATITE"], "SINAN"),
    (["AIDS", "HIV"], "SIH"),
    (["COBERTURA VACINAL", "VACINAL", "IMUNIZ"], "PNI"),
    (["PROFISSIONAIS DE SAUDE", "ESTABELECIMENTOS DE SAUDE", "CNES"], "CNES"),
    (["DESAPARECIDOS", "DESASTRES"], "CEPDEC"),
    (["AUTORIDADE CIVIL", "REGISTRO CIVIL"], "SINASC"),
    (["PROFICIENCIA", "INFRAESTRUTURA NAS ESCOLAS", "DOCENCIAS", "MATRICULAD", "PRE-ESCOLA", "ESCOLAR"], "INEP"),
    (["CADEIRAS", "VEREADOR"], "TSE"),
    (["DESPESAS PUBLICAS", "EDUCACAO E SEGURIDADE"], "STN/SICONFI"),
    (["AGENCIAS BANCARIAS", "PAE", "ATENDIMENTO ELETRONICO"], "BACEN"),
    (["REMANESCENTE", "FLORESTAL"], "INPE"),
    (["CONSUMIDORES", "ENERGIA ELETRICA"], "ENERGIA"),
    (["ESGOTO", "ABASTECIMENTO DE AGUA"], "SANEPAR"),
    (["VALOR ADICIONADO FISCAL"], "SEFA"),
    (["MORTALIDADE", "OBITOS", "MATERNA", "NEONATAL", "MORTES", "HOMICIDIO"], "SIM"),
    (["NASCIDOS VIVOS", "BAIXO PESO", "PRENATAL", "MAES ADOLESCENTES", "ADOLESCENTES"], "SINASC"),
    (["EMPREGO", "RAIS", "RENDIMENTO NOMINAL", "GERENCIAL"], "RAIS"),
    (["PIB", "INDUSTRIA"], "IPARDES"),
]

# Ajustes por arquivo, quando o perfil do publicador não basta.
AJUSTES_POR_ARQUIVO = {
    "ODS - Objetivo 02 - Proporção de Crianças Desnutridas com até dois Anos de Idade.xlsx": dict(
        publicador="Ministério do Desenvolvimento Social / SISVAN (VIGIANTE)",
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Desnutrição infantil: o dicionário cita o SIAB, que é o nome antigo do SISVAN."),
    "ODS - Objetivo 16 - Proporção de Nascidos Vivos Registrados por uma Autoridade Civil.xlsx": dict(
        publicador="Ministério da Saúde / SINASC (registro civil)",
        tipo_acesso="download", periodicidade="anual", mes_esperado=8,
        url_landing="https://opendatas.saude.gov.br/",
        observacao="Proporção de nascimentos com registro em cartório (SINASC)."),
    "ODS - Objetivo 08 - Produto Interno Bruto (PIB).xlsx": dict(
        observacao="PIB dos municípios: agregado SIDRA 6784 (PIB, PIB per capita, população e deflator)."),
    "ODS - Objetivo 09 - Percentual do Valor Adicionado na Indústria sobre o PIB.xlsx": dict(
        observacao="VAB da indústria: agregados do SIDRA (IBGE/IPARDES)."),
}


def _sem_acento(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def perfil_para(arquivo: str, fonte: str) -> dict:
    """Escolhe o perfil de acesso: primeiro pelo tema do arquivo, depois pela fonte."""
    tema = _sem_acento(arquivo)
    for palavras, chave in REGRAS_POR_TEMA:
        if any(p in tema for p in palavras):
            return dict(PERFIS[chave])
    f = _sem_acento(fonte)
    for chave in ("STN/SICONFI", "SISVAN", "SIAB", "SINASC", "SIH", "SIM", "SINAN",
                  "PNI", "CNES", "INEP", "RAIS", "TSE", "IPARDES", "BACEN", "IBGE",
                  "SANEPAR", "ENERGIA", "SEFA", "CEPDEC", "INPE"):
        if chave.upper() in f:
            return dict(PERFIS[chave])
    if "SANEPAR" in f or "SANEAMENTO" in f:
        return dict(PERFIS["SANEPAR"])
    if "ENERGIA" in f or "COPEL" in f or "CELESC" in f:
        return dict(PERFIS["ENERGIA"])
    if "FAZENDA" in f or "SEFA" in f:
        return dict(PERFIS["SEFA"])
    if "DEFESA CIVIL" in f or "CEPDEC" in f:
        return dict(PERFIS["CEPDEC"])
    if "ELEITORAL" in f or "TSE" in f:
        return dict(PERFIS["TSE"])
    if "SICONFI" in f or "TESOURO" in f:
        return dict(PERFIS["STN/SICONFI"])
    if "TRABALHO" in f or "RAIS" in f:
        return dict(PERFIS["RAIS"])
    if "EDUCACAO" in f or "INEP" in f:
        return dict(PERFIS["INEP"])
    if "SAUDE" in f:
        return dict(PERFIS["SIM"])
    if "IBGE" in f or "IPARDES" in f:
        return dict(PERFIS["IBGE"])
    if "BACEN" in f or "BANCO CENTRAL" in f:
        return dict(PERFIS["BACEN"])
    if "INPE" in f:
        return dict(PERFIS["INPE"])
    return dict(publicador=(fonte or "desconhecida").split("\n")[0][:70],
                tipo_acesso="manual", periodicidade="anual", mes_esperado=1,
                url_landing="", observacao="Revisar: fonte sem perfil de acesso definido.")


def sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def probe(url: str) -> str:
    """Classifica a resposta da URL: ok | url_alterada | sem_rede | erro."""
    if not url:
        return "sem_url"
    req = urllib.request.Request(url, headers=UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            r.read(2048)
            return "ok" if r.status < 400 else "erro_%d" % r.status
    except urllib.error.HTTPError as e:
        return "url_alterada" if e.code in (404, 410) else "erro_%d" % e.code
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, ConnectionError, OSError) as e:
        return "sem_rede"


def ler_registro() -> list:
    if not os.path.exists(REGISTRO):
        return []
    with io.open(REGISTRO, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def gravar_registro(linhas: list) -> None:
    os.makedirs(os.path.dirname(REGISTRO), exist_ok=True)
    with io.open(REGISTRO, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS, delimiter=";", lineterminator="\n")
        w.writeheader()
        for l in linhas:
            w.writerow({c: l.get(c, "") for c in COLUNAS})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicializar", action="store_true",
                    help="cria/atualiza o registro sem sobrescrever as colunas curadas")
    ap.add_argument("--recurar", action="store_true",
                    help="reaplica os perfis (publicador, acesso, URL, periodicidade) e zera o resto")
    ap.add_argument("--estrito", action="store_true",
                    help="sai com codigo 1 se houver fonte pendente ou URL quebrada")
    ap.add_argument("--sem-rede", action="store_true",
                    help="nao testa as URLs (ambiente sem acesso a internet)")
    args = ap.parse_args()

    hoje = datetime.date.today()
    cat = json.load(open(CATALOGO, encoding="utf-8"))

    # ---------- 1. catalogo -> linhas do registro
    arquivos = OrderedDict()
    for c in cat:
        arquivos.setdefault(c["arquivo"], []).append(c)

    existentes = {l["arquivo"]: l for l in ler_registro()}
    linhas = []
    ids_usados = set()
    for i, (arq, cs) in enumerate(arquivos.items(), 1):
        fonte = str(cs[0].get("fonte") or "")
        perfil = dict(perfil_para(arq, fonte))
        ajuste = next((v for k, v in AJUSTES_POR_ARQUIVO.items()
                       if _sem_acento(k) == _sem_acento(arq)), {})
        perfil.update(ajuste)
        antigo = existentes.get(arq, {})
        if args.recurar:
            antigo = {}
        linha = {
            "id": antigo.get("id") or "f%02d" % i,
            "ods": str(cs[0]["ods"]),
            "arquivo": arq,
            "publicador": antigo.get("publicador") or perfil["publicador"],
            "fonte_dicionario": " ".join(fonte.split())[:180],
            # colunas curadas: preserva o que ja foi editado a mao
            "tipo_acesso": antigo.get("tipo_acesso") or perfil["tipo_acesso"],
            "url_direta": antigo.get("url_direta") or perfil.get("url_direta", ""),
            "url_landing": antigo.get("url_landing") or perfil.get("url_landing", ""),
            "periodicidade": antigo.get("periodicidade") or perfil["periodicidade"],
            "mes_esperado": antigo.get("mes_esperado") or str(perfil.get("mes_esperado", "")),
            # data da EDICAO da fonte (o que o dicionario declara) — e o que define o lembrete
            "edicao_fonte": antigo.get("edicao_fonte") or max(
                [str(c.get("atualizado_em"))[:10] for c in cs if c.get("atualizado_em")] or [""]),
            "ultima_aquisicao": antigo.get("ultima_aquisicao", ""),
            "sha256": antigo.get("sha256", ""),
            "status": antigo.get("status") or "ativa",
            "observacao": antigo.get("observacao") or perfil.get("observacao", ""),
        }
        linhas.append(linha)
        ids_usados.add(linha["id"])

    # fontes externas (nao sao espelhos de um arquivo da pasta Base de Dados/):
    # ficam no registro e sao preservadas entre execucoes
    for l in existentes.values():
        if l.get("arquivo") and l["arquivo"] in arquivos:
            continue
        if l.get("id") in ids_usados:
            continue
        linhas.append({c: l.get(c, "") for c in COLUNAS})

    gravar_registro(linhas)
    print("registro: %s (%d fontes)" % (os.path.relpath(REGISTRO, ROOT), len(linhas)))

    # ---------- 2. checagem
    hoje_txt = hoje.strftime("%Y-%m-%d")
    pendentes, quebradas, sem_rede, ok = [], [], [], 0
    status_por_id = {}

    for linha in linhas:
        fid = linha["id"]
        caminho = os.path.join(BASE, linha["arquivo"])
        estado = {"status": "ativa", "detalhe": ""}
        if not linha["arquivo"]:
            # fonte externa (sem espelho local): só o status de URL e o lembrete
            estado["status"] = "externa"
        elif os.path.exists(caminho):
            mtime = datetime.date.fromtimestamp(os.path.getmtime(caminho))
            sha = sha256_arquivo(caminho)
            anterior = linha["sha256"]
            linha["ultima_aquisicao"] = mtime.strftime("%Y-%m-%d")
            linha["sha256"] = sha
            if anterior and anterior[:16] != sha[:16]:
                estado["status"] = "espelho_divergente"
                estado["detalhe"] = ("o espelho local mudou desde a ultima aquisicao registrada "
                                     "(%s -> %s)" % (anterior[:12], sha[:12]))
        else:
            estado["status"] = "arquivo_ausente"
            estado["detalhe"] = "espelho local nao encontrado em Base de Dados/"
        # lembrete: a fonte oficial ja deveria ter publicado a edicao deste ciclo?
        # o sinal e a data da EDICAO da fonte (o que o dicionario declara), nao a data
        # em que o espelho local foi baixado.
        mes = linha["mes_esperado"]
        edicao = linha["edicao_fonte"]
        if mes.isdigit() and edicao:
            try:
                d_ed = datetime.date.fromisoformat(edicao)
            except ValueError:
                d_ed = None
            if d_ed:
                m = int(mes)
                ciclo = hoje.year if hoje.month >= m else hoje.year - 1
                if d_ed < datetime.date(ciclo, m, 1):
                    estado["status"] = "pendente"
                    estado["detalhe"] = ("a edicao %d ja deveria ter saido (mes %d) e a fonte esta em %s"
                                         % (ciclo, m, edicao))
                    pendentes.append(linha)

        # URL direta
        url = linha["url_direta"]
        if url and not args.sem_rede:
            res = probe(url)
            if res == "url_alterada":
                estado["status"] = "url_alterada"
                estado["detalhe"] = "a URL direta nao responde mais (404/410): ajuste url_direta no registro"
                quebradas.append(linha)
            elif res.startswith("erro"):
                estado["status"] = "erro_http"
                estado["detalhe"] = "a URL direta respondeu %s" % res
            elif res == "sem_rede":
                sem_rede.append(linha)
            else:
                ok += 1
        status_por_id[fid] = {
            "id": fid, "arquivo": linha["arquivo"], "ods": int(linha["ods"]),
            "publicador": linha["publicador"], "status": estado["status"],
            "detalhe": estado["detalhe"], "periodicidade": linha["periodicidade"],
            "mes_esperado": linha["mes_esperado"], "edicao_fonte": linha["edicao_fonte"],
            "ultima_aquisicao": linha["ultima_aquisicao"],
            "sha256": (linha["sha256"] or "")[:16], "url_landing": linha["url_landing"],
        }

    gravar_registro(linhas)

    # ---------- 3. saidas
    os.makedirs(os.path.dirname(STATUS_JSON), exist_ok=True)
    status = {
        "gerado_em": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(linhas),
        "pendentes": len(pendentes),
        "urls_quebradas": len(quebradas),
        "sem_rede": len(sem_rede),
        "fontes": status_por_id,
    }
    with io.open(STATUS_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(status, fh, ensure_ascii=False, indent=1)
    # versao JS (o painel carrega os dados por <script>, como os demais arquivos do payload)
    with io.open(STATUS_JSON.replace(".json", ".js"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Status das fontes oficiais — gerado por scripts/05_fetch_fontes.py */\n")
        fh.write("window.BI=window.BI||{};BI.fontes=")
        fh.write(json.dumps(status, ensure_ascii=False, separators=(",", ":")))
        fh.write(";\n")

    L = []
    A = L.append
    A("# Status das fontes oficiais")
    A("")
    A("> Gerado por `scripts/05_fetch_fontes.py` em %s. Não editar à mão: o registro editável é "
      "[`data/fontes.csv`](fontes.csv)." % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    A("")
    A("| Situação | Fontes |")
    A("|---|---:|")
    A(f"| Ativas | {len(linhas) - len(pendentes) - len(quebradas)} |")
    A(f"| **Pendentes (edição nova já deveria ter saído)** | **{len(pendentes)}** |")
    A(f"| **URL alterada** | **{len(quebradas)}** |")
    A(f"| Sem rede (não verificadas) | {len(sem_rede)} |")
    A("")
    if pendentes or quebradas:
        A("## O que fazer")
        A("")
        A("1. Abra a **página da fonte** (coluna `url_landing`) e localize a nova edição.")
        A("2. Atualize a coluna `url_direta` da fonte em `data/fontes.csv` e rode:")
        A("   ```bash")
        A("   python scripts/05_fetch_fontes.py")
        A("   ```")
        A("3. Baixe o novo arquivo para `Base de Dados/` (mesmo nome) e rode o pipeline:")
        A("   ```bash")
        A("   python scripts/01_build_catalog.py && python scripts/04_build_populacao.py \\")
        A("       && python scripts/03_build_bi.py && python scripts/02_gen_schema.py")
        A("   ```")
        A("4. O histórico das trocas de URL fica no git.")
        A("")
        A("| Fonte | Situação | Detalhe | Onde buscar |")
        A("|---|---|---|---|")
        for l in pendentes + quebradas:
            s = status_por_id[l["id"]]
            A("| `%s` | %s | %s | %s |" % (l["id"], s["status"], s["detalhe"] or "—",
                                           s["url_landing"] or "—"))
        A("")
    A("## Inventário")
    A("")
    A("| Fonte | Arquivo | ODS | Publicador | Acesso | Periodicidade | Espelho |")
    A("|---|---|---:|---|---|---|---|")
    for l in linhas:
        s = status_por_id[l["id"]]
        A("| `%s` | %s | %s | %s | %s | %s | %s |" % (
            l["id"], l["arquivo"].replace("ODS - Objetivo ", "O")[:46], l["ods"],
            l["publicador"][:38], l["tipo_acesso"], l["periodicidade"],
            l["ultima_aquisicao"] or "—"))
    A("")
    with io.open(RELATORIO, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")

    print("status: %d ativas | %d pendentes | %d URL alterada | %d sem rede"
          % (len(linhas) - len(pendentes) - len(quebradas), len(pendentes), len(quebradas), len(sem_rede)))
    for l in pendentes:
        print("  PENDENTE  %s  %s" % (l["id"], (l["arquivo"] or l["publicador"])[:66]))
    for l in quebradas:
        print("  URL QUEBRADA %s  %s" % (l["id"], l["url_direta"][:70]))
    print("relatorio: %s" % os.path.relpath(RELATORIO, ROOT))

    if args.estrito and (pendentes or quebradas):
        sys.exit(1)


if __name__ == "__main__":
    main()
