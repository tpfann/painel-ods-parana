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

  // escape de texto vindo dos dados (nomes, definições, unidades...)
  const esc = (s) => String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  // integridade do payload: impede exibir dados de gerações diferentes
  function checarIntegridade() {
    const problemas = [];
    const build = EN.build || null;
    if (!build || !build.id) {
      problemas.push("manifesto do payload ausente (BI.build) — rode scripts/03_build_bi.py");
    }
    // todos os arquivos do payload precisam ser da mesma geração
    const builds = EN.builds || {};
    const ids = new Set(Object.values(builds).map((b) => b && b.id).filter(Boolean));
    if (ids.size > 1) {
      problemas.push("arquivos do payload de gerações diferentes (" + [...ids].join(" × ") +
        ") — regere tudo: 00 → 01 → 04 → 03");
    }
    INDS.forEach((i) => {
      const arr = EN.valores[i.id];
      if (!arr) { problemas.push(`indicador ${i.id} (${i.gcurto}) sem valores`); return; }
      const esperado = LOC.length * i.anos.length;
      if (arr.length !== esperado) {
        problemas.push(`indicador ${i.id} (${i.gcurto}) com ${arr.length} valores (esperado ${esperado})`);
      }
    });
    if (problemas.length) {
      document.body.innerHTML =
        `<div class="erro-carga"><h1>Payload inconsistente</h1><p>O painel não pode ser exibido com segurança:</p><ul>` +
        problemas.slice(0, 8).map((p) => `<li>${esc(p)}</li>`).join("") +
        `</ul><p class="dica">Regere o payload na ordem: <code>00 → 01 → 04 → 03</code>.</p></div>`;
      return false;
    }
    return true;
  }

  /* ---------------------------------------------------------- estado */
  // índices nomeados (evita depender da posição da localidade no array)
  const LOC_ID = {
    estado: LOC.findIndex((l) => l.t === "estado"),
    rgint: (nome) => LOC.findIndex((l) => l.t === "regiao" && l.reg === nome),
    municipio: (nome) => LOC.findIndex((l) => l.t === "municipio" && l.n === nome),
  };

  const state = {
    view: "geral",
    local: LOC_ID.municipio("Guarapuava"),
    ano: Math.max(...INDS.flatMap((i) => i.anos)),  // ano explorado (Explorador/Comparador)
    indId: null,
    odsFiltro: null,
    busca: "",
    cmp: [LOC_ID.municipio("Guarapuava"), LOC_ID.estado],
    cmpInd: null,
    cmpAno: null,
    cmpOds: null,
    mapaOds: 3,
    mapaInd: null,
    modo: "absoluto",
    rankModo: "perto",   // perto | top | bottom
  };

  /* ---------------------------------------------------------- dados */
  // núcleo de cálculo (core.js) — mesma lógica roda no navegador e nos testes
  const C = window.CORE.criar({ INDS, LOC, MUN, ODS, EN, POP });
  const {
    popDe, popAnoUsado, derivado, podeProporcional, taxa100k,
    raw, rawSerie, stats, pctMap, rankOf,
    quebras, corValor,
    elegivelMapa, elegivelRanking, elegivelSintese,
    unitShort, fmt, fmtShort, fmtValor,
  } = C;

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
  // (unitShort, fmt, fmtShort, fmtValor vêm de core.js)

  function fmtAno(a) { return String(a); }

  /* ---------------------------------------------------------- sparkline */
  function sparkline(vals, color, w, h, anos) {
    w = w || 84; h = h || 26;
    const clean = vals.filter((v) => v !== null && v !== undefined);
    if (clean.length < 2) return `<svg width="${w}" height="${h}"></svg>`;
    const lo = Math.min(...clean), hi = Math.max(...clean);
    const pad = (hi - lo) * 0.15 || 1;
    const X = (i) => 1 + (i / (vals.length - 1)) * (w - 2);
    const Y = (v) => h - 2 - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (h - 4);
    let d = "", open = false, prevI = -1;
    const soltos = [];
    vals.forEach((v, i) => {
      if (v === null || v === undefined) { open = false; prevI = -1; return; }
      // lacuna de mais de 1 ano: não une os pontos
      const lacuna = anos && prevI >= 0 && anos[i] - anos[prevI] > 1;
      if (lacuna) { open = false; soltos.push(i); }
      d += (open ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1);
      open = true; prevI = i;
    });
    const lastI = vals.map((v, i) => (v !== null ? i : -1)).filter((i) => i >= 0).pop();
    const lastV = vals[lastI];
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
      <path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
      ${soltos.map((i) => `<circle cx="${X(i).toFixed(1)}" cy="${Y(vals[i]).toFixed(1)}" r="1.6" fill="${color}"/>`).join("")}
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

    // séries (sem traço quando há lacuna de mais de 1 ano: não sugere interpolação)
    series.forEach((s) => {
      let d = "", open = false, prevI = -1;
      const soltos = [];
      s.values.forEach((v, i) => {
        if (v === null || v === undefined) { open = false; prevI = -1; return; }
        const lacuna = prevI >= 0 && anos[i] - anos[prevI] > 1;
        if (lacuna) { open = false; soltos.push(i); }
        d += (open ? "L" : "M") + X(anos[i]).toFixed(1) + "," + Y(v).toFixed(1);
        open = true; prevI = i;
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
      // pontos isolados (lacuna): marker, sem linha
      soltos.forEach((i) => {
        const c = document.createElementNS(NS, "circle");
        c.setAttribute("cx", X(anos[i]).toFixed(1));
        c.setAttribute("cy", Y(s.values[i]).toFixed(1));
        c.setAttribute("r", "2.6");
        c.setAttribute("fill", s.color);
        svg.appendChild(c);
      });
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
  let mapaSVG = null;
  let mapaTip = null;

  function montarMapa(host) {
    if (!MAPA) { host.innerHTML = '<div class="empty">Malha indisponível.</div>'; return null; }
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${MAPA.w} ${MAPA.h}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Mapa coroplético dos 399 municípios do Paraná");
    const g = document.createElementNS(NS, "g");
    MAPA.p.forEach((p) => {
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", p.d);
      path.setAttribute("fill", "#E9EEF4");
      path.dataset.cod = p.c;
      g.appendChild(path);
    });
    svg.appendChild(g);
    // rótulo do município em foco
    const lbl = document.createElementNS(NS, "text");
    lbl.setAttribute("class", "mapa-foco-rot");
    lbl.setAttribute("text-anchor", "middle");
    lbl.setAttribute("pointer-events", "none");
    lbl.textContent = "";
    svg.appendChild(lbl);
    host.innerHTML = "";
    host.appendChild(svg);
    if (!mapaTip) {
      mapaTip = el("div", "mapa-tip");
      mapaTip.setAttribute("role", "status");
      mapaTip.setAttribute("aria-live", "polite");
    }
    // o tooltip vive dentro do container (position: relative)
    if (mapaTip.parentNode !== host) host.appendChild(mapaTip);
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
      const foco = li === focoLi;
      p.setAttribute("stroke", foco ? "#0D1520" : "#fff");
      p.setAttribute("stroke-width", foco ? "2.2" : ".6");
      p.classList.toggle("foco", foco);
      // descrição acessível: município, valor e ano
      const nome = li === undefined ? "—" : LOC[li].n;
      const f = v === null ? { t: "—" } : fmt(v, ind);
      const rk = li === undefined ? null : rankOf(ind, li, ano);
      p.__info = {
        valor: f.t,
        unidade: v === null ? "" : (f.u || unitShort(ind)),
        ano: String(ano),
        pos: rk ? (rk.empateFrac > 0.3 ? `empate: ${rk.igual} de ${rk.total}` : `${rk.pos}º de ${rk.total}`) : "",
        semJuizo: ind.pol === 0,
      };
      p.setAttribute("aria-label", `${nome}: ${f.t} (${ano})`);
      p.dataset.li = li === undefined ? "" : String(li);
    });
    // rótulo do município em foco
    const lbl = mapaSVG.querySelector(".mapa-foco-rot");
    if (lbl) {
      const info = MAPA.p.find((x) => String(x.c) === String(COD2LI && LOC[focoLi] && LOC[focoLi].cod));
      if (focoLi !== undefined && LOC[focoLi] && LOC[focoLi].t === "municipio" && info) {
        lbl.setAttribute("x", info.x);
        lbl.setAttribute("y", info.y);
        lbl.textContent = LOC[focoLi].n;
      } else {
        lbl.textContent = "";
      }
    }
  }

  // tooltip do mapa: nome, valor, unidade, ano e posição
  function ligarMapa(host) {
    if (!host || host.dataset.tip) return;
    host.dataset.tip = "1";
    const mover = (ev) => {
      const alvo = ev.target.closest("path");
      if (!alvo || !mapaTip) return;
      const li = +alvo.dataset.li;
      const nome = LOC[li] ? LOC[li].n : "—";
      const info = alvo.__info;
      if (!info) return;
      mapaTip.innerHTML =
        `<b>${esc(nome)}</b><span>${esc(info.valor)}${info.unidade ? " " + esc(info.unidade) : ""}</span>` +
        `<small>${esc(info.ano)}${info.pos ? " · " + esc(info.pos) : ""}${info.semJuizo ? " · sem juízo de valor" : ""}</small>`;
      mapaTip.classList.add("on");
      const r = host.getBoundingClientRect();
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      mapaTip.style.left = Math.min(x + 14, r.width - 210) + "px";
      mapaTip.style.top = Math.max(y - 12, 4) + "px";
    };
    const sair = () => { if (mapaTip) mapaTip.classList.remove("on"); };
    const clicar = (ev) => {
      const alvo = ev.target.closest("path");
      if (!alvo) return;
      const li = +alvo.dataset.li;
      if (!LOC[li] || LOC[li].t !== "municipio") return;
      state.local = li;
      $("#btn-local").innerHTML = `${LOC[li].n} <svg width="9" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
      renderGeral();
      if (state.view === "explorador") renderDetalhe();
    };
    host.addEventListener("mousemove", mover);
    host.addEventListener("mouseleave", sair);
    host.addEventListener("click", clicar);
  }

  /* ---------------------------------------------------------- mapa (2 filtros) */
  // mapa: medidas comparáveis (percentual/taxa), com ou sem juízo de valor
  // (series espelhadas nao entram: a original ja esta no mapa)
  const elegMapa = () => INDS.filter((i) => elegivelMapa(i) && !i.espelho_de);

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
  // o indicador principal de cada ODS vem do catálogo (chave de negócio explícita)
  function principalDe(ods) {
    const o = ODS.find((x) => x.n === ods);
    if (o && o.principal) {
      const peloId = INDS.find((i) => i.id === o.principal);
      if (peloId) return peloId;
    }
    return INDS.find((i) => i.ods === ods);
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

  // ano de referência da base: política fixa (o dado pode ir além)
  const ANO_REF = 2025;
  const ANO_MAX_DADOS = Math.max(...INDS.flatMap((i) => i.anos));

  function seloAno(ano) {
    if (ano === null || ano === undefined) return "";
    return ano === ANO_REF
      ? `<span class="ano">${ano}</span>`
      : `<span class="ano stale" title="Último dado disponível: ${ano} — anterior a ${ANO_REF}">${ano}</span>`;
  }

  function renderGeral() {
    const li = state.local;
    const loc = LOC[li];

    $("#hero-nome").textContent = loc.n;
    const eleg = INDS.filter(elegivelRanking);
    // serie espelhada em outro ODS: conta uma vez so (a original)
    const elegUnicas = eleg.filter((i) => !i.espelho_de);
    const porOds = new Map();
    let acima = 0, total = 0;
    const foraDaSintese = [];
    elegUnicas.forEach((ind) => {
      const a = ultimoAnoDado(ind);
      const st = stats(ind, a);
      // regra de qualidade (DECISOES.md §2.3): só entra em síntese o que discrimina
      const ok = elegivelSintese(ind, st);
      if (!ok.ok) { foraDaSintese.push({ ind, a, motivo: ok.motivo }); return; }
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
      <div class="stat" title="Indicadores com medida comparável, juízo de valor e base de comparação suficiente (≥30 municípios com dado, empates ≤30%, ≥5 valores distintos).">
        <b>${acima}<small style="font-size:13px;color:#7C889B">/${total}</small></b><span>acima da mediana</span>
      </div>
      <div class="stat" title="Percentil médio do município nos indicadores comparáveis de cada ODS. Verde = acima da mediana paranaense; vermelho = abaixo; cinza claro = ODS sem indicador comparável (só contagens).">
        <b>${acimaOds}<small style="font-size:13px;color:#7C889B">/${comOds}</small></b>
        <span>ODS acima da mediana</span>
        <div class="semaforo">${semaforo.map((s) => `<i class="${s.media === null ? "nd" : s.media > 50 ? "up" : "down"}" title="ODS ${s.o.n} · ${s.o.nome} — ${s.media === null ? "sem indicador comparável" : "percentil médio " + Math.round(s.media) + " em " + s.n + " indicadores"}"></i>`).join("")}</div>
      </div>`;

    // auditoria: indicadores fora das sínteses (e por quê)
    const notaSintese = $("#nota-sintese");
    if (notaSintese) {
      notaSintese.innerHTML = foraDaSintese.length
        ? `<details class="auditoria"><summary>${foraDaSintese.length} de ${eleg.length} indicadores ficaram fora das sínteses (card acima, semáforo e destaques) — ver lista</summary>
           <ul>${foraDaSintese.map((f) => `<li><b>${esc(f.ind.gcurto)}</b>${f.ind.recorte && f.ind.recorte !== "Total" ? " · " + esc(f.ind.recorte) : ""} — ${esc(f.motivo)}</li>`).join("")}</ul>
           <p>Regra: só entra em síntese o indicador com medida comparável, juízo de valor e base de comparação suficiente (≥ ${C.REGRAS.N_MIN} municípios com dado, maior grupo de empate ≤ ${Math.round(C.REGRAS.EMPATE_MAX * 100)}%, ≥ ${C.REGRAS.DISTINTOS_MIN} valores distintos). <a href="DECISOES.md" target="_blank">Ver metodologia</a></p>
           </details>`
        : `<p class="nota">Todos os ${eleg.length} indicadores comparáveis entraram nas sínteses.</p>`;
    }

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
          <span class="ods-name">${esc(o.nome)}</span>
        </div>
        <div class="ods-ind" title="${esc(ind.grupo)} · ${esc(ind.medida)}">${esc(subInd)}${
          ind.espelho_de ? (() => {
            const o = INDS.find((x) => x.id === ind.espelho_de);
            return o ? `<br><small class="rec">mesma série oficial classificada também no ODS ${o.ods}</small>` : "";
          })() : ""
        }</div>
        <div class="ods-val">
          <div><b>${f.t}</b><small>${f.u || unitShort(ind)}</small></div>
          ${sparkline(serie, o.cor, 84, 26, ind.anos.slice(-10))}
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
    elegUnicas.forEach((ind) => {
      const a = ultimoAnoDado(ind);
      const st = stats(ind, a);
      // mesma regra das sínteses: só o que discrimina entra nos destaques
      if (!elegivelSintese(ind, st).ok) return;
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
      const rec = (n.ind.recorte && n.ind.recorte !== "Total") ? `<span class="rec">${esc(n.ind.recorte)}</span>` : "";
      return `<button class="list-item" data-ind="${esc(n.ind.id)}" title="${esc(n.ind.grupo)} · ${esc(n.ind.medida)}">
        <span class="pos">${n.p}%</span>
        <span class="nm"><span class="tt">${esc(n.ind.gcurto)}</span><small>${rec}${seloAno(n.ano)}</small></span>
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
      b.innerHTML = `<span class="t">${esc(titulo)}</span><span class="u">${esc(sub)}</span>`;
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
    const vEstado = raw(ind, LOC_ID.estado, ano);
    const regLi = loc.reg ? LOC_ID.rgint(loc.reg) : -1;
    const vReg = regLi > 0 ? raw(ind, regLi, ano) : null;
    const f = fmt(v, ind);
    const fEst = fmt(vEstado, ind);
    const fMed = fmt(st ? st.med : null, ind);

    host.innerHTML = "";
    const head = el("div", "card");
    head.innerHTML = `
      <div class="detail-head">
        <div>
          <span class="badge" style="background:${o.cor}1a;color:${o.cor}">ODS ${o.n} · ${esc(o.nome)}</span>
          <h2>${esc(ind.gcurto)}</h2>
          <p class="sub">${esc(ind.medida)}${tag(ind) ? ` · <b>${esc(tag(ind))}</b>` : ""}</p>
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
    const st2 = stats(ind, ano);
    const split = el("div", "split");
    host.appendChild(split);
    const cardRank = el("div", "card");
    cardRank.innerHTML = `<div class="card-head"><h3>Ranking · ${ano}</h3>
        <div class="rank-modos" role="group" aria-label="Trecho do ranking">
          <button data-rmodo="perto" class="${state.rankModo === "perto" ? "on" : ""}">Ao redor</button>
          <button data-rmodo="top" class="${state.rankModo === "top" ? "on" : ""}">Top 10</button>
          <button data-rmodo="bottom" class="${state.rankModo === "bottom" ? "on" : ""}">Bottom 10</button>
        </div>
      </div><div id="rank"></div>`;
    split.appendChild(cardRank);
    const cardMap = el("div", "card");
    cardMap.innerHTML = `<div class="card-head"><h3>Distribuição no Paraná</h3></div><div id="mapa-det"><div class="empty">…</div></div>
      <div class="legend"><span>${ind.pol === 0 ? "menor" : "pior"}</span><span class="ramp"></span><span>${ind.pol === 0 ? "maior" : "melhor"}</span><span class="nd"><i></i>sem dado</span></div>
      <div style="font-size:11px;color:var(--muted);margin-top:8px">Cor = quintil do valor entre os municípios com dado (${st2 ? st2.n : 0}). Cinza = sem dado (diferente de zero).</div>`;
    split.appendChild(cardMap);

    // ranking
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
      let janela, titulo;
      if (state.rankModo === "top") {
        janela = todos.slice(0, 10);
        titulo = `Os 10 melhores entre ${todos.length} municípios com dado.`;
      } else if (state.rankModo === "bottom") {
        janela = todos.slice(-10).reverse();
        titulo = `Os 10 piores entre ${todos.length} municípios com dado.`;
      } else {
        const ini = iEu >= 0 ? Math.max(0, iEu - 4) : 0;
        janela = todos.slice(ini, ini + (iEu >= 0 ? 9 : 8));
        titulo = iEu >= 0
          ? `${loc.n} está na ${posicoes[iEu]}ª posição de ${todos.length}${ind.tipo === "contagem" ? " em volume" : ""}.`
          : `${loc.n} sem dado neste ano.`;
      }
      // escala na janela exibida, com folga para as diferenças ficarem legíveis
      const vmax = Math.max(...janela.map((x) => x.v));
      const vmin = Math.min(...janela.map((x) => x.v));
      const span = (vmax - vmin) || Math.abs(vmax) * 0.1 || 1;
      const escala = (v) => 10 + 88 * ((v - (vmin - span * 0.15)) / (span * 1.25));
      const row = (x) => {
        const p = posicoes[todos.indexOf(x)];
        return `<div class="rank-row ${x.li === li ? "me" : ""}">
          <span class="rk">${p}º</span>
          <span class="nm">${esc(LOC[x.li].n)}</span>
          <span class="bar"><i style="width:${escala(x.v)}%" class="${x.li === li ? "me" : ""}"></i></span>
          <span class="vl">${fmt(x.v, ind).t}</span>
        </div>`;
      };
      rkHost.innerHTML =
        `<div style="font-size:11px;color:var(--muted);margin-bottom:8px">${esc(titulo)}` +
        (st2.empateFrac > 0.3 ? ` Atenção: ${st2.maiorEmpate} municípios compartilham o mesmo valor — empates dividem a colocação.` : "") +
        (st2.n < MUN.length ? ` <br>${MUN.length - st2.n} municípios sem dado neste ano.` : "") +
        `</div>` +
        janela.map(row).join("");
    }
    $$(".rank-modos button", host).forEach((b) => b.addEventListener("click", () => {
      state.rankModo = b.dataset.rmodo;
      renderDetalhe();
    }));
    pintarMapa($("#mapa-det"), ind, ano, li);
    ligarMapa($("#mapa-det"));

    // sobre
    const cardMeta = el("div", "card");
    const popInfo = POP && POP.info ? POP.info : null;
    const anoPop = ind.derivado ? popAnoUsado(ano) : null;
    const popAviso = ind.derivado && anoPop && anoPop !== ano
      ? `<p class="aviso">Denominador do ano <b>${anoPop}</b> (o indicador é de ${ano}).`
        + (popInfo && popInfo.anos_interpolados && popInfo.anos_interpolados.includes(anoPop)
          ? ` Ano ${anoPop} é interpolado pelo IBGE.` : "") + `</p>` : "";
    cardMeta.innerHTML = `
      <div class="card-head"><h3>Sobre o indicador</h3><span style="font-size:11px;color:var(--muted)">código ${esc(ind.codigo || "—")} · id ${esc(ind.id)}</span></div>
      <dl class="meta-grid">
        <div><dt>Unidade</dt><dd>${esc(ind.unidade || "—")}</dd></div>
        <div><dt>Fonte</dt><dd>${esc(ind.fonte || "—")}</dd></div>
        <div><dt>Planilha de origem</dt><dd>${esc(ind.arquivo || "—")}</dd></div>
        <div><dt>Atualizado em</dt><dd>${esc(ind.atualizado_em || "—")}</dd></div>
        <div class="wide"><dt>Fonte oficial</dt><dd>${ind.fonte_publicador
          ? esc(ind.fonte_publicador) +
            (ind.fonte_url ? ` — <a href="${esc(ind.fonte_url)}" target="_blank" rel="noopener">${esc(ind.fonte_url)}</a>` : "")
          : "—"}
          ${ind.fonte_baixado ? `<br><small>espelho local baixado em ${esc(ind.fonte_baixado)}` +
            (ind.fonte_sha ? ` · sha256 ${esc(ind.fonte_sha)}…` : "") + "</small>" : ""}
          ${ind.fonte_id ? `<br><small>fonte ${esc(ind.fonte_id)} no registro de fontes</small>` : ""}
        </dd></div>
        <div><dt>Municípios com dado</dt><dd>${st2 ? st2.n + " de " + MUN.length : "—"} (no ano ${ano})</dd></div>
        <div><dt>Valores distintos</dt><dd>${st2 ? st2.distintos : "—"}</dd></div>
        <div class="wide"><dt>Definição</dt><dd>${esc(ind.definicao || "—")}</dd></div>
        <div class="wide"><dt>Fórmula</dt><dd>${esc(ind.formula || "—")}</dd></div>
        ${ind.derivado ? `<div class="wide"><dt>Valor calculado</dt><dd>Total do indicador ÷ população residente (IBGE) × 100.000. Não é um dado oficial: é uma taxa derivada para comparar municípios de portes diferentes.${ind.proporcional_motivo ? " Elegível porque " + esc(ind.proporcional_motivo) + "." : ""}</dd></div>` : ""}
      </dl>${popAviso}`;
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
        return `<tr><td>${a}</td><td>${fmt(raw(ind, li, a), ind).t}</td><td>${rl === null ? "—" : fmt(rl, ind).t}</td><td>${fmt(raw(ind, LOC_ID.estado, a), ind).t}</td><td>${s ? fmt(s.med, ind).t : "—"}</td></tr>`;
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
  const POL_KEY = "painelods.pol.v2";   // v2: chaves = nome da coluna de origem (estáveis)
  const POL_KEY_ANTIGO = "painelods.pol.v1"; // v1: ids posicionais (obsoleto — ignorado)

  function polSalva() {
    try { return JSON.parse(window.localStorage.getItem(POL_KEY) || "{}"); } catch (e) { return {}; }
  }

  function gravarPol(obj) {
    try { window.localStorage.setItem(POL_KEY, JSON.stringify(obj)); } catch (e) { /* file:// bloqueado: segue só na sessão */ }
  }

  // aplica as escolhas do revisor sobre a proposta automática do gerador
  // (chave = nome da coluna de origem: estável entre versões da base)
  function aplicarPolaridade() {
    const salvo = polSalva();
    INDS.forEach((i) => {
      if (i.polAuto === undefined) i.polAuto = i.pol;
    });
    const desconhecidas = [];
    Object.keys(salvo).forEach((chave) => {
      const ind = INDS.find((x) => x.chave === chave);
      if (ind) { ind.pol = salvo[chave]; ind.polRevisado = true; }
      else desconhecidas.push(chave);
    });
    if (desconhecidas.length) {
      console.warn("polaridade.json: " + desconhecidas.length +
        " chave(s) não encontrada(s) na base atual (ignoradas):", desconhecidas.slice(0, 3));
    }
    return desconhecidas;
  }

  function definirPolaridade(chave, valor) {
    const ind = INDS.find((x) => x.chave === chave);
    if (!ind) return;
    const salvo = polSalva();
    if (valor === ind.polAuto) { delete salvo[chave]; ind.polRevisado = false; }
    else { salvo[chave] = valor; ind.polRevisado = true; }
    ind.pol = valor;
    gravarPol(salvo);
    C.limparCache();
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
        const desconhecidas = Object.keys(obj).filter((c) => !INDS.some((i) => i.chave === c));
        const saida = {
          _meta: {
            descricao: "Revisão de polaridade do Painel ODS. As chaves são os nomes das colunas de origem (estáveis entre versões da base).",
            build: (EN.build && EN.build.id) || null,
            regras: (EN.build && EN.build.regras) || null,
            exportado_em: new Date().toISOString().slice(0, 19).replace("T", " "),
            n_alteracoes: Object.keys(obj).length,
            chaves_desconhecidas: desconhecidas,
          },
          polaridade: obj,
        };
        const txt = JSON.stringify(saida, null, 2);
        try { if (navigator.clipboard) navigator.clipboard.writeText(txt); } catch (e) { /* segue para o download */ }
        try {
          const a = document.createElement("a");
          a.href = "data:application/json;charset=utf-8," + encodeURIComponent(txt);
          a.download = "polaridade.json";
          a.click();
        } catch (e) { /* sem download disponível */ }
        $("#rev-export").textContent = "Exportado (" + Object.keys(obj).length + " alterações)";
        setTimeout(() => { $("#rev-export").textContent = "Exportar JSON das alterações"; }, 2000);
      });
      $("#rev-clear").addEventListener("click", () => {
        gravarPol({});
        INDS.forEach((i) => { i.pol = i.polAuto; i.polRevisado = false; });
        C.limparCache();
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
      const rec = i.recorte && i.recorte !== "Total" ? " · " + esc(i.recorte) : "";
      const botoes = [-1, 0, 1].map((v) => `<button data-chave="${esc(i.chave)}" data-v="${v}" class="${i.pol === v ? "on p" + v : ""}" title="${i.pol === v ? "selecionado" : "definir como " + POL_TXT[v]}">${POL_TXT[v]}</button>`).join("");
      const consequencia = i.pol === 0
        ? "sem juízo: fica no mapa, mas fora do ranking e das sínteses"
        : (i.tipo === "percentual" || i.tipo === "taxa")
          ? "entra no ranking, no mapa e nas sínteses"
          : "volume absoluto: fora do ranking e das sínteses";
      return `<div class="rev-row">
        <div class="rev-nome">
          <b>${esc(i.gcurto)}</b>${rec}
          <small title="${esc(i.grupo)} · ${esc(i.medida)}">${esc(i.medida)}</small>
          <span class="rev-meta">ODS ${i.ods} · ${esc(i.tipo)}${i.unidade ? " · " + esc(i.unidade) : ""} · ${esc(consequencia)}</span>
          <span class="rev-motivo" title="Justificativa da proposta automática">proposta: ${esc(i.pol_motivo || "—")}</span>
        </div>
        <div class="rev-pol">${botoes}<span class="rev-tag ${i.polRevisado ? "ok" : ""}">${i.polRevisado ? "revisado" : "auto"}</span></div>
      </div>`;
    }).join("");

    $$("#rev-lista .rev-pol button").forEach((b) =>
      b.addEventListener("click", () => definirPolaridade(b.dataset.chave, +b.dataset.v)));
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
    const opcao = (i) => `<option value="${esc(i.id)}">${esc(i.gcurto)} — ${esc(i.medida)}${i.recorte && i.recorte !== "Total" ? " (" + esc(i.recorte) + ")" : ""}</option>`;
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
        <span>${esc(LOC[li].n)}</span><b>${f.t}</b>
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
    $$(".tabs button").forEach((b) => {
      const ativo = b.dataset.view === v;
      b.classList.toggle("active", ativo);
      b.setAttribute("aria-selected", ativo ? "true" : "false");
    });
    $$(".view").forEach((s) => s.classList.toggle("active", s.id === "view-" + v));
    // o ano global só faz sentido nas visões de exploração e comparação
    marcarAnoGlobal();
    render();
    salvarHash();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function render() {
    if (state.view === "geral") renderGeral();
    if (state.view === "explorador") { renderFiltroOds(); renderDetalhe(); renderListaInd(); }
    if (state.view === "comparador") renderComparador();
    if (state.view === "revisao") renderRevisao();
    renderRodape();
  }

  /* ---------------------------------------------- estado compartilhável (URL) */
  function salvarHash() {
    const p = new URLSearchParams();
    p.set("v", state.view);
    if (LOC[state.local]) p.set("m", LOC[state.local].n);
    if (state.indId) p.set("i", state.indId);
    if (state.ano) p.set("a", state.ano);
    if (state.modo !== "absoluto") p.set("modo", state.modo);
    const novo = "#" + p.toString();
    if (window.location.hash !== novo) {
      try { history.replaceState(null, "", novo); } catch (e) { window.location.hash = novo; }
    }
  }

  function lerHash() {
    const s = new URLSearchParams((window.location.hash || "").replace(/^#/, ""));
    if (!s.size) return;
    const v = s.get("v");
    if (v && ["geral", "explorador", "comparador", "revisao"].includes(v)) state.view = v;
    const m = s.get("m");
    if (m) {
      const i = LOC_ID.municipio(m);
      if (i >= 0) state.local = i;
    }
    const i = s.get("i");
    if (i && INDS.some((x) => x.id === i)) state.indId = i;
    const a = s.get("a");
    if (a && +a > 1900) state.ano = +a;
    const modo = s.get("modo");
    if (modo === "proporcional" || modo === "absoluto") state.modo = modo;
  }

  /* --------------------------------------------------------------- rodapé */
  function renderRodape() {
    const rodape = $("#rodape");
    if (!rodape) return;
    const b = EN.build || {};
    const pop = POP && POP.info ? POP.info : null;
    const fs = EN.fontes || null;
    const aviso = fs && (fs.pendentes || fs.urls_quebradas)
      ? `<span class="rodape-alerta">⚠ ${fs.pendentes || 0} fonte(s) oficial(is) aguardando nova edição` +
        `${fs.urls_quebradas ? " · " + fs.urls_quebradas + " com URL alterada" : ""} — ver data/FONTES.md</span>`
      : `<span>Fontes oficiais: ${fs ? fs.total : "—"} registradas, todas em dia</span>`;
    rodape.innerHTML =
      `<span>Base gerada em <b>${esc(b.gerado_em || EN.indice.gerado || "—")}</b> · build <code>${esc(b.id || "—")}</code>` +
      `${b.regras ? " · regras " + esc(b.regras) : ""}</span>` +
      `<span>${INDS.length} indicadores · ${MUN.length} municípios · dados do IBGE (Censos 2010 e 2022, estimativas)</span>` +
      (pop && pop.anos_interpolados && pop.anos_interpolados.length
        ? `<span>População interpolada pelo IBGE em ${pop.anos_interpolados.join(", ")}</span>` : "") +
      aviso +
      `<span><a href="DECISOES.md" target="_blank">Metodologia e decisões</a> · <a href="DATA_SCHEMA.md" target="_blank">Dicionário de dados</a> · <a href="data/FONTES.md" target="_blank">Fontes oficiais</a> · <a href="data/CONVERGENCIA.md" target="_blank">Convergência com o IDSC</a></span>`;
  }

  /* ---------------------------------------------------------- init */
  function init() {
    // integridade do payload: sem isso, não se renderiza nada
    if (!checarIntegridade()) return;

    // polaridade revisada pelo usuário (localStorage) sobre a proposta automática
    aplicarPolaridade();

    // estado vindo da URL (link compartilhável)
    lerHash();

    // ano global
    const anos = Array.from(new Set(INDS.flatMap((i) => i.anos))).sort((a, b) => b - a);
    const selAno = $("#sel-ano");
    selAno.innerHTML = anos.map((a) => `<option ${a === state.ano ? "selected" : ""}>${a}</option>`).join("");
    selAno.addEventListener("change", () => { state.ano = +selAno.value; state.cmpAno = null; render(); salvarHash(); });

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

    // imprimir
    const btnImp = $("#btn-imprimir");
    if (btnImp) btnImp.addEventListener("click", () => window.print());

    // explorador
    $("#busca-ind").addEventListener("input", (e) => { state.busca = e.target.value; renderListaInd(); });

    // comparador default: município + estado + RGInt do município
    const g = LOC_ID.municipio("Guarapuava");
    const r = LOC_ID.rgint(LOC[g] ? LOC[g].reg : "");
    state.cmp = [g, LOC_ID.estado, r].filter((x) => x >= 0);

    // mapa: tooltip e clique para focar
    ligarMapa($("#mapa"));

    // resize
    let t = null;
    window.addEventListener("resize", () => {
      clearTimeout(t);
      t = setTimeout(() => { if (state.view === "explorador") renderDetalhe(); if (state.view === "comparador") renderComparador(); }, 180);
    });

    // aplica a visão vinda da URL
    const v0 = state.view;
    state.view = "geral";
    irPara(v0);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
