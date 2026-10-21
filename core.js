/* ------------------------------------------------------------------
   core.js — núcleo de cálculo do Painel ODS (sem DOM, testável em node)

   Concentra as funções puras: leitura de valores, estatística de posição,
   percentil, ranking, faixas do mapa e formatação. Recebe os dados por
   injeção, o que permite rodar a mesma lógica no navegador e nos testes
   (scripts/06_test_core.js) sem depender do DOM.

   Regras de elegibilidade e metodologia: DECISOES.md §2.
------------------------------------------------------------------- */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CORE = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---- limites da regra de elegibilidade para síntese (DECISOES.md §2.3) ----
  const REGRAS = {
    N_MIN: 30,          // municípios com dado
    EMPATE_MAX: 0.30,   // maior grupo de empate
    DISTINTOS_MIN: 5,   // valores distintos
  };

  const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

  const lowerBound = (a, v) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < v) lo = m + 1; else hi = m; } return lo; };
  const upperBound = (a, v) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= v) lo = m + 1; else hi = m; } return lo; };

  function criar(dados) {
    const { INDS, LOC, MUN, ODS, EN, POP } = dados;

    const statsCache = new Map();
    const pctCache = new Map();
    const popCache = new Map();
    const breakCache = new Map();

    /* ------------------------------------------------ leitura de valores */
    function popDe(li, ano) {
      if (!POP) return null;
      const key = li + "|" + ano;
      if (popCache.has(key)) return popCache.get(key);
      const n = POP.anos.length;
      let j = POP.anos.indexOf(ano);
      if (j < 0) {
        let melhor = 0;
        POP.anos.forEach((a, k) => { if (Math.abs(a - ano) < Math.abs(POP.anos[melhor] - ano)) melhor = k; });
        j = melhor;
      }
      const v = POP.valores[li * n + j];
      const out = v === undefined || v === null ? null : v;
      popCache.set(key, out);
      return out;
    }

    // ano efetivamente usado como denominador (pode diferir do ano do indicador)
    function popAnoUsado(ano) {
      if (!POP) return null;
      if (POP.anos.indexOf(ano) >= 0) return ano;
      let melhor = POP.anos[0];
      POP.anos.forEach((a) => { if (Math.abs(a - ano) < Math.abs(melhor - ano)) melhor = a; });
      return melhor;
    }

    function derivado(ind) {
      return Object.assign({}, ind, {
        id: ind.id + "@100k",
        unidade: "100 mil habitantes",
        tipo: "taxa",
        derivado: true,
        baseId: ind.id,
      });
    }

    // contagem por 100 mil habitantes: a elegibilidade vem do catálogo (dado curado)
    function podeProporcional(ind) {
      return !!POP && ind && ind.tipo === "contagem" && !ind.derivado && !!ind.proporcional;
    }

    function taxa100k(base, li, ano) {
      const v = raw(base, li, ano);
      const p = popDe(li, ano);
      if (v === null || !p) return null;
      return (v / p) * 100000;
    }

    function raw(ind, li, ano) {
      if (ind && ind.derivado) {
        const base = INDS.find((x) => x.id === ind.baseId);
        return base ? taxa100k(base, li, ano) : null;
      }
      const j = ind.anos.indexOf(ano);
      if (j < 0) return null;
      const arr = EN.valores[ind.id];
      if (!arr) return null;
      const v = arr[li * ind.anos.length + j];
      return v === undefined ? null : v;
    }

    function rawSerie(ind, li) {
      if (ind && ind.derivado) return ind.anos.map((a) => raw(ind, li, a));
      const arr = EN.valores[ind.id];
      if (!arr) return new Array(ind.anos.length).fill(null);
      const n = ind.anos.length;
      return ind.anos.map((_, j) => {
        const v = arr[li * n + j];
        return v === undefined ? null : v;
      });
    }

    /* ---------------------------------------------------------- estatística */
    function stats(ind, ano) {
      const key = ind.id + "|" + ano;
      if (statsCache.has(key)) return statsCache.get(key);
      const j = ind.anos.indexOf(ano);
      let out = null;
      if (j >= 0) {
        const arr = EN.valores[ind.id];
        const vals = [];
        if (ind.derivado) {
          for (const li of MUN) { const v = raw(ind, li, ano); if (v !== undefined && v !== null) vals.push(v); }
        } else if (arr) {
          const n = ind.anos.length;
          for (const li of MUN) { const v = arr[li * n + j]; if (v !== undefined && v !== null) vals.push(v); }
        }
        if (vals.length) {
          vals.sort((a, b) => a - b);
          const n = vals.length, m = n >> 1;
          let distintos = 1, maiorEmpate = 1, seguidas = 1;
          for (let k = 1; k < n; k++) {
            if (vals[k] === vals[k - 1]) { seguidas++; if (seguidas > maiorEmpate) maiorEmpate = seguidas; }
            else { distintos++; seguidas = 1; }
          }
          out = {
            vals, n, distintos, maiorEmpate, empateFrac: maiorEmpate / n,
            med: n % 2 ? vals[m] : (vals[m - 1] + vals[m]) / 2,
          };
        }
      }
      statsCache.set(key, out);
      return out;
    }

    // faixa de posições ocupada pelo valor (competição) — 1-based, [primeira, ultima]
    function faixa(ind, st, v) {
      const { vals, n } = st;
      if (ind.pol < 0) {
        const antes = lowerBound(vals, v);          // menores que v
        const ate = upperBound(vals, v);            // menores ou iguais a v
        return { primeira: antes + 1, ultima: ate, total: n };
      }
      const depois = n - upperBound(vals, v);        // maiores que v
      const ate = n - lowerBound(vals, v);          // maiores ou iguais a v
      return { primeira: depois + 1, ultima: ate, total: n };
    }

    // percentil mid-rank: o grupo de empate recebe a posição que realmente ocupa
    function pctMap(ind, ano) {
      const key = ind.id + "|" + ano;
      if (pctCache.has(key)) return pctCache.get(key);
      const st = stats(ind, ano);
      const out = new Array(LOC.length).fill(null);
      if (st) {
        for (const li of MUN) {
          const v = raw(ind, li, ano);
          if (v === null) continue;
          const f = faixa(ind, st, v);
          const mid = (f.primeira + f.ultima) / 2;
          out[li] = Math.round((100 * (f.total - (mid - 1))) / f.total);
        }
      }
      pctCache.set(key, out);
      return out;
    }

    function rankOf(ind, li, ano) {
      if (!LOC[li] || LOC[li].t !== "municipio") return null;
      const st = stats(ind, ano);
      const v = raw(ind, li, ano);
      if (!st || v === null) return null;
      const f = faixa(ind, st, v);
      const iguais = f.ultima - f.primeira + 1;
      return { pos: f.primeira, total: st.n, igual: iguais, empateFrac: iguais / st.n };
    }

    /* ------------------------------------------------------ faixas do mapa */
    const CORES_MAPA = ["#B42318", "#E8893B", "#F2C94C", "#7FBF6A", "#0E8A5F"];
    const COR_SEM_DADO = "#E9EEF4";

    function quebras(ind, ano) {
      const key = ind.id + "|" + ano;
      if (breakCache.has(key)) return breakCache.get(key);
      const st = stats(ind, ano);
      let b = null;
      if (st && st.n >= 5) {
        const q = (p) => st.vals[Math.min(st.n - 1, Math.floor(p * st.n))];
        b = [q(0.2), q(0.4), q(0.6), q(0.8)];
      }
      breakCache.set(key, b);
      return b;
    }

    function corValor(ind, ano, v) {
      if (v === null || v === undefined) return COR_SEM_DADO;
      const b = quebras(ind, ano);
      if (!b) return COR_SEM_DADO;
      let c = 0;
      while (c < 4 && v > b[c]) c++;
      if (ind.pol < 0) c = 4 - c; // menor é melhor -> inverte a escala
      return CORES_MAPA[c];
    }

    /* -------------------------------------------------------- elegibilidade */
    // medida comparável (entra no mapa); o juízo é opcional
    function elegivelMapa(ind) {
      return (ind.recorte === null || ind.recorte === "Total") &&
        (ind.tipo === "percentual" || ind.tipo === "taxa");
    }

    // com juízo de valor (entra em ranking e sínteses)
    function elegivelRanking(ind) {
      return elegivelMapa(ind) && ind.pol !== 0;
    }

    // regra de qualidade para sínteses (DECISOES.md §2.3)
    function elegivelSintese(ind, st) {
      if (!elegivelRanking(ind)) return { ok: false, motivo: "sem juízo de valor" };
      if (!st) return { ok: false, motivo: "sem dado" };
      if (st.n < REGRAS.N_MIN) return { ok: false, motivo: "apenas " + st.n + " municípios com dado" };
      if (st.empateFrac > REGRAS.EMPATE_MAX) {
        return { ok: false, motivo: st.maiorEmpate + " municípios com o mesmo valor" };
      }
      if (st.distintos < REGRAS.DISTINTOS_MIN) {
        return { ok: false, motivo: "só " + st.distintos + " valores distintos" };
      }
      return { ok: true, motivo: "" };
    }

    /* ---------------------------------------------------------- formatação */
    function unitShort(ind) {
      if (ind.tipo === "contagem") return ind.unidade || "";
      const u = ind.unidade;
      if (u === "%") return "%";
      if (u === "100 mil habitantes") return "/100 mil hab.";
      if (u === "mil habitantes") return "/mil hab.";
      if (u === "mil nascidos vivos") return "/mil nasc. vivos";
      if (u === "100 mil nascidos vivos") return "/100 mil nasc. vivos";
      if (u === "mil meninas do grupo etário") return "/mil meninas 15–19";
      if (u === "100 mil adultos") return "/100 mil adultos";
      if (u === "R$ 1,00") return "R$";
      if (u === "R$ 1.000,00") return "R$ mil";
      if (u === "RAIS") return "vínculos";
      return "";
    }

    function fmt(v, ind) {
      if (v === null || v === undefined) return { t: "—", u: "" };
      if (ind.tipo === "moeda") {
        // mantém a unidade oficial do arquivo: "R$ 1.000,00" é exibido como R$ mil
        const t = Math.abs(v) >= 1000 ? nf0.format(v) : nf1.format(v);
        return { t, u: ind.unidade === "R$ 1.000,00" ? "R$ mil" : "R$" };
      }
      if (ind.tipo === "contagem") return { t: nf0.format(Math.round(v)), u: "" };
      return { t: nf1.format(v), u: "" };
    }

    function fmtShort(v) {
      if (v === null || v === undefined) return "—";
      if (Math.abs(v) >= 1e6) return nf2.format(v / 1e6) + "M";
      if (Math.abs(v) >= 1e3) return nf0.format(v);
      return nf1.format(v);
    }

    function fmtValor(v, ind) {
      const f = fmt(v, ind);
      return f.u ? `${f.t} ${f.u}` : f.t;
    }

    function limparCache() {
      statsCache.clear();
      pctCache.clear();
      breakCache.clear();
    }

    return {
      REGRAS, CORES_MAPA, COR_SEM_DADO,
      popDe, popAnoUsado, derivado, podeProporcional, taxa100k,
      raw, rawSerie, stats, faixa, pctMap, rankOf,
      quebras, corValor,
      elegivelMapa, elegivelRanking, elegivelSintese,
      unitShort, fmt, fmtShort, fmtValor,
      limparCache,
    };
  }

  return { criar, REGRAS };
});
