/* ------------------------------------------------------------------
   Testes do núcleo de cálculo (core.js) — rodar com:  node scripts/06_test_core.js

   Carrega o payload real (data/bi/*.js) e confere a matemática contra casos
   conhecidos: percentil mid-rank com empates, posição competitiva, regra de
   elegibilidade para síntese, zero × ausente, faixas do mapa e chaves.
------------------------------------------------------------------- */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.dirname(__dirname);
const BI_DIR = path.join(ROOT, "data", "bi");

/* ---------------------------------------------------------- carregar payload */
const sandbox = { console, Intl, Math, Date, JSON, Object, Array, Map, Set, Number, String, isNaN, parseFloat, parseInt };
sandbox.window = sandbox;   // no navegador, window é o próprio global
sandbox.self = sandbox;
vm.createContext(sandbox);

const arquivos = ["indice.js", "mapa.js", "populacao.js", "sinisa.js"].concat(
  fs.readdirSync(BI_DIR).filter((f) => /^val_ods\d+\.js$/.test(f)).sort()
);
arquivos.forEach((f) => {
  const codigo = fs.readFileSync(path.join(BI_DIR, f), "utf8");
  vm.runInContext(codigo, sandbox, { filename: f });
});
const coreCodigo = fs.readFileSync(path.join(ROOT, "core.js"), "utf8");
vm.runInContext(coreCodigo, sandbox, { filename: "core.js" });

const BI = sandbox.window.BI;
const CORE = sandbox.window.CORE;
const INDS = BI.indice.indicadores;
const LOC = BI.indice.localidades;
const ODS = BI.indice.ods;
const MUN = LOC.map((l, i) => (l.t === "municipio" ? i : -1)).filter((i) => i >= 0);
const C = CORE.criar({ INDS, LOC, MUN, ODS, EN: BI, POP: BI.pop || null });

/* ------------------------------------------------------------- mini asserção */
let passou = 0, falhou = 0;
const falhas = [];
function ok(nome, cond, detalhe) {
  if (cond) { passou++; }
  else { falhou++; falhas.push(nome + (detalhe ? " — " + detalhe : "")); }
}
function eq(nome, a, b) { ok(nome, a === b, "obtido " + JSON.stringify(a) + ", esperado " + JSON.stringify(b)); }
function near(nome, a, b, tol) { ok(nome, Math.abs(a - b) <= (tol || 0.51), "obtido " + a + ", esperado " + b); }

/* ------------------------------------------------------------- 1. integridade */
ok("manifesto do payload presente", !!(BI.build && BI.build.id));
ok("todos os arquivos do mesmo build",
  new Set(Object.values(BI.builds).map((b) => b.id)).size === 1);
const n_espelhos = INDS.filter((i) => i.espelho_de).length;
ok("194 indicadores do catalogo + externos + espelhos",
  INDS.length === 194 + (BI.sinisa ? BI.sinisa.ind.length : 0) + n_espelhos, String(INDS.length));
ok("espelhos apontam para indicador existente",
  INDS.filter((i) => i.espelho_de).every((i) => INDS.some((x) => x.id === i.espelho_de)));
ok("406 localidades", LOC.length === 406, String(LOC.length));
ok("399 municipios", MUN.length === 399, String(MUN.length));
ok("13 ODS (12 do painel + ODS 11)", ODS.length === 13, String(ODS.length));ok("chaves de negocio unicas", new Set(INDS.map((i) => i.chave)).size === INDS.length);
ok("ids curtos unicos", new Set(INDS.map((i) => i.id)).size === INDS.length);
ok("cada indicador tem 399 municipios na origem", INDS.every((i) => i.n_municipios === 399));
ok("principais definidos para os 12 ODS", ODS.every((o) => !!o.principal));
ok("37 contagens proporcionais", INDS.filter((i) => i.proporcional).length === 37);
ok("nenhum indicador sem polaridade justificada", INDS.every((i) => !!i.pol_motivo));

/* --------------------------------------------- 2. estatística com casos fixos */
const fake = (vals, pol) => {
  const anos = [2020];
  const arr = new Array(LOC.length).fill(null);   // layout: localidade × anos
  MUN.forEach((li, k) => { arr[li] = vals[k]; });
  const ind = {
    id: "fake" + Math.random().toString(36).slice(2), ods: 3, grupo: "G", gcurto: "G",
    medida: "M", recorte: "Total", unidade: "%", tipo: "percentual", pol, anos,
    chave: "fake", principal: false,
  };
  const EN = { valores: { [ind.id]: arr } };
  const cc = CORE.criar({ INDS: [ind].concat(INDS), LOC, MUN, ODS, EN, POP: null });
  return { ind, core: cc, ano: 2020 };
};

