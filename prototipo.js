/* ------------------------------------------------------------------
   Painel ODS · protótipo
   Depende de: data/bi/indice.js, data/bi/val_odsN.js, data/bi/mapa.js
------------------------------------------------------------------- */
(function () {
  "use strict";

  const EN = window.BI || {};
  if (!EN.indice) {
    document.body.innerHTML = '<p style="padding:40px">Dados não carregados. Rode scripts/03_build_bi.py.</p>';
    return;
  }

  const LOC = EN.indice.localidades;
  const INDS = EN.indice.indicadores;
  const ODS = EN.indice.ods;
  const MAPA = EN.mapa;
  const POP = EN.pop || null;

  const MUN = LOC.map((l, i) => i).filter((i) => LOC[i].t === "municipio");
  const COD2LI = {};
  LOC.forEach((l, i) => { if (l.cod) COD2LI[String(l.cod)] = i; });

  const NS = "http://www.w3.org/2000/svg";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };

  /* ---------------------------------------------------------- estado */
  const state = {
    view: "geral",
    local: LOC.findIndex((l) => l.n === "Guarapuava"),
    ano: Math.max(...INDS.flatMap((i) => i.anos)),
    indId: null,
    odsFiltro: null,
    busca: "",
    cmp: [LOC.findIndex((l) => l.n === "Guarapuava"), 0],
    cmpInd: null,
    cmpAno: null,
    cmpOds: null,
    mapaOds: 3,
    mapaInd: null,
    modo: "absoluto",
  };

  /* ---------------------------------------------------------- dados */
  const statsCache = new Map();
  const pctCache = new Map();
  const popCache = new Map();

  // populacao residente da localidade no ano (ou no ano mais proximo da serie)
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

  // indicador de contagem visto como taxa por 100 mil habitantes (valor calculado)
  function derivado(ind) {
    return Object.assign({}, ind, {
      id: ind.id + "@100k",
      unidade: "100 mil habitantes",
      tipo: "taxa",
      derivado: true,
      baseId: ind.id,
    });
  }

  // contagem por 100 mil habitantes só faz sentido quando o numerador conta pessoas/eventos
  // (óbitos, casos, matrículas, vínculos). Unidades atendidas, consumidores, agências etc. são
  // de outra natureza: ficam no absoluto.
  const UNIDADE_NAO_PESSOAL = /unidade|consumidor|residênc|habitaç|domicíl|agência|posto|estabelecimento|escola|leito|veículo|propriedade|máquina|trator|aparelho|equipa/i;

  function podeProporcional(ind) {
    return !!POP && ind && ind.tipo === "contagem" && !ind.derivado &&
      !UNIDADE_NAO_PESSOAL.test(ind.unidade || "") && !UNIDADE_NAO_PESSOAL.test(ind.medida || "");
  }

  // o que está na tela: total absoluto ou taxa calculada por 100 mil habitantes
  function indExib(ind) {
    return state.modo === "proporcional" && podeProporcional(ind) ? derivado(ind) : ind;
  }

  function modoCtrls(ind) {
    if (!podeProporcional(ind) && !ind.derivado) return "";
    return `<div class="modo" role="group" aria-label="Forma de exibição">
      <button data-modo="absoluto" class="${state.modo === "absoluto" ? "on" : ""}">Total</button>
      <button data-modo="proporcional" class="${state.modo === "proporcional" ? "on" : ""}">por 100 mil hab.*</button>
    </div>`;
  }

  function ligarModo(host, rerender) {
    $$(".modo button", host).forEach((b) => b.addEventListener("click", () => {
      state.modo = b.dataset.modo;
      rerender();
    }));
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

  const lowerBound = (a, v) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < v) lo = m + 1; else hi = m; } return lo; };
  const upperBound = (a, v) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= v) lo = m + 1; else hi = m; } return lo; };

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

  function pctMap(ind, ano) {
    const key = ind.id + "|" + ano;
    if (pctCache.has(key)) return pctCache.get(key);
    const st = stats(ind, ano);
    const out = new Array(LOC.length).fill(null);
    if (st) {
      const { vals, n } = st;
      for (const li of MUN) {
        const v = raw(ind, li, ano);
        if (v === null) continue;
        // posição competitiva: empates compartilham a mesma posição
        const melhor = ind.pol < 0 ? lowerBound(vals, v) : n - upperBound(vals, v);
        out[li] = Math.round((100 * (n - melhor)) / n);
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
    const better = ind.pol < 0 ? lowerBound(st.vals, v) : st.n - upperBound(st.vals, v);
    const igual = upperBound(st.vals, v) - lowerBound(st.vals, v);
    return { pos: better + 1, total: st.n, igual, empateFrac: igual / st.n };
  }

  function tag(ind) {
    return ind.recorte ? ind.recorte : null;
  }

  // rótulo curto do item: parte específica da medida, sem repetir o tema do grupo
  function rotuloItem(i) {
    if (i.recorte && i.recorte !== "Total") return i.recorte;
    let t = i.medida;
    for (const base of [i.gcurto, i.grupo]) {
      if (base && t.toLowerCase().startsWith(base.toLowerCase())) {
        const resto = t.slice(base.length).replace(/^[\s\-–—:]+/, "").trim();
        if (resto) { t = resto; break; }
      }
    }
    const limpo = t
      .replace(/^(Taxa de Mortalidade|Taxa de|Proporção de|Número de|Percentual do|Percentual de)\s+/i, "")
      .replace(/^Causas (Selecionadas|Externas)\s*[-–—]\s*/i, "")
      .replace(/^(Atribuída a|Atribuída|Atribuídos a|por)\s+/i, "")
      .replace(/^(Estudantes|Pessoas|Crianças)\s+/i, "")
      .replace(/\s*que Atingiram um Nível Mínimo de Proficiência\s*/i, " ")
      .replace(/^em\s+/i, "")
      .replace(/\s+/g, " ")
      .trim();
    return (i.recorte === null || i.recorte === "Total") && mesmoTema(limpo, i.grupo) ? "Total" : limpo;
  }

  const semAcento = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  function mesmoTema(titulo, grupo) {
    const palavras = (s) => new Set(semAcento(s).replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter((w) => w.length > 2));
    const a = palavras(titulo), b = palavras(grupo);
    if (!a.size || !b.size || a.size > b.size) return false;
    for (const w of a) if (!b.has(w)) return false;
    // só considera "mesmo tema" quando o título cobre boa parte do grupo
    return a.size / b.size >= 0.6;
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

  const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

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

  function fmtAno(a) { return String(a); }

  /* ---------------------------------------------------------- sparkline */
  function sparkline(vals, color, w, h) {
    w = w || 84; h = h || 26;
    const clean = vals.filter((v) => v !== null && v !== undefined);
    if (clean.length < 2) return `<svg width="${w}" height="${h}"></svg>`;
    const lo = Math.min(...clean), hi = Math.max(...clean);
    const pad = (hi - lo) * 0.15 || 1;
    const X = (i) => 1 + (i / (vals.length - 1)) * (w - 2);
    const Y = (v) => h - 2 - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (h - 4);
    let d = "", open = false;
    vals.forEach((v, i) => {
      if (v === null || v === undefined) { open = false; return; }
      d += (open ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1);
      open = true;
    });
    const lastI = vals.map((v, i) => (v !== null ? i : -1)).filter((i) => i >= 0).pop();
    const lastV = vals[lastI];
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
      <path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${X(lastI).toFixed(1)}" cy="${Y(lastV).toFixed(1)}" r="2.1" fill="${color}"/>
    </svg>`;
  }

  /* ---------------------------------------------------------- eixos */
  function niceTicks(lo, hi, n) {
    const span = hi - lo;
    if (span <= 0) return [lo];
    const step0 = Math.pow(10, Math.floor(Math.log10(span / n)));
    const err = span / n / step0;
    const mult = err >= 7.5 ? 10 : err >= 3 ? 5 : err >= 1.5 ? 2 : 1;
    const step = step0 * mult;
    const start = Math.ceil(lo / step) * step;
    const out = [];
    for (let v = start; v <= hi + 1e-9; v += step) out.push(+v.toPrecision(12));
    return out;
  }

  /* ---------------------------------------------------------- gráfico de linha */
  function lineChart(host, cfg) {
    host.innerHTML = "";
    const wrap = el("div", "chart-wrap");
    host.appendChild(wrap);
    const anos = cfg.anos;
    const series = cfg.series.filter((s) => s.values.some((v) => v !== null));
    if (!series.length) { host.innerHTML = '<div class="empty">Sem dados para este recorte.</div>'; return; }

    const w = Math.max(wrap.clientWidth || host.clientWidth || 640, 300);
    const H = cfg.height || 230;
    const m = { t: 12, r: 16, b: 26, l: 52 };
    const W = w - m.l - m.r, HH = H - m.t - m.b;

    let all = [];
    series.forEach((s) => s.values.forEach((v) => { if (v !== null) all.push(v); }));
    let lo = Math.min(...all), hi = Math.max(...all);
    const ticks = niceTicks(lo, hi, 4);
    if (ticks.length) { lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]); }
    if (lo === hi) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;

    const x0 = anos[0], x1 = anos[anos.length - 1];
    const X = (a) => m.l + (x1 === x0 ? W / 2 : ((a - x0) / (x1 - x0)) * W);
    const Y = (v) => m.t + HH - ((v - lo) / (hi - lo)) * HH;

    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${H}`);
    svg.setAttribute("height", H);

    // grid + eixo y
    ticks.forEach((t) => {
      const y = Y(t);
      const l = document.createElementNS(NS, "line");
      l.setAttribute("x1", m.l); l.setAttribute("x2", w - m.r);
      l.setAttribute("y1", y); l.setAttribute("y2", y);
      l.setAttribute("stroke", "#EDF1F5");
      svg.appendChild(l);
      const tx = document.createElementNS(NS, "text");
      tx.setAttribute("x", m.l - 8); tx.setAttribute("y", y + 3.5);
      tx.setAttribute("text-anchor", "end");
      tx.setAttribute("font-size", "10");
      tx.setAttribute("fill", "#94A3B8");
      tx.textContent = fmtShort(t);
      svg.appendChild(tx);
    });

    // eixo x
    const passoX = Math.max(1, Math.ceil(anos.length / Math.max(4, Math.floor(W / 58))));
    anos.forEach((a, i) => {
      if (i % passoX !== 0 && i !== anos.length - 1) return;
      const tx = document.createElementNS(NS, "text");
      tx.setAttribute("x", X(a)); tx.setAttribute("y", H - 6);
      tx.setAttribute("text-anchor", "middle");
      tx.setAttribute("font-size", "10");
      tx.setAttribute("fill", "#94A3B8");
      tx.textContent = a;
      svg.appendChild(tx);
    });

    // séries
    series.forEach((s) => {
      let d = "", open = false;
      s.values.forEach((v, i) => {
        if (v === null || v === undefined) { open = false; return; }
        d += (open ? "L" : "M") + X(anos[i]).toFixed(1) + "," + Y(v).toFixed(1);
        open = true;
      });
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", d);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", s.color);
      p.setAttribute("stroke-width", s.width || 2);
      p.setAttribute("stroke-linejoin", "round");
      p.setAttribute("stroke-linecap", "round");
      if (s.dash) p.setAttribute("stroke-dasharray", s.dash);
      p.setAttribute("opacity", s.opacity || 1);
      svg.appendChild(p);
    });

    // hover
    const cross = document.createElementNS(NS, "line");
    cross.setAttribute("y1", m.t); cross.setAttribute("y2", m.t + HH);
    cross.setAttribute("stroke", "#CBD5E1"); cross.setAttribute("stroke-width", "1");
    cross.setAttribute("opacity", "0");
    svg.appendChild(cross);

    const dots = series.map((s) => {
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("r", "3.2"); c.setAttribute("fill", "#fff");
      c.setAttribute("stroke", s.color); c.setAttribute("stroke-width", "2");
      c.setAttribute("opacity", "0");
      svg.appendChild(c); return c;
    });

    const overlay = document.createElementNS(NS, "rect");
    overlay.setAttribute("x", m.l); overlay.setAttribute("y", m.t);
    overlay.setAttribute("width", W); overlay.setAttribute("height", HH);
    overlay.setAttribute("fill", "transparent");
    svg.appendChild(overlay);

    const tip = el("div", "tooltip");
    wrap.appendChild(svg);
    wrap.appendChild(tip);

    function move(ev) {
      const r = svg.getBoundingClientRect();
      const scale = w / r.width;
      const px = (ev.clientX - r.left) * scale;
      const anoAlvo = x0 + ((px - m.l) / W) * (x1 - x0);
      let best = null, bd = Infinity;
      anos.forEach((a) => { const d = Math.abs(a - anoAlvo); if (d < bd) { bd = d; best = a; } });
      if (best === null) return;
      const gx = X(best);
      cross.setAttribute("x1", gx); cross.setAttribute("x2", gx); cross.setAttribute("opacity", "1");
      const rows = [];
      series.forEach((s, si) => {
        const v = s.values[anos.indexOf(best)];
        if (v === null || v === undefined) { dots[si].setAttribute("opacity", "0"); return; }
        dots[si].setAttribute("cx", gx); dots[si].setAttribute("cy", Y(v)); dots[si].setAttribute("opacity", "1");
        rows.push(`<div style="display:flex;gap:8px;align-items:center"><i style="width:7px;height:7px;border-radius:50%;background:${s.color};display:inline-block"></i><span style="flex:1">${s.name}</span><b>${fmtValor(v, cfg.ind)}</b></div>`);
      });
      tip.innerHTML = `<div style="opacity:.6;margin-bottom:3px">${best}</div>` + rows.join("");
      tip.classList.add("on");
      const tw = tip.offsetWidth;
      const left = Math.min(Math.max((gx / w) * r.width - tw / 2, 0), r.width - tw);
      tip.style.left = left + "px";
      tip.style.top = "6px";
    }
    function leave() {
      cross.setAttribute("opacity", "0");
      dots.forEach((d) => d.setAttribute("opacity", "0"));
      tip.classList.remove("on");
    }
    overlay.addEventListener("mousemove", move);
    overlay.addEventListener("mouseleave", leave);
  }

  /* ---------------------------------------------------------- mapa */
  const CORES_MAPA = ["#B42318", "#E8893B", "#F2C94C", "#7FBF6A", "#0E8A5F"];
  const breakCache = new Map();

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
    if (v === null || v === undefined) return "#E9EEF4";
    const b = quebras(ind, ano);
    if (!b) return "#E9EEF4";
    let c = 0;
    while (c < 4 && v > b[c]) c++;
    if (ind.pol < 0) c = 4 - c; // menor é melhor → inverte a escala
    return CORES_MAPA[c];
  }

  let mapaSVG = null;
  function montarMapa(host) {
    if (!MAPA) { host.innerHTML = '<div class="empty">Malha indisponível.</div>'; return null; }
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${MAPA.w} ${MAPA.h}`);
    const g = document.createElementNS(NS, "g");
    MAPA.p.forEach((p) => {
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", p.d);
      path.setAttribute("fill", "#E9EEF4");
      path.dataset.cod = p.c;
      g.appendChild(path);
    });
    svg.appendChild(g);
    host.innerHTML = "";
    host.appendChild(svg);
    return svg;
  }

  function pintarMapa(host, ind, ano, focoLi) {
    if (!mapaSVG || mapaSVG.parentNode !== host) mapaSVG = montarMapa(host);
    if (!mapaSVG) return;
    const paths = mapaSVG.querySelectorAll("path");
    paths.forEach((p) => {
      const li = COD2LI[String(p.dataset.cod)];
      const v = li === undefined ? null : raw(ind, li, ano);
      p.setAttribute("fill", corValor(ind, ano, v));
      p.setAttribute("stroke", li === focoLi ? "#0D1520" : "#fff");
      p.setAttribute("stroke-width", li === focoLi ? "2.2" : ".6");
    });
  }

  /* ---------------------------------------------------------- mapa (2 filtros) */
  // indicadores que fazem sentido colorir por quintil (proporção/taxa, sem recorte)
  // mapa: só indicadores oficiais já proporcionalizados (percentual/taxa)
  const elegMapa = () => INDS.filter(elegivelRanking);

  const rotuloBase = (i) => i.gcurto + (i.recorte && i.recorte !== "Total" ? " · " + i.recorte : "");

  function rotulosUnicos(lista) {
    const cont = new Map();
    lista.forEach((i) => cont.set(rotuloBase(i), (cont.get(rotuloBase(i)) || 0) + 1));
    const out = new Map();
    const usados = new Set();
    lista.forEach((i) => {
      let rotulo = rotuloBase(i);
      if (cont.get(rotulo) > 1) {
        let det = rotuloItem(i);
        if (det === "Total") det = i.medida.replace(/^(Número de|Taxa de|Proporção de|Percentual d[eo])\s+/i, "");
        rotulo = `${i.gcurto} · ${det}`;
        if (usados.has(rotulo)) rotulo = `${i.gcurto} · ${det} (${i.unidade || i.tipo})`;
      }
      usados.add(rotulo);
      out.set(i.id, rotulo);
    });
    return out;
  }

  function atualizarMapa() {
    const selOds = $("#mapa-ods");
    const selInd = $("#mapa-ind");
    const listaTotal = elegMapa();
    if (!selOds || !selInd || !listaTotal.length) return;

    if (!selOds.dataset.ready) {
      selOds.innerHTML = ODS
        .map((o) => ({ o, n: listaTotal.filter((i) => i.ods === o.n).length }))
        .filter((x) => x.n > 0)
        .map((x) => `<option value="${x.o.n}">ODS ${x.o.n} · ${x.o.nome} (${x.n})</option>`)
        .join("");
      selOds.dataset.ready = "1";
      selOds.addEventListener("change", () => {
        state.mapaOds = +selOds.value;
        state.mapaInd = null;
        atualizarMapa();
      });
      selInd.addEventListener("change", () => {
        state.mapaInd = selInd.value;
        atualizarMapa();
      });
    }

    const ods = state.mapaOds || 3;
    const lista = listaTotal.filter((i) => i.ods === ods);
    selOds.value = String(ods);
    const rotulos = rotulosUnicos(lista);
    selInd.innerHTML = lista.map((i) => `<option value="${i.id}">${rotulos.get(i.id)}</option>`).join("");

    let ind = INDS.find((i) => i.id === state.mapaInd);
    if (!ind || ind.ods !== ods) ind = lista.find((i) => i.id === principalDe(ods).id) || lista[0];
    if (!ind) return;

    state.mapaInd = ind.id;
    selInd.value = ind.id;
    const ano = ultimoAnoDado(ind);
    pintarMapa($("#mapa"), ind, ano, state.local);
    const recorte = ind.recorte && ind.recorte !== "Total" ? " · " + ind.recorte : "";
    $("#mapa-leg-txt").innerHTML =
      `${ind.gcurto}${recorte} · último dado: ${seloAno(ano)}`;
    $("#mapa-leg-a").textContent = ind.pol === 0 ? "menor" : "pior";
    $("#mapa-leg-b").textContent = ind.pol === 0 ? "maior" : "melhor";
  }

  /* ---------------------------------------------------------- home */
  const PRINCIPAL = {
    1: "Despesas Públicas Municipais com Educação",
    2: "Nascidos Vivos com Baixo Peso ao Nascer - Total",
    3: "Taxa de Mortalidade Infantil em Menores de 1 ano de Idade - Total",
    4: "Anos Iniciais do Ensino Fundamental que Atingiram um Nível Mínimo de Proficiência em Língua Portuguesa - Total",
    5: "Cadeiras Ocupadas por Mulheres nas Câmaras de Vereadores - Total",
    6: "Atendimento de Esgoto",
    7: "Energia Elétrica Residencial",
    8: "per Capita",
    9: "Percentual do Valor Adicionado Bruto na Indústria",
    13: "Mortes, Pessoas Desaparecidas",
    15: "Remanescente Florestal",
    16: "Taxa de Mortalidade por Homicídios",
  };

  function principalDe(ods) {
    const alvo = PRINCIPAL[ods];
    if (!alvo) return INDS.find((i) => i.ods === ods);
    return INDS.find((i) => i.ods === ods && i.nome.includes(alvo)) || INDS.find((i) => i.ods === ods);
  }

  function ultimoAno(ind, anoLimite) {
    const ok = ind.anos.filter((a) => a <= anoLimite);
    return ok.length ? ok[ok.length - 1] : ind.anos[0];
  }

  // último dado disponível do indicador, independente do ano de referência global
  function ultimoAnoDado(ind) {
    return ind.anos.length ? ind.anos[ind.anos.length - 1] : null;
  }

  // o seletor de ano fica sempre visível (evita o cabeçalho pular), mas só vale nas
  // visões de exploração e comparação — na Visão geral aparece desativado
  function marcarAnoGlobal() {
    const sa = $("#sel-ano");
    if (!sa) return;
    const soLeitura = state.view === "geral";
    sa.disabled = soLeitura;
    sa.title = soLeitura ? "O ano vale para o Explorador e o Comparador; aqui a leitura usa o último dado de cada indicador" : "";
  }

  // ano de referência da base (usado para marcar dado desatualizado)
  const ANO_REF = Math.max(...INDS.flatMap((i) => i.anos));

  function seloAno(ano) {
    if (ano === null || ano === undefined) return "";
    return ano === ANO_REF
      ? `<span class="ano">${ano}</span>`
      : `<span class="ano stale" title="Último dado disponível: ${ano} — anterior a ${ANO_REF}">${ano}</span>`;
  }

  function elegivelRanking(ind) {
    return (ind.recorte === null || ind.recorte === "Total") &&
      (ind.tipo === "percentual" || ind.tipo === "taxa") && ind.pol !== 0;
  }

  function renderGeral() {
    const li = state.local;
    const loc = LOC[li];

    $("#hero-nome").textContent = loc.n;
    const eleg = INDS.filter(elegivelRanking);
    const porOds = new Map();
    let acima = 0, total = 0;
    eleg.forEach((ind) => {
      const a = ultimoAnoDado(ind);
      const p = pctMap(ind, a)[li];
      if (p === null) return;
      total++; if (p > 50) acima++;
      const g = porOds.get(ind.ods) || { soma: 0, n: 0 };
      g.soma += p; g.n++;
      porOds.set(ind.ods, g);
    });
    // semáforo: percentil médio do município nos indicadores comparáveis de cada ODS
    const semaforo = ODS.map((o) => {
      const g = porOds.get(o.n);
      return { o, media: g ? g.soma / g.n : null, n: g ? g.n : 0 };
    });
    const comOds = semaforo.filter((s) => s.media !== null).length;
    const acimaOds = semaforo.filter((s) => s.media !== null && s.media > 50).length;
    $("#hero-sub").innerHTML =
      `Posição de <b>${loc.n}</b> frente aos 399 municípios do Paraná. ` +
      `Posições pelo último dado disponível de cada indicador (base até <b>${ANO_REF}</b>). ` +
      `Região intermediária: <b>${loc.reg || "—"}</b>.`;

    $("#hero-stats").innerHTML = `
      <div class="stat"><b>${INDS.length}</b><span>indicadores</span></div>
      <div class="stat"><b>${MUN.length}</b><span>municípios</span></div>
      <div class="stat"><b>${acima}<small style="font-size:13px;color:#7C889B">/${total}</small></b><span>acima da mediana</span></div>
      <div class="stat" title="Percentil médio do município nos indicadores comparáveis de cada ODS. Verde = acima da mediana paranaense; vermelho = abaixo; cinza claro = ODS sem indicador comparável (só contagens).">
        <b>${acimaOds}<small style="font-size:13px;color:#7C889B">/${comOds}</small></b>
        <span>ODS acima da mediana</span>
        <div class="semaforo">${semaforo.map((s) => `<i class="${s.media === null ? "nd" : s.media > 50 ? "up" : "down"}" title="ODS ${s.o.n} · ${s.o.nome} — ${s.media === null ? "sem indicador comparável" : "percentil médio " + Math.round(s.media) + " em " + s.n + " indicadores"}"></i>`).join("")}</div>
      </div>`;

    // cards ODS
    const grid = $("#ods-grid");
    grid.innerHTML = "";
    ODS.forEach((o) => {
      const ind = principalDe(o.n);
      if (!ind) return;
      const ano = ultimoAnoDado(ind);
      const v = raw(ind, li, ano);
      const p = pctMap(ind, ano)[li];
      const rk = rankOf(ind, li, ano);
      const serie = rawSerie(ind, li).slice(-10);
      const f = fmt(v, ind);
      const extra = rotuloItem(ind);
      const detalhe = extra !== "Total" && extra.split(/\s+/).length <= 3 &&
        !mesmoTema(extra, ind.gcurto) && !mesmoTema(ind.gcurto, extra);
      const subInd = ind.gcurto + (detalhe ? " · " + extra : "");
      const card = el("button", "ods-card");
      card.style.setProperty("--c", o.cor);
      card.innerHTML = `
        <div class="ods-top">
          <span class="ods-num">${o.n}</span>
          <span class="ods-name">${o.nome}</span>
        </div>
        <div class="ods-ind" title="${ind.grupo} · ${ind.medida}">${subInd}</div>
        <div class="ods-val">
          <div><b>${f.t}</b><small>${f.u || unitShort(ind)}</small></div>
          ${sparkline(serie, o.cor)}
        </div>
        <div class="ods-foot">
          ${
            ind.tipo === "contagem"
              ? rk
                ? rk.empateFrac > 0.3
                  ? `<span class="badge mid" title="Muitos municípios com o mesmo valor: ${rk.igual} de ${rk.total}">empate: ${rk.igual} municípios</span>${seloAno(ano)}`
                  : `<span class="badge mid">${rk.pos}º em volume</span>${seloAno(ano)}`
                : `<span class="badge mid">sem dado em ${ano}</span>`
              : p === null
              ? `<span class="badge mid">sem dado em ${ano}</span>`
              : rk && rk.empateFrac > 0.3
              ? `<span class="badge mid" title="Muitos municípios com o mesmo valor: ${rk.igual} de ${rk.total}">empate: ${rk.igual} municípios</span>${seloAno(ano)}`
              : `<span class="badge ${p >= 60 ? "good" : p < 40 ? "bad" : "mid"}">${rk ? rk.pos + "º de " + rk.total : ""}</span>
                 ${seloAno(ano)}`
          }
        </div>`;
      card.addEventListener("click", () => {
        state.indId = ind.id;
        state.odsFiltro = o.n;
        irPara("explorador");
      });
      grid.appendChild(card);
    });

    // mapa
    atualizarMapa();

    // destaques
    const notas = [];
    eleg.forEach((ind) => {
      const a = ultimoAnoDado(ind);
      const st = stats(ind, a);
      if (!st) return;
      // descarta indicadores sem poder de discriminação (muitos municípios empatados)
      if (st.empateFrac > 0.3) return;
      const p = pctMap(ind, a)[li];
      if (p === null) return;
      notas.push({ ind, ano: a, p, v: raw(ind, li, a) });
    });
    notas.sort((a, b) => b.p - a.p);
    // no máximo 1 indicador por grupo em cada coluna, para variar os temas
    const diversificar = (arr, vistos) => {
      const out = [];
      for (const n of arr) {
        const g = n.ind.ods + "|" + n.ind.gcurto;
        if (vistos.has(g)) continue;
        vistos.add(g); out.push(n);
        if (out.length === 5) break;
      }
      return out;
    };
    const vistosG = new Set();
    const melhores = diversificar(notas, vistosG);
    const piores = diversificar([...notas].reverse(), vistosG);
    const linha = (n) => {
      const f = fmt(n.v, n.ind);
      const rec = (n.ind.recorte && n.ind.recorte !== "Total") ? `<span class="rec">${n.ind.recorte}</span>` : "";
      return `<button class="list-item" data-ind="${n.ind.id}" title="${n.ind.grupo} · ${n.ind.medida}">
        <span class="pos">${n.p}%</span>
        <span class="nm"><span class="tt">${n.ind.gcurto}</span><small>${rec}${seloAno(n.ano)}</small></span>
        <span class="vl">${f.t}${f.u ? " " + f.u : ""}</span>
      </button>`;
    };
    $("#destaques").innerHTML = `
      <div style="display:grid;grid-template-columns:minmax(0,1fr);gap:14px">
        <div>
          <div style="font-size:12px;font-weight:600;color:var(--good);margin:4px 0 4px">Melhores posições</div>
          <div class="lists">${melhores.map((n) => linha(n)).join("")}</div>
        </div>
        <div>
          <div style="font-size:12px;font-weight:600;color:var(--bad);margin:4px 0 4px">Pontos de atenção</div>
          <div class="lists">${piores.map((n) => linha(n)).join("")}</div>
        </div>
      </div>`;
    $$("#destaques .list-item").forEach((b) =>
      b.addEventListener("click", () => { state.indId = b.dataset.ind; irPara("explorador"); })
    );
  }

  /* ---------------------------------------------------------- explorador */
  function renderListaInd() {
    const q = state.busca.toLowerCase();
    const list = $("#lista-ind");
    const scroll = list.scrollTop;
    list.innerHTML = "";
    const filtrados = INDS.filter((i) =>
      (!state.odsFiltro || i.ods === state.odsFiltro) &&
      (!q || (i.grupo + " " + i.medida + " " + (i.recorte || "")).toLowerCase().includes(q))
    );
    // medidas repetidas no mesmo grupo = variação por recorte; aí o recorte vira o título
    let grupoAtual = null;
    filtrados.forEach((i) => {
      const g = `ODS ${i.ods} · ${i.gcurto}`;
      if (g !== grupoAtual) {
        grupoAtual = g;
        list.appendChild(el("div", "ind-group", g));
      }
      const titulo = rotuloItem(i);
      const sub = [unitShort(i) || i.unidade].filter(Boolean).join(" · ");
      const b = el("button", "ind-item" + (state.indId === i.id ? " on" : ""));
      b.title = i.grupo + " · " + i.medida + (i.recorte ? " · " + i.recorte : "");
      b.innerHTML = `<span class="t">${titulo}</span><span class="u">${sub}</span>`;
      b.addEventListener("click", () => { state.indId = i.id; renderDetalhe(); renderListaInd(); });
      list.appendChild(b);
    });
    if (!filtrados.length) list.appendChild(el("div", "empty", "Nenhum indicador encontrado."));
    list.scrollTop = scroll;
    const on = list.querySelector(".ind-item.on");
    if (on) on.scrollIntoView({ block: "nearest" });
  }

  function renderFiltroOds() {
    const sel = $("#sel-ods-exp");
    if (!sel) return;
    const contagem = {};
    INDS.forEach((i) => { contagem[i.ods] = (contagem[i.ods] || 0) + 1; });
    sel.innerHTML = `<option value="">Todos os ODS (${INDS.length})</option>` +
      ODS.map((o) => `<option value="${o.n}">ODS ${o.n} · ${o.nome} (${contagem[o.n] || 0})</option>`).join("");
    sel.value = state.odsFiltro === null ? "" : String(state.odsFiltro);
    if (!sel.dataset.ready) {
      sel.dataset.ready = "1";
      sel.addEventListener("change", () => {
        state.odsFiltro = sel.value ? +sel.value : null;
        const atual = INDS.find((i) => i.id === state.indId);
        if (state.odsFiltro !== null && (!atual || atual.ods !== state.odsFiltro)) {
          state.indId = principalDe(state.odsFiltro).id;
        }
        renderDetalhe();
        renderListaInd();
      });
    }
  }

  function renderDetalhe() {
    const host = $("#detalhe");
    const base = INDS.find((i) => i.id === state.indId) || principalDe(3);
    state.indId = base.id;
    const ind = indExib(base);
    const li = state.local;
    const loc = LOC[li];
    const o = ODS.find((x) => x.n === ind.ods);
    const ano = ultimoAno(ind, Math.min(state.ano, ind.anos[ind.anos.length - 1]));
    const anoFallback = ano !== state.ano;
    const defasagem = ano === null ? 0 : ANO_REF - ano;
    const defasado = defasagem >= 3;
    const v = raw(ind, li, ano);
    const st = stats(ind, ano);
    const rk = rankOf(ind, li, ano);
    const p = pctMap(ind, ano)[li];
    const vEstado = raw(ind, 0, ano);
    const regLi = LOC.findIndex((l) => l.n === "RGInt de " + loc.reg);
    const vReg = regLi > 0 ? raw(ind, regLi, ano) : null;
    const f = fmt(v, ind);
    const fEst = fmt(vEstado, ind);
    const fMed = fmt(st ? st.med : null, ind);

    host.innerHTML = "";
    const head = el("div", "card");
    head.innerHTML = `
      <div class="detail-head">
        <div>
          <span class="badge" style="background:${o.cor}1a;color:${o.cor}">ODS ${o.n} · ${o.nome}</span>
          <h2>${ind.gcurto}</h2>
          <p class="sub">${ind.medida}${tag(ind) ? ` · <b>${tag(ind)}</b>` : ""}</p>
          <p class="sub" style="margin-top:6px">Dado exibido: ${seloAno(ano)}${
            anoFallback
              ? ` <span class="aviso">o ano ${state.ano} não tem dado — usamos o último anterior</span>`
              : ""
          }</p>
        </div>
        <div class="detail-ctrl">
          <div class="quick-col">
            <label>Ano</label>
            <select class="select" id="sel-ano-ind">${ind.anos.slice().reverse().map((a) => `<option ${a === ano ? "selected" : ""}>${a}</option>`).join("")}</select>
          </div>
          ${modoCtrls(base) ? `<div class="quick-col"><label>Exibição</label>${modoCtrls(base)}</div>` : ""}
        </div>
      </div>
      ${defasado ? `<div class="aviso-box"><b>Série desatualizada.</b> O último dado disponível é de <b>${ano}</b> — ${defasagem} anos sem atualização. A posição relativa, o ranking e o que aparece em “pontos de atenção” usam esse mesmo ano.</div>` : ""}
      <div class="kpis" style="margin-top:16px">
        <div class="kpi"><span>${loc.n}</span><b>${f.t}</b><small>${f.u || unitShort(ind)}</small></div>
        <div class="kpi"><span>Posição</span><b>${rk ? (rk.empateFrac > 0.3 ? "empate" : rk.pos + "º") : "—"}</b><small>${
          rk
            ? (rk.empateFrac > 0.3
              ? `${rk.igual} de ${rk.total} com o mesmo valor`
              : (ind.tipo === "contagem" ? "em volume, de " + rk.total : "de " + rk.total))
            : "sem dado"
        }</small></div>
        <div class="kpi"><span>Mediana dos municípios</span><b>${fMed.t}</b><small>${fMed.u || unitShort(ind)}</small></div>
        <div class="kpi"><span>Estado do Paraná</span><b>${fEst.t}</b><small>${fEst.u || unitShort(ind)}</small></div>
        ${vReg !== null ? `<div class="kpi"><span>RGInt de ${loc.reg}</span><b>${fmt(vReg, ind).t}</b><small>${fmt(vReg, ind).u || unitShort(ind)}</small></div>` : ""}
      </div>
      <p class="nota">Valor <b>0</b> é dado real (ex.: nenhuma ocorrência no período); <b>—</b> indica dado inexistente para o ano ou recorte. As unidades seguem o padrão oficial de cada indicador. <b>*</b> taxa calculada a partir da população do IBGE — não é dado oficial.</p>`;
    host.appendChild(head);

    // gráfico
    const cardChart = el("div", "card");
    cardChart.innerHTML = `<div class="card-head"><h3>Série histórica</h3><div class="legend-inline" id="lg"></div></div><div id="chart"></div>`;
    host.appendChild(cardChart);

    const series = [
      { name: loc.n, color: "#114E7A", width: 2.4, values: rawSerie(ind, li) },
      { name: "Estado do Paraná", color: "#64748B", width: 1.6, dash: "5 4", values: rawSerie(ind, 0) },
      { name: "Mediana dos municípios", color: "#94A3B8", width: 1.4, dash: "2 3", values: ind.anos.map((a) => { const s = stats(ind, a); return s ? s.med : null; }) },
    ];
    if (regLi > 0) series.splice(1, 0, { name: "RGInt de " + loc.reg, color: "#C2410C", width: 1.6, dash: "6 3", values: rawSerie(ind, regLi) });
    $("#lg").innerHTML = series.map((s) => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("");
    lineChart($("#chart"), { anos: ind.anos, series, ind, height: 250 });

    // ranking + mapa
    const split = el("div", "split");
    host.appendChild(split);
    const cardRank = el("div", "card");
    cardRank.innerHTML = `<div class="card-head"><h3>Ranking · ${ano}</h3><span style="font-size:11px;color:var(--muted)">${ind.tipo === "contagem" ? "por volume" : ind.pol < 0 ? "menor é melhor" : ind.pol > 0 ? "maior é melhor" : "sem juízo de valor"}</span></div><div id="rank"></div>`;
    split.appendChild(cardRank);
    const cardMap = el("div", "card");
    cardMap.innerHTML = `<div class="card-head"><h3>Distribuição no Paraná</h3></div><div id="mapa-det"><div class="empty">…</div></div>
      <div class="legend"><span>${ind.pol === 0 ? "menor" : "pior"}</span><span class="ramp"></span><span>${ind.pol === 0 ? "maior" : "melhor"}</span><span class="nd"><i></i>sem dado</span></div>
      <div style="font-size:11px;color:var(--muted);margin-top:8px">Cor = quintil do valor entre os 399 municípios. Cinza = sem dado (diferente de zero).</div>`;
    split.appendChild(cardMap);

    // ranking
    const st2 = stats(ind, ano);
    const rkHost = $("#rank");
    if (!st2) {
      rkHost.innerHTML = '<div class="empty">Sem dados neste ano.</div>';
    } else {
      const todos = MUN.map((i) => ({ li: i, v: raw(ind, i, ano) })).filter((x) => x.v !== null);
      todos.sort((a, b) => ind.pol < 0 ? a.v - b.v : b.v - a.v);
      // posição competitiva: empates dividem a mesma colocação
      const posicoes = [];
      let r = 1;
      todos.forEach((x, i) => {
        if (i > 0 && x.v !== todos[i - 1].v) r = i + 1;
        posicoes.push(r);
      });
      const iEu = todos.findIndex((x) => x.li === li);
      const ini = iEu >= 0 ? Math.max(0, iEu - 4) : 0;
      const janela = todos.slice(ini, ini + (iEu >= 0 ? 9 : 8));
      // escala na janela exibida, com folga para as diferenças ficarem legíveis
      const vmax = Math.max(...janela.map((x) => x.v));
      const vmin = Math.min(...janela.map((x) => x.v));
      const span = (vmax - vmin) || Math.abs(vmax) * 0.1 || 1;
      const esc = (v) => 10 + 88 * ((v - (vmin - span * 0.15)) / (span * 1.25));
      const row = (x) => {
        const p = posicoes[todos.indexOf(x)];
        return `<div class="rank-row ${x.li === li ? "me" : ""}">
          <span class="rk">${p}º</span>
          <span class="nm">${LOC[x.li].n}</span>
          <span class="bar"><i style="width:${esc(x.v)}%" class="${x.li === li ? "me" : ""}"></i></span>
          <span class="vl">${fmt(x.v, ind).t}</span>
        </div>`;
      };
      rkHost.innerHTML =
        (iEu >= 0
          ? `<div style="font-size:11px;color:var(--muted);margin-bottom:8px">${loc.n} está na ${posicoes[iEu]}ª posição de ${todos.length}${ind.tipo === "contagem" ? " em volume" : ""}.` +
            (st2.empateFrac > 0.3 ? ` Atenção: ${st2.maiorEmpate} municípios compartilham o mesmo valor — empates dividem a colocação.` : "") +
            `</div>`
          : "") +
        janela.map(row).join("");
    }
    pintarMapa($("#mapa-det"), ind, ano, li);

    // sobre
    const cardMeta = el("div", "card");
    cardMeta.innerHTML = `
      <div class="card-head"><h3>Sobre o indicador</h3><span style="font-size:11px;color:var(--muted)">código ${ind.codigo || "—"}</span></div>
      <dl class="meta-grid">
        <div><dt>Unidade</dt><dd>${ind.unidade || "—"}</dd></div>
        <div><dt>Fonte</dt><dd>${ind.fonte || "—"}</dd></div>
        <div class="wide"><dt>Definição</dt><dd>${ind.definicao || "—"}</dd></div>
        <div class="wide"><dt>Fórmula</dt><dd>${ind.formula || "—"}</dd></div>
        ${ind.derivado ? `<div class="wide"><dt>Valor calculado</dt><dd>Total do indicador ÷ população residente (IBGE) × 100.000. Não é um dado oficial: é uma taxa derivada para comparar municípios de portes diferentes.</dd></div>` : ""}
      </dl>`;
    host.appendChild(cardMeta);

    // tabela
    const cardTab = el("div", "card");
    const anos = ind.anos.slice().reverse();
    cardTab.innerHTML = `
      <div class="card-head"><h3>Valores por ano</h3></div>
      <div style="overflow:auto;max-height:320px">
      <table class="data"><thead><tr><th>Ano</th><th>${loc.n}</th><th>RGInt</th><th>Paraná</th><th>Mediana</th></tr></thead>
      <tbody>${anos.map((a) => {
        const rl = regLi > 0 ? raw(ind, regLi, a) : null;
        const s = stats(ind, a);
        return `<tr><td>${a}</td><td>${fmt(raw(ind, li, a), ind).t}</td><td>${rl === null ? "—" : fmt(rl, ind).t}</td><td>${fmt(raw(ind, 0, a), ind).t}</td><td>${s ? fmt(s.med, ind).t : "—"}</td></tr>`;
      }).join("")}</tbody></table></div>`;
    host.appendChild(cardTab);

    $("#sel-ano-ind").addEventListener("change", (e) => {
      state.ano = +e.target.value;
      $("#sel-ano").value = state.ano;
      renderDetalhe();
    });
    ligarModo(host, renderDetalhe);
  }

  /* ---------------------------------------------------------- revisão de polaridade */
  const POL_KEY = "painelods.pol.v1";

  function polSalva() {
    try { return JSON.parse(window.localStorage.getItem(POL_KEY) || "{}"); } catch (e) { return {}; }
  }

  function gravarPol(obj) {
    try { window.localStorage.setItem(POL_KEY, JSON.stringify(obj)); } catch (e) { /* file:// bloqueado: segue só na sessão */ }
  }

  // aplica as escolhas do revisor sobre a proposta automática do gerador
  function aplicarPolaridade() {
    const salvo = polSalva();
    INDS.forEach((i) => {
      if (i.polAuto === undefined) i.polAuto = i.pol;
    });
    Object.keys(salvo).forEach((id) => {
      const ind = INDS.find((x) => x.id === id);
      if (ind) { ind.pol = salvo[id]; ind.polRevisado = true; }
    });
  }

  function definirPolaridade(id, valor) {
    const ind = INDS.find((x) => x.id === id);
    if (!ind) return;
    const salvo = polSalva();
    if (valor === ind.polAuto) { delete salvo[id]; ind.polRevisado = false; }
    else { salvo[id] = valor; ind.polRevisado = true; }
    ind.pol = valor;
    gravarPol(salvo);
    pctCache.clear();
    renderRevisao();
  }

  const POL_TXT = { "-1": "menor é melhor", "0": "sem juízo de valor", "1": "maior é melhor" };

  function renderRevisao() {
    const lista = $("#rev-lista");
    const selOds = $("#rev-ods");
    if (!selOds.dataset.ready) {
      selOds.innerHTML = `<option value="">Todos os ODS</option>` +
        ODS.map((o) => `<option value="${o.n}">ODS ${o.n} · ${o.nome}</option>`).join("");
      selOds.dataset.ready = "1";
      selOds.addEventListener("change", renderRevisao);
      $("#rev-tipo").addEventListener("change", renderRevisao);
      $("#rev-pend").addEventListener("change", renderRevisao);
      $("#rev-export").addEventListener("click", () => {
        const obj = polSalva();
        const txt = JSON.stringify(obj, null, 2);
        try { if (navigator.clipboard) navigator.clipboard.writeText(txt); } catch (e) { /* segue para o download */ }
        try {
          const a = document.createElement("a");
          a.href = "data:application/json;charset=utf-8," + encodeURIComponent(txt);
          a.download = "polaridade.json";
          a.click();
        } catch (e) { /* sem download disponível */ }
        $("#rev-export").textContent = "Exportado (" + Object.keys(obj).length + " alterações)";
        setTimeout(() => { $("#rev-export").textContent = "Copiar JSON das alterações"; }, 2000);
      });
      $("#rev-clear").addEventListener("click", () => {
        gravarPol({});
        INDS.forEach((i) => { i.pol = i.polAuto; i.polRevisado = false; });
        pctCache.clear();
        renderRevisao();
      });
    }

    const ods = selOds.value ? +selOds.value : null;
    const tipo = $("#rev-tipo").value;
    const soPend = $("#rev-pend").checked;
    const total = INDS.length;
    const revisados = INDS.filter((i) => i.polRevisado).length;
    $("#rev-prog").textContent = `${revisados} de ${total} revisados · proposta automática em ${total - revisados}`;

    const filtrados = INDS.filter((i) =>
      (!ods || i.ods === ods) && (!tipo || i.tipo === tipo) && (!soPend || !i.polRevisado));

    lista.innerHTML = filtrados.map((i) => {
      const rec = i.recorte && i.recorte !== "Total" ? " · " + i.recorte : "";
      const botoes = [-1, 0, 1].map((v) => `<button data-id="${i.id}" data-v="${v}" class="${i.pol === v ? "on p" + v : ""}">${POL_TXT[v]}</button>`).join("");
      return `<div class="rev-row">
        <div class="rev-nome">
          <b>${i.gcurto}</b>${rec}
          <small title="${i.grupo} · ${i.medida}">${i.medida}</small>
          <span class="rev-meta">ODS ${i.ods} · ${i.tipo}${i.unidade ? " · " + i.unidade : ""}</span>
        </div>
        <div class="rev-pol">${botoes}<span class="rev-tag ${i.polRevisado ? "ok" : ""}">${i.polRevisado ? "revisado" : "auto"}</span></div>
      </div>`;
    }).join("");

    $$("#rev-lista .rev-pol button").forEach((b) =>
      b.addEventListener("click", () => definirPolaridade(b.dataset.id, +b.dataset.v)));
  }


  /* ---------------------------------------------------------- comparador */
  const CORES_CMP = ["#114E7A", "#C2410C", "#0E8A5F", "#7C3AED", "#B7791F", "#0E7490"];

  function renderComparador() {
    const selOds = $("#cmp-ods");
    const sel = $("#cmp-ind");

    // filtro de ODS (independente do seletor de indicador)
    const contagem = {};
    INDS.forEach((i) => { contagem[i.ods] = (contagem[i.ods] || 0) + 1; });
    if (!selOds.dataset.ready) {
      selOds.innerHTML = `<option value="">Todos os ODS (${INDS.length})</option>` +
        ODS.map((o) => `<option value="${o.n}">ODS ${o.n} · ${o.nome} (${contagem[o.n] || 0})</option>`).join("");
      selOds.dataset.ready = "1";
      selOds.addEventListener("change", () => {
        state.cmpOds = selOds.value ? +selOds.value : null;
        state.cmpInd = null;
        state.cmpAno = null;
        renderComparador();
      });
    }

    if (!state.cmpInd) {
      const alvo = state.cmpOds === null || state.cmpOds === undefined ? 3 : state.cmpOds;
      state.cmpInd = (principalDe(alvo) || INDS[0]).id;
    }
    const listaCmp = INDS.filter((i) => state.cmpOds === null || state.cmpOds === undefined || i.ods === state.cmpOds);
    const opcao = (i) => `<option value="${i.id}">${i.gcurto} — ${i.medida}${i.recorte && i.recorte !== "Total" ? " (" + i.recorte + ")" : ""}</option>`;
    sel.innerHTML = state.cmpOds === null || state.cmpOds === undefined
      ? ODS.filter((o) => listaCmp.some((i) => i.ods === o.n))
        .map((o) => `<optgroup label="ODS ${o.n} · ${o.nome}">` + listaCmp.filter((i) => i.ods === o.n).map(opcao).join("") + `</optgroup>`).join("")
      : listaCmp.map(opcao).join("");
    if (!sel.dataset.ready) {
      sel.dataset.ready = "1";
      sel.addEventListener("change", () => { state.cmpInd = sel.value; state.cmpAno = null; renderComparador(); });
    }
    const base = INDS.find((i) => i.id === state.cmpInd) || principalDe(3);
    state.cmpInd = base.id;
    selOds.value = state.cmpOds === null || state.cmpOds === undefined ? "" : String(state.cmpOds);
    sel.value = base.id;
    const ind = indExib(base);
    if ($("#cmp-modo")) {
      $("#cmp-modo").innerHTML =
        (ind.derivado ? '<span class="tag-calc">taxa calculada por 100 mil hab.*</span>' : "") + modoCtrls(base);
      ligarModo($("#cmp-modo"), renderComparador);
    }

    const selAno = $("#cmp-ano");
    const baseAno = state.cmpAno && ind.anos.indexOf(state.cmpAno) >= 0 ? state.cmpAno : ultimoAno(ind, state.ano);
    state.cmpAno = baseAno;
    selAno.innerHTML = ind.anos.slice().reverse().map((a) => `<option ${a === baseAno ? "selected" : ""}>${a}</option>`).join("");
    selAno.value = baseAno;
    selAno.onchange = () => { state.cmpAno = +selAno.value; renderComparador(); };
    if ($("#cmp-selo")) $("#cmp-selo").innerHTML = `Dado exibido: ${seloAno(baseAno)}`;

    // chips
    const chips = $("#cmp-chips");
    chips.innerHTML = "";
    state.cmp.forEach((li, k) => {
      const c = el("span", "loc-chip", `${LOC[li].n}<button title="Remover">×</button>`);
      c.style.background = CORES_CMP[k % 6] + "18";
      c.style.color = CORES_CMP[k % 6];
      c.querySelector("button").addEventListener("click", () => {
        if (state.cmp.length <= 1) return;
        state.cmp.splice(k, 1); renderComparador();
      });
      chips.appendChild(c);
    });
    if (state.cmp.length < 6) {
      const b = el("button", "btn-add", "+ Adicionar localidade");
      b.addEventListener("click", () => abrirPicker((li) => {
        if (!state.cmp.includes(li)) state.cmp.push(li);
        renderComparador();
      }));
      chips.appendChild(b);
    }

    // gráfico
    const series = state.cmp.map((li, k) => ({
      name: LOC[li].n, color: CORES_CMP[k % 6], width: li === state.local ? 2.6 : 1.9,
      values: rawSerie(ind, li),
    }));
    lineChart($("#cmp-chart"), { anos: ind.anos, series, ind, height: 280 });
    $("#cmp-lg").innerHTML = series.map((s) => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("");

    // tabela
    const anos = ind.anos.filter((a) => a <= state.cmpAno).slice(-12).reverse();
    $("#cmp-tabela").innerHTML = `
      <table class="data"><thead><tr><th>Localidade</th>${anos.map((a) => `<th>${a}</th>`).join("")}</tr></thead>
      <tbody>${state.cmp.map((li) => `<tr><td>${LOC[li].n}</td>${anos.map((a) => `<td>${fmt(raw(ind, li, a), ind).t}</td>`).join("")}</tr>`).join("")}</tbody></table>`;

    // destaque do ano
    $("#cmp-resumo").innerHTML = state.cmp.map((li, k) => {
      const v = raw(ind, li, state.cmpAno);
      const f = fmt(v, ind);
      const rk = rankOf(ind, li, state.cmpAno);
      return `<div class="kpi" style="border-left:3px solid ${CORES_CMP[k % 6]}">
        <span>${LOC[li].n}</span><b>${f.t}</b>
        <small>${f.u || unitShort(ind)}${rk ? (rk.empateFrac > 0.3 ? ` · empate: ${rk.igual} de ${rk.total}` : " · " + rk.pos + "º de " + rk.total + (base.tipo === "contagem" ? " em volume" : "")) : ""}</small></div>`;
    }).join("");
  }

  /* ---------------------------------------------------------- picker */
  let pickerCb = null;
  function abrirPicker(cb) {
    pickerCb = cb;
    $("#pop-local").classList.add("open");
    $("#busca-local").value = "";
    preencherPicker("");
    setTimeout(() => $("#busca-local").focus(), 30);
  }
  function preencherPicker(q) {
    const list = $("#lista-local");
    const qq = q.toLowerCase();
    list.innerHTML = "";
    LOC.forEach((l, i) => {
      if (qq && !l.n.toLowerCase().includes(qq)) return;
      const b = el("button", l.n === LOC[state.local].n ? "sel" : "", l.n);
      b.addEventListener("click", () => {
        $("#pop-local").classList.remove("open");
        if (pickerCb) { pickerCb(i); pickerCb = null; return; }
        state.local = i;
        $("#btn-local").innerHTML = `${l.n} <svg width="9" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
        renderGeral();
        if (state.view === "explorador") renderDetalhe();
      });
      list.appendChild(b);
    });
  }

  /* ---------------------------------------------------------- navegação */
  function irPara(v) {
    state.view = v;
    $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
    $$(".view").forEach((s) => s.classList.toggle("active", s.id === "view-" + v));
    // o ano global só faz sentido nas visões de exploração e comparação
    marcarAnoGlobal();
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function render() {
    if (state.view === "geral") renderGeral();
    if (state.view === "explorador") { renderFiltroOds(); renderDetalhe(); renderListaInd(); }
    if (state.view === "comparador") renderComparador();
    if (state.view === "revisao") renderRevisao();
  }

  /* ---------------------------------------------------------- init */
  function init() {
    // polaridade revisada pelo usuário (localStorage) sobre a proposta automática
    aplicarPolaridade();

    // ano global
    const anos = Array.from(new Set(INDS.flatMap((i) => i.anos))).sort((a, b) => b - a);
    const selAno = $("#sel-ano");
    selAno.innerHTML = anos.map((a) => `<option ${a === state.ano ? "selected" : ""}>${a}</option>`).join("");
    selAno.addEventListener("change", () => { state.ano = +selAno.value; state.cmpAno = null; render(); });

    // picker
    $("#btn-local").innerHTML = `${LOC[state.local].n} <svg width="9" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
    $("#btn-local").addEventListener("click", (e) => {
      e.stopPropagation();
      const p = $("#pop-local");
      if (p.classList.contains("open")) p.classList.remove("open");
      else abrirPicker(null);
    });
    $("#busca-local").addEventListener("input", (e) => preencherPicker(e.target.value));
    document.addEventListener("click", (e) => {
      if (!e.target.closest("#pop-local") && !e.target.closest("#btn-local") && !e.target.closest(".btn-add")) {
        $("#pop-local").classList.remove("open");
      }
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#pop-local").classList.remove("open"); });

    // tabs
    $$(".tabs button").forEach((b) => b.addEventListener("click", () => irPara(b.dataset.view)));
    marcarAnoGlobal();

    // explorador
    $("#busca-ind").addEventListener("input", (e) => { state.busca = e.target.value; renderListaInd(); });

    // comparador default
    const g = LOC.findIndex((l) => l.n === "Guarapuava");
    const r = LOC.findIndex((l) => l.n === "RGInt de Guarapuava");
    state.cmp = [g, 0, r].filter((x) => x >= 0);

    // resize
    let t = null;
    window.addEventListener("resize", () => {
      clearTimeout(t);
      t = setTimeout(() => { if (state.view === "explorador") renderDetalhe(); if (state.view === "comparador") renderComparador(); }, 180);
    });

    render();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