// caso A: 399 municípios com valores 0..398 (todos distintos), exceto um empate
//   no meio da série: os dois empatados compartilham a posição
{
  const n = MUN.length;
  const vals = MUN.map((_, k) => k);
  vals[10] = 10; vals[11] = 10;              // empate entre 10 e 11
  const { ind, core } = fake(vals, 1);
  const rkPior = core.rankOf(ind, MUN[0], 2020);        // valor 0 -> último
  eq("ranking: pior valor fica em último", rkPior.pos, n);
  const rkTie = core.rankOf(ind, MUN[10], 2020);        // valor 10 (empate)
  eq("ranking: empate compartilha a posição", rkTie.pos, n - 11);
  eq("ranking: tamanho do grupo de empate", rkTie.igual, 2);
  const rkMelhor = core.rankOf(ind, MUN[n - 1], 2020);  // valor máximo
  eq("ranking: melhor valor em 1º", rkMelhor.pos, 1);
  // mid-rank: o grupo ocupa as posições (n-11) e (n-10) -> meio = n-10,5
  const p = core.pctMap(ind, 2020)[MUN[10]];
  near("percentil mid-rank do grupo empatado", p, (100 * (n - (n - 10.5))) / n, 1);
  ok("percentil não é 0 nem 100 no meio da série", p > 0 && p < 100, "percentil " + p);
}

// caso B: empate no topo (todos com o mesmo valor máximo) -> todos com 1º
{
  const n = MUN.length;
  const vals = MUN.map(() => 10);
  const { ind, core } = fake(vals, 1);
  const rk = core.rankOf(ind, MUN[0], 2020);
  eq("empate no topo: todos em 1º", rk.pos, 1);
  eq("empate no topo: grupo inteiro", rk.igual, n);
  const p = core.pctMap(ind, 2020)[MUN[0]];
  near("percentil mid-rank de empate total", p, (100 * (n - (n / 2))) / n, 1);
}

/* -------------------------------- 3. percentil não é 100 para massa de zeros */
{
  const n = MUN.length;
  const vals = new Array(n).fill(0);
  for (let k = 0; k < 354; k++) vals[k] = 0;              // 354 com 0
  for (let k = 354; k < n; k++) vals[k] = 1;              // resto com 1
  const { ind, core } = fake(vals, -1);                    // menor é melhor
  const p = core.pctMap(ind, 2020)[MUN[0]];
  ok("percentil de massa de zeros não é 100", p < 60, "percentil " + p);
  const st = core.stats(ind, 2020);
  near("empate máximo detectado", st.maiorEmpate, 354, 0);
  ok("empateFrac > 0,3", st.empateFrac > 0.3);
}

/* --------------------------------------------------- 4. regra de elegibilidade */
{
  const n = MUN.length;
  const vals = new Array(n).fill(0);
  for (let k = 0; k < 354; k++) vals[k] = 0;
  for (let k = 354; k < n; k++) vals[k] = 1;
  const { ind, core } = fake(vals, -1);
  const st = core.stats(ind, 2020);
  const r = core.elegivelSintese(ind, st);
  ok("indicador com massa de empate fora da síntese", !r.ok);
  ok("motivo cita os municipios empatados", /munic[ií]pios/.test(r.motivo), r.motivo);

  // n pequeno
  const vals2 = new Array(n).fill(null).map((_, k) => (k < 10 ? k : null));
  const f2 = fake(vals2, 1);
  const r2 = f2.core.elegivelSintese(f2.ind, f2.core.stats(f2.ind, 2020));
  ok("indicador com poucos municipios fora da síntese", !r2.ok);
  ok("motivo cita o n", /munic[ií]pios com dado/.test(r2.motivo), r2.motivo);

  // indicador bom: todos com valores distintos
  const vals3 = MUN.map((_, k) => k);
  const f3 = fake(vals3, 1);
  const r3 = f3.core.elegivelSintese(f3.ind, f3.core.stats(f3.ind, 2020));
  ok("indicador que discrimina entra na síntese", r3.ok, r3.motivo);
}

/* ---------------------------------------- 5. zero é valor, ausente é ausente */
{
  const n = MUN.length;
  const vals = MUN.map((_, k) => (k < 50 ? 0 : (k < 100 ? 5 : null)));
  const { ind, core } = fake(vals, 1);
  eq("zero é lido como zero", core.raw(ind, MUN[0], 2020), 0);
  eq("ausente é null", core.raw(ind, MUN[n - 1], 2020), null);
  const st = core.stats(ind, 2020);
  eq("contagem de municipios com dado", st.n, 100);
}

/* -------------------------------------------------------- 6. faixas do mapa */
{
  const n = MUN.length;
  const vals = MUN.map((_, k) => k);
  const { ind, core } = fake(vals, 1);
  const b = core.quebras(ind, 2020);
  ok("cinco faixas (4 cortes)", b && b.length === 4);
  const cores = new Set();
  for (let k = 0; k < n; k++) cores.add(core.corValor(ind, 2020, k));
  eq("cores usadas = 5", cores.size, 5);
  // polaridade invertida troca as extremidades
  const f2 = fake(vals, -1);
  ok("pol<0 inverte a escala", core.corValor(ind, 2020, 0) !== f2.core.corValor(f2.ind, 2020, 0));
}

/* ------------------------------------------- 7. elegibilidade: mapa x ranking */
{
  const semJuizo = INDS.filter((i) => i.pol === 0);
  ok("existem indicadores sem juízo de valor", semJuizo.length > 0);
  ok("sem juízo NÃO entra no ranking", semJuizo.every((i) => !C.elegivelRanking(i)));
  const semJuizoTotal = semJuizo.filter((i) => i.recorte === null || i.recorte === "Total");
  const semJuizoMedida = semJuizo.filter((i) => (i.recorte === null || i.recorte === "Total") &&
    (i.tipo === "percentual" || i.tipo === "taxa"));
  ok("sem juízo (Total, medida comparável) ENTRA no mapa",
    semJuizoMedida.length > 0 && semJuizoMedida.every((i) => C.elegivelMapa(i)));
  ok("sem juízo com recorte (fora do Total) fica fora do mapa",
    semJuizo.filter((i) => i.recorte !== null && i.recorte !== "Total").every((i) => !C.elegivelMapa(i)));
  ok("sem juízo (volume ou estrutural) não entra no ranking", semJuizo.every((i) => !C.elegivelRanking(i)));
  const contagens = INDS.filter((i) => i.tipo === "contagem");
  ok("contagens não entram no mapa", contagens.every((i) => !C.elegivelMapa(i)));
  ok("contagens não entram no ranking", contagens.every((i) => !C.elegivelRanking(i)));
  ok("só recorte Total entra no mapa", INDS.filter((i) => C.elegivelMapa(i)).every((i) => i.recorte === null || i.recorte === "Total"));
}

/* ------------------------------------------------------- 8. população e taxas */
{
  ok("população carregada", !!(BI.pop && BI.pop.valores.length));
  ok("população: 26 anos", BI.pop.anos.length === 26);
  const j2022 = BI.pop.anos.indexOf(2022);
  const soma = MUN.reduce((s, li) => s + BI.pop.valores[li * BI.pop.anos.length + j2022], 0);
  eq("soma dos municipios em 2022 = Censo PR", soma, 11444380);
  const pop = C.popDe(MUN[0], 2022);
  ok("população de um municipio em 2022", pop > 0);
  const anoUsado = C.popAnoUsado(2023);
  eq("ano do denominador para 2023 (interpolado)", anoUsado, 2023);
  ok("anos interpolados declarados", BI.pop.info.anos_interpolados.length === 2);
  // taxa derivada
  const cont = INDS.find((i) => i.tipo === "contagem" && i.proporcional);
  ok("existe contagem proporcional", !!cont);
  const d = C.derivado(cont);
  const v = C.raw(d, MUN[0], cont.anos[cont.anos.length - 1]);
  const esperado = C.raw(cont, MUN[0], cont.anos[cont.anos.length - 1]) / C.popDe(MUN[0], cont.anos[cont.anos.length - 1]) * 100000;
  near("taxa derivada = total / população × 100.000", v, esperado, 0.01);
}

/* ------------------------------------------------------ 9. formatação e moeda */
{
  const moeda = INDS.find((i) => i.tipo === "moeda" && i.unidade === "R$ 1.000,00");
  const f = C.fmt(13500, moeda);
  eq("moeda mantém a unidade oficial", f.u, "R$ mil");
  ok("moeda não é convertida para reais", !/R\\$ mil/.test(f.t) && f.t.indexOf("R$") === -1);
  const cont = INDS.find((i) => i.tipo === "contagem");
  eq("contagem sem decimal", C.fmt(12.7, cont).t, "13");
  eq("ausente vira travessão", C.fmt(null, cont).t, "—");
}

/* ----------------------------------------------------------------- resultado */
console.log("\n" + "=".repeat(64));
console.log("TESTES DO NÚCLEO — " + passou + " passaram, " + falhou + " falharam");
if (falhou) {
  console.log("=".repeat(64));
  falhas.forEach((f) => console.log("  ✗ " + f));
  process.exit(1);
}
console.log("payload:", BI.build.id, "| indicadores:", INDS.length, "| localidades:", LOC.length);
console.log("=".repeat(64) + "\n");
