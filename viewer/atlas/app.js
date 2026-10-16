/* SuperPOD Fabric Atlas — UI. All numbers come from Atlas.configure() (engine.js); this file
 * only renders them, keeps per-viewer UI state, and wires the optional runtime capabilities
 * (db: shared scenarios, downloads: file exports, user: who may save). */
(() => {
  "use strict";
  const { PROFILES, ORDER, RA } = window.ATLAS;
  const Atlas = window.Atlas;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n, d = 0) => (n == null || !isFinite(n) ? "—" : Number(n).toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: d }));
  const kw = (v) => (v >= 1000 ? `${fmt(v / 1000, 2)} MW` : `${fmt(v, 1)} kW`);
  const store = { get(k, d) { try { const v = localStorage.getItem("atlas." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
                  set(k, v) { try { localStorage.setItem("atlas." + k, JSON.stringify(v)); } catch { /* storage unavailable */ } } };
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const TABS = [["overview", "Overview"], ["topology", "Topology"], ["racks", "Racks"], ["bom", "Bill of materials"],
                ["power", "Power & cooling"], ["compliance", "Compliance"], ["proposal", "Proposal"], ["asbuilt", "As built (NetBox)"]];
  const FAB = { compute: "Compute IB", storage: "Storage IB", "storage-eth": "Storage Ethernet", inband: "In-band", oob: "Out-of-band", nvlink: "NVLink", mgmt: "Management" };
  const COOL = [["auto", "RA default"], ["air", "Air"], ["air-rdhx", "Air + RDHx"], ["liquid", "Liquid (DLC)"]];
  const WORK = [["training", "Training"], ["mixed", "Mixed"], ["inference", "Inference"]];

  /** Shared scenarios and stored state are untrusted: keep only known keys with sane values. */
  function sanitize(x) {
    const c = Object.assign({}, Atlas.DEFAULTS);
    if (!x || typeof x !== "object") return c;
    if (PROFILES[x.gen]) c.gen = x.gen;
    const n = (v, lo, hi) => (v === null || v === "" || !isFinite(+v) ? null : Math.min(hi, Math.max(lo, +v)));
    c.sus = n(x.sus, 1, 64) ?? c.sus; c.populated = n(x.populated, 1, 100000); c.density = n(x.density, 1, 6);
    c.pue = n(x.pue, 1, 3);
    if (COOL.some(([k]) => k === x.cooling)) c.cooling = x.cooling;
    if (WORK.some(([k]) => k === x.workload)) c.workload = x.workload;
    if (typeof x.storageTier === "string") c.storageTier = x.storageTier.slice(0, 20);
    if (x.taper === "2:1") c.taper = "2:1";
    for (const k of ["preparedFor", "preparedBy", "site"]) if (typeof x[k] === "string") c[k] = x[k].slice(0, 120);
    return c;
  }
  let cfg = sanitize(store.get("cfg", {}));
  let tab = (location.hash || "").slice(1);
  if (!TABS.some(([k]) => k === tab)) tab = store.get("tab", "overview");
  let view = store.get("view", "compute");
  let R = null, cy = null, cy2 = null, signoff = store.get("signoff", {});
  const caps = { db: null, downloads: null, user: null, canWrite: false, scenarios: [] };

  // ------------------------------------------------------------------ helpers
  function toast(msg) {
    const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
    setTimeout(() => t.remove(), 2400);
  }
  const coolPill = (p) => p.coolingNative === "liquid" ? `<span class="pill liquid">liquid</span>` : p.coolingRecommended === "air-rdhx" ? `<span class="pill rdhx">air + RDHx</span>` : `<span class="pill air">air</span>`;
  const srcPill = (s) => `<span class="src ${esc(s)}">${esc(s)}</span>`;
  const unit = (p) => (p.family === "nvl72" ? "NVL72 racks" : "systems");
  const suSizes = (p) => (p.family === "nvl72" ? [1, 2, 4, 8, 16] : Object.keys(p.su.table).concat(Object.keys(p.su.beyond || {})).map(Number).sort((a, b) => a - b));

  function update(patch) {
    Object.assign(cfg, patch);
    store.set("cfg", cfg);
    render();
  }

  // ------------------------------------------------------------------ rail
  function renderRail() {
    const p = PROFILES[cfg.gen];
    const gens = ORDER.map((id) => {
      const g = PROFILES[id], s = g.system;
      const spec = g.family === "nvl72" ? `${s.trays} trays · ${s.gpus} GPU/rack · ${s.rackKw} kW/rack` : `${s.gpus} GPU · ${s.u}U · ${s.kw} kW · ${s.memGB ? fmt(s.memGB) + " GB" : ""}`;
      return `<button type="button" class="gen" aria-pressed="${id === cfg.gen}" data-gen="${id}">
        <span class="n">${esc(g.label)}</span>${coolPill(g)}
        <span class="m">${esc(g.arch)} · ${esc(spec)}</span></button>`;
    }).join("");
    const sizes = suSizes(p);
    const tiers = p.perf.tiers;
    const dens = p.family === "hgx" ? Object.keys(p.density.options).map(Number) : [];
    $("rail").innerHTML = `
      <div class="card"><h2>System generation</h2><div class="gens" id="gens">${gens}</div>
        <div class="hint">Reference: <a href="${esc(p.ra.url)}" target="_blank" rel="noopener">${esc(p.ra.doc)}</a> (${esc(p.ra.date)})</div></div>
      <div class="card"><h2>Scale</h2>
        <div class="row"><label for="sus">Scalable units</label>
          <span class="stepper"><button type="button" data-step="-1" aria-label="Fewer SUs">−</button><input id="sus" class="num" inputmode="numeric" value="${cfg.sus}" aria-label="Scalable units"><button type="button" data-step="1" aria-label="More SUs">+</button></span></div>
        <div class="chips" aria-label="Sizes in the RA tables">${sizes.map((s) => `<button type="button" data-sus="${s}" aria-pressed="${s === cfg.sus}">${s} SU</button>`).join("")}</div>
        <div class="hint">One SU = ${p.family === "nvl72" ? `${p.racksPerSU} NVL72 racks (${p.racksPerSU * p.system.gpus} GPUs)` : `${p.su.systems} systems (${p.su.systems * 8} GPUs)`}. Chips are the sizes printed in the RA.</div>
        <div class="row"><label for="pop">Populate only</label><input id="pop" class="inp num" style="width:9ch" inputmode="numeric" placeholder="all" value="${cfg.populated ?? ""}" aria-label="Populate only this many ${p.family === "nvl72" ? "GPUs" : "systems"}"><span class="hint">${p.family === "nvl72" ? "GPUs" : "systems"} (fabric stays full)</span></div>
      </div>
      <div class="card"><h2>Cooling</h2>
        <div class="seg" id="cool">${COOL.map(([k, l]) => `<button type="button" data-cool="${k}" aria-pressed="${cfg.cooling === k}">${l}</button>`).join("")}</div>
        <div class="hint">${p.coolingNative === "liquid" ? "NVL72 is hybrid: GPUs and CPUs on direct liquid cooling, the rest on air." : p.coolingRecommended === "air-rdhx" ? "Air-cooled system; NVIDIA recommends active rear-door heat exchangers at 4 per rack." : "Air-cooled system. Liquid is not a DGX option for this generation."}</div></div>
      <div class="card"><h2>Workload focus</h2>
        <div class="seg" id="work">${WORK.map(([k, l]) => `<button type="button" data-work="${k}" aria-pressed="${cfg.workload === k}">${l}</button>`).join("")}</div>
        <div class="hint">Sets the storage tier and the fabric options offered. The RA itself is written for training.</div></div>
      <div class="card"><details class="adv" ${store.get("advOpen", false) ? "open" : ""} id="adv"><summary>Deviations and assumptions</summary>
        <div class="row"><label for="tier">Storage tier</label><select id="tier" class="sel"><option value="auto">Auto (${esc(R ? R.workload.recommended : "")})</option>${tiers.map((t) => `<option value="${t}" ${cfg.storageTier === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
        ${p.family === "hgx" ? `<div class="row"><label for="dens">Systems / rack</label><select id="dens" class="sel"><option value="">RA (${p.density.def})</option>${[1, 2, 3, 4, 5, 6].filter((d) => d !== p.density.def).map((d) => `<option value="${d}" ${+cfg.density === d ? "selected" : ""}>${d}${d > 4 ? " — not supported" : dens.includes(d) ? " — documented" : " — non-RA"}</option>`).join("")}</select></div>` : ""}
        <div class="row"><label for="taper">Compute fabric</label><select id="taper" class="sel"><option value="none">Non-blocking (RA)</option><option value="2:1" ${cfg.taper === "2:1" ? "selected" : ""}>Tapered 2:1 (non-RA)</option></select></div>
        <div class="row"><label for="pue">Facility PUE</label><input id="pue" class="inp num" style="width:7ch" inputmode="decimal" placeholder="auto" value="${cfg.pue ?? ""}"></div>
        <div class="row"><label for="pfor">Prepared for</label><input id="pfor" class="inp" style="flex:1" placeholder="Name or team" value="${esc(cfg.preparedFor)}"></div>
        <div class="row"><label for="by">Prepared by</label><input id="by" class="inp" style="flex:1" placeholder="Your name" value="${esc(cfg.preparedBy)}"></div>
        <div class="row"><label for="site">Site</label><input id="site" class="inp" style="flex:1" placeholder="Data centre / location" value="${esc(cfg.site)}"></div>
        <button type="button" class="btn" id="reset">Reset to RA defaults</button>
      </details></div>`;
  }

  function wireRail() {
    const rail = $("rail");
    rail.onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.gen) { const g = PROFILES[b.dataset.gen]; const s = suSizes(g); update({ gen: b.dataset.gen, sus: s.includes(cfg.sus) ? cfg.sus : s[0], density: null, storageTier: "auto", populated: null }); }
      else if (b.dataset.sus) update({ sus: +b.dataset.sus });
      else if (b.dataset.step) update({ sus: Math.max(1, Math.min(64, cfg.sus + +b.dataset.step)) });
      else if (b.dataset.cool) update({ cooling: b.dataset.cool });
      else if (b.dataset.work) update({ workload: b.dataset.work, storageTier: "auto" });
      else if (b.id === "reset") update({ cooling: "auto", storageTier: "auto", density: null, taper: "none", pue: null, populated: null });
    };
    rail.onchange = (e) => {
      const t = e.target, v = t.value.trim();
      const num = (x) => (x === "" ? null : Number(x));
      if (t.id === "sus") update({ sus: Math.max(1, Math.min(64, parseInt(v) || 1)) });
      if (t.id === "pop") update({ populated: v === "" ? null : Math.max(1, parseInt(v) || 1) });
      if (t.id === "tier") update({ storageTier: v });
      if (t.id === "dens") update({ density: num(v) });
      if (t.id === "taper") update({ taper: v });
      if (t.id === "pue") update({ pue: v === "" ? null : Math.max(1, Number(v) || 1) });
      if (t.id === "pfor") update({ preparedFor: v });
      if (t.id === "by") update({ preparedBy: v });
      if (t.id === "site") update({ site: v });
    };
    rail.addEventListener("toggle", (e) => { if (e.target.id === "adv") store.set("advOpen", e.target.open); }, true);
  }

  // ------------------------------------------------------------------ counters
  function renderCounters() {
    const c = R.counts, p = R.profile;
    const items = [
      ["GPUs", fmt(c.gpus), `${esc(p.system.gpu)}`],
      [p.family === "nvl72" ? "NVL72 racks" : "Systems", fmt(c.systems), p.family === "nvl72" ? `${fmt(c.trays)} compute trays` : `${c.sus} SU · ${fmt(c.racks.perRack)} per rack`],
      ["GPU memory", c.gpuMemTB ? `${fmt(c.gpuMemTB, 1)} TB` : "—", c.gpuMemTB ? "HBM total" : "not in RA"],
      ["Switches", fmt(c.switches), `${fmt(c.compute.leaves)} leaf · ${fmt(c.compute.spines)} spine${c.compute.core ? ` · ${c.compute.core} core` : ""}`],
      ["Cables", fmt(c.cablesTotal), `${fmt(c.transceivers)} optics`],
      ["Racks", fmt(c.racksTotal), `${fmt(c.racks.compute)} compute · ${fmt(c.racks.mgmt)} network`],
      ["IT load", kw(R.power.itKw), `${kw(c.racks.rackKw)} per compute rack`],
      ["Facility", kw(R.power.facilityKw), `PUE ${R.power.pue}${R.power.pueSrc === "assumption" ? " (assumed)" : ""}`],
    ];
    $("counters").innerHTML = items.map(([k, v, d]) => `<div class="ctr"><span class="k">${k}</span><span class="v num">${v}</span><span class="d">${d}</span></div>`).join("") +
      `<div class="ctr flags"><span class="k">Review</span><span class="v num"><span class="sev-b" title="blockers">${c.flags.blocker}</span><span class="sev-a" title="need approval">${c.flags.approval}</span><span class="sev-i" title="notes">${c.flags.info}</span></span><span class="d">blockers · approvals · notes</span></div>`;
    $("subline").textContent = `${p.label} · ${c.sus} SU · ${WORK.find(([k]) => k === cfg.workload)[1]}${cfg.preparedFor ? " · for " + cfg.preparedFor : ""}`;
  }

  function renderTabs() {
    const c = R.counts.flags;
    $("tabs").innerHTML = TABS.map(([k, l]) => {
      const badge = k === "compliance" && (c.blocker || c.approval) ? `<span class="badge ${c.blocker ? "b" : ""}">${c.blocker + c.approval}</span>` : "";
      return `<button type="button" role="tab" aria-selected="${k === tab}" data-tab="${k}" id="tab-${k}">${l}${badge}</button>`;
    }).join("");
  }
  $("tabs").onclick = (e) => { const b = e.target.closest("[data-tab]"); if (!b) return; tab = b.dataset.tab; store.set("tab", tab); history.replaceState(null, "", "#" + tab); renderTabs(); renderPane(); };

  // ------------------------------------------------------------------ panes
  function renderPane() {
    const f = { overview, topology, racks, bom, power, compliance, proposal, asbuilt }[tab];
    $("pane").setAttribute("aria-labelledby", "tab-" + tab);
    f();
  }

  function statement() {
    const p = R.profile, c = R.counts;
    const what = p.family === "nvl72" ? `${fmt(c.systems)} ${p.label} racks (${fmt(c.trays)} compute trays)` : `${fmt(c.systems)} ${p.label} systems`;
    return `A <b>${c.sus}-SU ${esc(p.label)} SuperPOD</b> with <b>${fmt(c.gpus)} GPUs</b> in ${what}, built for <b>${esc(cfg.workload)}</b>. It draws about <b>${kw(R.power.itKw)}</b> of IT load (${kw(R.power.facilityKw)} at the facility), in ${fmt(c.racksTotal)} racks, cooled by <b>${esc(R.cooling.mode.toLowerCase())}</b>.`;
  }

  function overview() {
    const p = R.profile, c = R.counts, s = p.system;
    const spec = p.family === "nvl72"
      ? [["System", p.label], ["Per rack", `${s.trays} compute trays × ${s.gpusPerTray} GPU, ${s.nvsTrays} NVLink switch trays, ${s.shelves} × ${s.shelfKw} kW power shelves`], ["GPU", s.gpu], ["Networking", s.nics], ["Rack power", `${s.rackKw} kW${s.rackKwSrc === "choice" ? " (estimate)" : ""}`]]
      : [["System", p.label], ["GPU", `${s.gpus} × ${s.gpu}`], ["GPU memory", s.memGB ? `${fmt(s.memGB)} GB per system` : "—"], ["Height / power", `${s.u}U · ${s.peakNote}`], ["Networking", s.nics], ["Power supply", s.psu]];
    const fab = [["Compute fabric", p.compute.tech], ["Compute switch", p.compute.switch],
      ["Storage", p.family === "hgx" ? p.storage.tech : "Ethernet RoCE (Spectrum-4) via BlueField-3"],
      ["In-band", p.family === "hgx" ? `${p.inband.tech} · ${p.inband.switch}` : `Spectrum-4 ${p.ethernet.switch.replace("NVIDIA ", "")}`],
      ["Out-of-band", p.oob.switch], ["Fabric manager", p.ufm.model]];
    const dl = (rows) => `<dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
    const top = R.flags.filter((f) => f.sev !== "info").slice(0, 4);
    $("pane").innerHTML = `
      <div class="card"><p class="statement">${statement()}</p></div>
      <div class="grid2">
        <div class="card"><h2>System</h2>${dl(spec)}</div>
        <div class="card"><h2>Fabrics</h2>${dl(fab)}</div>
        <div class="card"><h2>Workload fit — ${esc(cfg.workload)}</h2><ul class="notes">${R.workload.notes.map((n) => `<li>${srcPill(n.src)}<span>${esc(n.text)}</span></li>`).join("")}</ul></div>
        <div class="card"><h2>Needs attention</h2>${top.length ? top.map(flagHTML).join("") : `<p class="hint">No blockers or approvals: this configuration follows the reference architecture. ${c.flags.info} notes are listed under Compliance.</p>`}</div>
      </div>
      <div class="card"><h2>Across generations — same GPU target (≥ ${fmt(c.gpus)} GPUs)</h2>${compareTable()}
        <p class="hint">Each row is the smallest RA size of that generation reaching the current GPU count, with the same workload and its default cooling. Click a row to switch.</p></div>`;
    $("pane").querySelector("#cmp")?.addEventListener("click", (e) => { const tr = e.target.closest("tr[data-gen]"); if (tr) { const g = tr.dataset.gen; update({ gen: g, sus: +tr.dataset.sus, density: null, storageTier: "auto", populated: null, cooling: "auto" }); } });
  }

  function compareTable() {
    const target = R.counts.gpus;
    const rows = ORDER.map((id) => {
      const p = PROFILES[id];
      let best = null;
      for (const s of suSizes(p)) {
        if (best && s >= best.cfg.sus) continue;
        try { const r = Atlas.configure({ gen: id, sus: s, workload: cfg.workload }); if (r.counts.gpus >= target && (!best || s < best.cfg.sus)) best = r; } catch { /* skip */ }
      }
      return best;
    }).filter(Boolean);
    return `<div class="tablewrap"><table class="t" id="cmp"><thead><tr><th>Generation</th><th>Cooling</th><th class="n">SUs</th><th class="n">GPUs</th><th class="n">Systems</th><th class="n">Racks</th><th class="n">Switches</th><th class="n">Cables</th><th class="n">IT load</th><th class="n">kW / GPU</th><th class="n">Review</th></tr></thead><tbody>${
      rows.map((r) => `<tr data-gen="${r.profile.id}" data-sus="${r.cfg.sus}" class="${r.profile.id === cfg.gen ? "cur" : ""}" style="cursor:pointer"><td><b>${esc(r.profile.label)}</b><div class="ref">${esc(r.profile.ra.doc)}</div></td><td>${coolPill(r.profile)}</td><td class="n">${r.cfg.sus}</td><td class="n">${fmt(r.counts.gpus)}</td><td class="n">${fmt(r.counts.systems)}</td><td class="n">${fmt(r.counts.racksTotal)}</td><td class="n">${fmt(r.counts.switches)}</td><td class="n">${fmt(r.counts.cablesTotal)}</td><td class="n">${kw(r.power.itKw)}</td><td class="n">${fmt(r.power.itKw / r.counts.gpus, 2)}</td><td class="n"><span class="sev-b">${r.counts.flags.blocker}</span> · <span class="sev-a">${r.counts.flags.approval}</span></td></tr>`).join("")
    }</tbody></table></div>`;
  }

  // ------------------------------------------------------------------ topology
  function topology() {
    const views = Object.keys(R.graph);
    if (!views.includes(view)) view = views[0];
    const g = R.graph[view];
    const fabs = [...new Set(g.edges.map((e) => e.f))];
    $("pane").innerHTML = `
      <div class="row"><div class="seg" id="views">${views.map((v) => `<button type="button" data-view="${v}" aria-pressed="${v === view}">${esc(R.graph[v].title)}</button>`).join("")}</div>
        <div class="legend">${fabs.map((f) => `<span><i class="sw" style="background:${css("--f-" + f)}"></i>${FAB[f] || f}</span>`).join("")}<span>line width ∝ cable count</span></div></div>
      <div class="topo"><div class="stage"><div id="cy" aria-label="Topology diagram"></div></div>
        <div class="card insp" id="insp"><h2>Inspector</h2><p class="hint">Tiers read top-down like NVIDIA Air: core, spines, leaves, systems. Click a node or link for its cable count. Grouped nodes stand for many devices (×n).</p>${topoSummary(g)}</div></div>`;
    $("views").onclick = (e) => { const b = e.target.closest("[data-view]"); if (b) { view = b.dataset.view; store.set("view", view); topology(); } };
    drawGraph(g);
  }

  function topoSummary(g) {
    const byKind = {};
    for (const n of g.nodes) byKind[n.kind] = (byKind[n.kind] || 0) + (n.count || 1);
    const cables = g.edges.reduce((a, e) => a + e.n, 0);
    return `<div>${Object.entries(byKind).map(([k, v]) => `<div class="row2"><span>${esc(k)}</span><b class="num">${fmt(v)}</b></div>`).join("")}<div class="row2"><span>cables drawn</span><b class="num">${fmt(cables)}</b></div></div>`;
  }

  function drawGraph(g, cyId = "cy", inspId = "insp") {
    if (!window.cytoscape) { $(cyId).innerHTML = `<p class="hint" style="padding:16px">The diagram library did not load. Check the connection and reload.</p>`; return; }
    const rows = new Map();
    for (const n of g.nodes) (rows.get(n.tier) || rows.set(n.tier, []).get(n.tier)).push(n);
    const tiers = [...rows.keys()].sort((a, b) => a - b);
    const widest = Math.max(...[...rows.values()].map((r) => r.length));
    const span = Math.max(760, widest * 84), gap = Math.max(150, span * 0.24);
    const els = [];
    tiers.forEach((t, i) => {
      const r = rows.get(t), step = r.length > 1 ? span / (r.length - 1) : 0;
      r.forEach((n, j) => els.push({ group: "nodes", data: { id: n.id, label: n.label, kind: n.kind, count: n.count || 1 }, classes: n.kind + (n.count > 1 ? " grp" : ""), position: { x: r.length > 1 ? j * step : span / 2, y: i * gap } }));
    });
    const maxN = Math.max(1, ...g.edges.map((e) => e.n || 0));
    g.edges.forEach((e, i) => els.push({ group: "edges", data: { id: "e" + i, source: e.s, target: e.t, n: e.n, f: e.f, w: 1 + 7 * Math.sqrt(Math.max(0, e.n || 0) / maxN) } }));
    const ink = css("--ink"), panel = css("--panel"), muted = css("--muted");
    const style = [
      { selector: "node", style: { label: "data(label)", "text-wrap": "wrap", "text-max-width": 90, "font-size": 10, "font-family": "IBM Plex Mono, monospace", color: ink, "text-valign": "bottom", "text-margin-y": 5,
          "background-color": panel, "border-color": ink, "border-width": 1.5, shape: "round-rectangle", width: 40, height: 20, "min-zoomed-font-size": 6 } },
      { selector: "node.spine, node.core", style: { "background-color": ink, width: 48 } },
      { selector: "node.systems", style: { shape: "barrel", width: 58, height: 32, "background-color": css("--k-system"), "border-color": css("--k-system"), color: ink } },
      { selector: "node.storage", style: { shape: "barrel", "background-color": css("--k-storage"), "border-color": css("--k-storage") } },
      { selector: "node.mgmt", style: { "background-color": css("--k-mgmt"), "border-color": css("--k-mgmt") } },
      { selector: "node.oob", style: { "background-color": css("--k-oob"), "border-color": css("--k-oob") } },
      { selector: "node.grp", style: { "border-width": 3, "border-style": "double" } },
      { selector: "edge", style: { "curve-style": "haystack", "haystack-radius": 0, width: "data(w)", opacity: 0.55 } },
      { selector: ".faded", style: { opacity: 0.07 } }, { selector: "edge.hl", style: { opacity: 0.95 } },
      { selector: "node:selected", style: { "border-color": css("--accent"), "border-width": 3 } },
    ].concat(Object.keys(FAB).map((f) => ({ selector: `edge[f = "${f}"]`, style: { "line-color": css("--f-" + f) || muted } })));
    if (cy) cy.destroy();
    cy = cytoscape({ container: $(cyId), elements: els, layout: { name: "preset" }, style, wheelSensitivity: 0.25, minZoom: 0.05, maxZoom: 4, boxSelectionEnabled: false });
    cy.fit(undefined, 30);
    const insp = $(inspId);
    const show = (ele) => {
      cy.elements().addClass("faded");
      const hood = ele.isNode() ? ele.closedNeighborhood() : ele.union(ele.connectedNodes());
      hood.removeClass("faded"); hood.edges().addClass("hl");
      if (ele.isNode()) {
        const rows = ele.connectedEdges().map((e) => { const o = e.source().id() === ele.id() ? e.target() : e.source(); return [o.data("label").replace("\n", " "), e.data("n"), e.data("f")]; }).sort((a, b) => b[1] - a[1]);
        insp.innerHTML = `<h2>${esc(ele.data("label").replace("\n", " · "))}</h2><p class="hint">${ele.data("count") > 1 ? `stands for ${ele.data("count")} devices · ` : ""}${fmt(rows.reduce((a, r) => a + r[1], 0))} cables</p><div>${rows.map(([l, n, f]) => `<div class="row2"><span><i class="sw" style="background:${css("--f-" + f)}"></i> ${esc(l)}</span><b class="num">${fmt(n)}</b></div>`).join("")}</div>`;
      } else insp.innerHTML = `<h2>${esc(ele.source().data("label").replace("\n", " "))} ↔ ${esc(ele.target().data("label").replace("\n", " "))}</h2><p class="hint">${FAB[ele.data("f")] || ele.data("f")}</p><div class="row2"><span>cables</span><b class="num">${fmt(ele.data("n"))}</b></div>`;
    };
    cy.on("tap", "node, edge", (e) => show(e.target));
    cy.on("tap", (e) => { if (e.target === cy) { cy.elements().removeClass("faded hl"); insp.innerHTML = `<h2>Inspector</h2>${topoSummary(g)}`; } });
  }

  // ------------------------------------------------------------------ racks
  function rackSVG(rk) {
    const U = rk.u || 48, uh = 11, w = 250, left = 34, top = 18, H = U * uh;
    const color = (k) => css("--k-" + k) || css("--muted");
    const parts = [`<svg viewBox="0 0 ${left + w + 16} ${H + top + 22}" width="${left + w + 16}" role="img" aria-label="${esc(rk.title)} elevation">`,
      `<rect x="${left}" y="${top}" width="${w}" height="${H}" fill="${css("--panel-2")}" stroke="${css("--ink")}" stroke-width="2"/>`];
    for (let u = 1; u <= U; u++) {
      const y = top + H - u * uh;
      parts.push(`<line x1="${left}" x2="${left + w}" y1="${y}" y2="${y}" stroke="${css("--grid")}" stroke-width="1"/>`);
      if (u % 2 === 1) parts.push(`<text x="${left - 6}" y="${y + uh - 2}" font-size="8" text-anchor="end" fill="${css("--muted")}" font-family="IBM Plex Mono, monospace">${u}</text>`);
    }
    for (const it of rk.items) {
      const y = top + H - (it.u + it.h - 1) * uh, h = it.h * uh;
      parts.push(`<rect x="${left + 3}" y="${y + 1}" width="${w - 6}" height="${h - 2}" rx="2" fill="${color(it.kind)}" fill-opacity="0.85"/>`);
      if (h >= 10) parts.push(`<text x="${left + w / 2}" y="${y + h / 2 + 3.5}" font-size="${Math.min(10, h - 2)}" text-anchor="middle" fill="${css("--panel")}" font-family="IBM Plex Sans Condensed, Arial, sans-serif" font-weight="600">${esc(it.label)}</text>`);
    }
    parts.push(`<text x="${left}" y="12" font-size="11" fill="${css("--ink")}" font-family="IBM Plex Sans Condensed, Arial, sans-serif" font-weight="600">${U}U</text></svg>`);
    return parts.join("");
  }

  function racks() {
    const c = R.counts;
    const bar = (v, b) => `<div class="bar ${v > b ? "over" : ""}" title="${fmt(v, 1)} of ${fmt(b, 1)} kW"><i style="width:${Math.min(100, (v / b) * 100)}%"></i></div>`;
    $("pane").innerHTML = `
      <div class="grid2">
        <div class="card"><h2>Rack plan</h2><dl class="kv">
          <dt>Compute racks</dt><dd class="num">${fmt(c.racks.compute)} × ${R.profile.family === "nvl72" ? "NVL72" : `${c.racks.perRack} systems`}</dd>
          <dt>Network / mgmt / storage racks</dt><dd class="num">${fmt(c.racks.mgmt)}</dd>
          <dt>Compute rack power</dt><dd class="num">${kw(c.racks.rackKw)} peak · budget ${kw(c.racks.budget)}</dd></dl>
          ${bar(c.racks.rackKw, c.racks.budget)}
          <p class="hint">Budget: ${esc(R.profile.family === "hgx" ? R.profile.density.ref : R.profile.rack.ref)}.</p></div>
        <div class="card"><h2>Floor</h2><dl class="kv"><dt>Rack type</dt><dd>${R.profile.id === "b300e" ? "19-inch MGX racks with 54 V DC busbar" : R.profile.family === "nvl72" ? "NVL72 rack (liquid manifolds)" : "600 × 1200 mm, ≥ 48U (DCG §4)"}</dd><dt>Racks total</dt><dd class="num">${fmt(c.racksTotal)}</dd><dt>Approx. floor (racks only)</dt><dd class="num">${fmt(c.racksTotal * 0.72, 1)} m²</dd></dl>
          <p class="hint">Aisles, ${R.profile.family === "nvl72" ? "CDUs, " : ""}and service clearances are extra.${/InfiniBand/.test(R.profile.compute.tech) ? " The H100 data-centre guide caps any InfiniBand cable path at 50 m; confirm the limit for this generation's optics." : ""}</p></div>
      </div>
      <div class="racks">${R.racks.map((rk) => `<figure class="rackfig card">${rackSVG(rk)}<figcaption class="cap"><b>${esc(rk.title)} × ${fmt(rk.count)}</b><div class="hint">${esc(rk.note)}${rk.kw ? ` · ${kw(rk.kw)}` : ""}</div></figcaption></figure>`).join("")}</div>`;
  }

  // ------------------------------------------------------------------ BOM
  let bomFilter = store.get("bomFilter", "all");
  function bom() {
    const rows = R.bom.filter((b) => bomFilter === "all" || b.src === bomFilter);
    const groups = [...new Set(rows.map((b) => b.group))];
    const srcs = ["all", "RA", "DERIVED", "CHOICE", "NON-RA"];
    const counts = R.counts.bomSrc;
    $("pane").innerHTML = `
      <div class="row"><div class="seg" id="bf">${srcs.map((s) => `<button type="button" data-src="${s}" aria-pressed="${s === bomFilter}">${s === "all" ? "All lines" : s}${s !== "all" ? ` (${counts[s] || 0})` : ""}</button>`).join("")}</div>
        <span class="spacer" style="flex:1"></span>${dlButtons(["csv"])}</div>
      <p class="hint">${srcPill("RA")} stated in the RA · ${srcPill("DERIVED")} computed from RA rules · ${srcPill("CHOICE")} assumption to confirm · ${srcPill("NON-RA")} deviation needing approval</p>
      <div class="tablewrap"><table class="t"><thead><tr><th>Item</th><th>Model</th><th class="n">Qty</th><th>Source</th><th>Reference</th></tr></thead><tbody>${
        groups.map((g) => `<tr class="grp"><td colspan="5">${esc(g)}</td></tr>` + rows.filter((b) => b.group === g).map((b) => `<tr><td>${esc(b.item)}</td><td>${esc(b.model)}</td><td class="n">${fmt(b.qty)}</td><td>${srcPill(b.src)}</td><td class="ref">${esc(b.ref)}</td></tr>`).join("")).join("")
      }</tbody></table></div>`;
    $("bf").onclick = (e) => { const b = e.target.closest("[data-src]"); if (b) { bomFilter = b.dataset.src; store.set("bomFilter", bomFilter); bom(); } };
    wireDownloads();
  }

  // ------------------------------------------------------------------ power
  function power() {
    const cats = {};
    for (const b of R.bom) if (b.w) { const k = b.group === "Compute" ? "Compute" : /Storage/.test(b.group) ? "Storage" : b.group === "Management" ? "Management" : "Networking"; cats[k] = (cats[k] || 0) + (b.w * b.qty) / 1000; }
    const total = Object.values(cats).reduce((a, b) => a + b, 0);
    const colors = { Compute: "--k-system", Networking: "--k-ib", Storage: "--k-storage", Management: "--k-mgmt" };
    let x = 0;
    const segs = Object.entries(cats).map(([k, v]) => { const w = (v / total) * 100; const s = `<rect x="${x}%" width="${w}%" height="28" fill="${css(colors[k])}"><title>${k}: ${kw(v)}</title></rect>`; x += w; return s; }).join("");
    const pw = R.power, co = R.cooling;
    $("pane").innerHTML = `
      <div class="card"><h2>IT load by function — ${kw(total)}</h2>
        <svg width="100%" height="28" role="img" aria-label="IT load split">${segs}</svg>
        <div class="legend">${Object.entries(cats).map(([k, v]) => `<span><i class="sw" style="height:10px;background:${css(colors[k])}"></i>${k} <b class="num">${kw(v)}</b> (${fmt((v / total) * 100, 1)} %)</span>`).join("")}</div>
        <p class="hint">Peak figures: system maximum power from the RA/user guides; switch and server figures from the DCG component table or marked assumptions in the BOM.</p></div>
      <div class="grid2">
        <div class="card"><h2>Facility and energy</h2><dl class="kv">
          <dt>IT load (peak)</dt><dd class="num">${kw(pw.itKw)}</dd>
          <dt>PUE</dt><dd class="num">${pw.pue} ${pw.pueSrc === "assumption" ? srcPill("CHOICE") : ""}</dd>
          <dt>Facility load</dt><dd class="num">${kw(pw.facilityKw)}</dd>
          <dt>Energy per year</dt><dd class="num">${fmt(pw.annualMWh)} MWh (at 100 % load)</dd></dl>
          <p class="hint">An upper bound: AI clusters run near peak during training, but real averages depend on utilisation.</p></div>
        <div class="card"><h2>Cooling</h2><dl class="kv">
          <dt>Mode</dt><dd>${esc(co.mode)}</dd>
          ${co.liquidKw ? `<dt>To liquid</dt><dd class="num">${kw(co.liquidKw)} ${srcPill("CHOICE")}</dd>` : ""}
          <dt>To air</dt><dd class="num">${kw(co.airKw)}</dd>
          ${co.cfm ? `<dt>Airflow</dt><dd class="num">${fmt(co.cfm)} CFM (${co.cfmPerKw} CFM/kW, ${esc(co.cfmRef)})</dd>` : ""}
          <dt>Compute rack density</dt><dd class="num">${kw(R.counts.racks.rackKw)} per rack</dd></dl>
          ${co.liquidSrc ? `<p class="hint">${esc(co.liquidSrc)}.</p>` : ""}</div>
      </div>`;
  }

  // ------------------------------------------------------------------ compliance
  function flagHTML(f) {
    return `<div class="flag ${f.sev}"><div class="h"><span class="sev">${f.sev === "approval" ? "needs approval" : f.sev}</span>${esc(f.title)}</div><p>${esc(f.detail)}</p>${f.ref ? `<div class="r">Ref: ${esc(f.ref)}</div>` : ""}</div>`;
  }
  function compliance() {
    const by = (s) => R.flags.filter((f) => f.sev === s);
    const choice = R.bom.filter((b) => b.src === "CHOICE" || b.src === "NON-RA");
    const key = JSON.stringify([cfg.gen, cfg.sus, cfg.cooling, cfg.workload, cfg.density, cfg.taper, cfg.storageTier]);
    const items = by("blocker").concat(by("approval")).map((f) => f.title).concat(choice.map((b) => `Confirm: ${b.item} (${b.src})`));
    const done = signoff[key] || {};
    $("pane").innerHTML = `
      <div class="grid2">
        <div class="card"><h2>Blockers — ${by("blocker").length}</h2>${by("blocker").map(flagHTML).join("") || `<p class="hint">None. Every selected option is supported.</p>`}</div>
        <div class="card"><h2>Needs approval — ${by("approval").length}</h2>${by("approval").map(flagHTML).join("") || `<p class="hint">None. The design follows the RA.</p>`}</div>
      </div>
      <div class="card"><h2>Sign-off checklist</h2><p class="hint">Tick items as NVIDIA, the storage partner or the facility team confirm them. Ticks stay in this browser only.</p>
        <div class="signoff" id="so">${items.map((t, i) => `<label><input type="checkbox" data-i="${i}" ${done[i] ? "checked" : ""}> <span>${esc(t)}</span></label>`).join("") || `<p class="hint">Nothing to sign off.</p>`}</div></div>
      <div class="card"><h2>Notes — ${by("info").length}</h2>${by("info").map(flagHTML).join("")}</div>
      ${R.profile.raNotes ? `<div class="card"><h2>Inconsistencies in the ${esc(R.profile.label)} RA</h2><p class="hint">Where NVIDIA's own document disagrees with itself. Raise these with NVIDIA when the design is reviewed.</p><ul class="notes">${R.profile.raNotes.map((n) => `<li>${srcPill("RA")}<span>${esc(n)}</span></li>`).join("")}</ul></div>` : ""}
      <div class="card"><h2>Where the numbers come from</h2><p class="hint">${Object.entries(R.counts.bomSrc).map(([k, v]) => `${srcPill(k)} ${v} lines`).join(" · ")}</p>
        <p class="hint">Reference: <a href="${esc(R.profile.ra.url)}" target="_blank" rel="noopener">${esc(R.profile.ra.title)}</a>, ${esc(R.profile.ra.doc)} (${esc(R.profile.ra.date)}).</p></div>`;
    $("so")?.addEventListener("change", (e) => { const i = e.target.dataset.i; if (i == null) return; signoff[key] = Object.assign({}, signoff[key], { [i]: e.target.checked }); store.set("signoff", signoff); });
  }

  // ------------------------------------------------------------------ proposal
  function proposalMarkdown() {
    const p = R.profile, c = R.counts, pw = R.power, d = new Date().toISOString().slice(0, 10);
    const L = [];
    L.push(`# ${p.label} SuperPOD — ${c.sus} SU, ${fmt(c.gpus)} GPUs`, "");
    L.push(`Prepared ${cfg.preparedFor ? `for **${cfg.preparedFor}** ` : ""}${cfg.preparedBy ? `by ${cfg.preparedBy} ` : ""}on ${d}${cfg.site ? ` · site: ${cfg.site}` : ""}.`, "");
    L.push("## Summary", "", statement().replace(/<\/?b>/g, "**"), "");
    L.push("## Configuration", "", "| Item | Value |", "|---|---|");
    [["Generation", p.label], ["Scalable units", c.sus], ["GPUs", fmt(c.gpus)], [p.family === "nvl72" ? "NVL72 racks" : "Systems", fmt(c.systems)],
     ["Workload focus", cfg.workload], ["Storage tier", `${R.workload.tier} (${p.perf.ref})`], ["Compute fabric", `${p.compute.tech}${cfg.taper !== "none" ? `, tapered ${cfg.taper}` : ""}`],
     ["Cooling", R.cooling.mode], ["Racks", `${c.racks.compute} compute + ${c.racks.mgmt} network/management`], ["IT load (peak)", kw(pw.itKw)],
     ["Facility load", `${kw(pw.facilityKw)} (PUE ${pw.pue}${pw.pueSrc === "assumption" ? ", assumed" : ""})`], ["Energy per year", `${fmt(pw.annualMWh)} MWh`]]
      .forEach(([k, v]) => L.push(`| ${k} | ${v} |`));
    L.push("", "## Bill of materials", "", "| Group | Item | Model | Qty | Source |", "|---|---|---|---:|---|");
    R.bom.forEach((b) => L.push(`| ${b.group} | ${b.item} | ${b.model} | ${b.qty} | ${b.src} |`));
    const req = R.flags.filter((f) => f.sev !== "info");
    L.push("", "## Items needing a decision", "");
    if (!req.length) L.push("None — the configuration follows the reference architecture.");
    req.forEach((f) => L.push(`- **${f.sev === "blocker" ? "Blocker" : "Approval"}: ${f.title}.** ${f.detail} _(${f.ref})_`));
    L.push("", "## Assumptions and notes", "");
    R.flags.filter((f) => f.sev === "info").forEach((f) => L.push(`- ${f.title}: ${f.detail}`));
    L.push("", "## Sources", "", `- ${p.ra.title}, ${p.ra.doc} (${p.ra.date}): ${p.ra.url}`);
    if (p.dc) L.push(`- ${p.dc.title}, ${p.dc.doc}: ${p.dc.url}`);
    if (p.raNotes) { L.push("", "## Inconsistencies in the reference architecture", ""); p.raNotes.forEach((n) => L.push(`- ${n}`)); }
    L.push("", "_Independent planning estimate based on NVIDIA's public DGX SuperPOD reference architectures. Not an NVIDIA document or quotation; lines marked DERIVED, CHOICE or NON-RA must be confirmed with NVIDIA or an NVIDIA partner._");
    return L.join("\n");
  }

  function proposal() {
    const p = R.profile, c = R.counts, req = R.flags.filter((f) => f.sev !== "info"), d = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    const grp = [...new Set(R.bom.map((b) => b.group))];
    $("pane").innerHTML = `
      <div class="row">${dlButtons(["md", "csv", "air"])}<button type="button" class="btn" id="copymd">Copy as Markdown</button></div>
      <article class="doc">
        <div class="meta">${cfg.preparedFor ? `Prepared for <b>${esc(cfg.preparedFor)}</b> · ` : ""}${cfg.preparedBy ? `by ${esc(cfg.preparedBy)} · ` : ""}${d}${cfg.site ? ` · ${esc(cfg.site)}` : ""}</div>
        <h2>${esc(p.label)} SuperPOD — ${c.sus} SU, ${fmt(c.gpus)} GPUs</h2>
        <p>${statement()}</p>
        <h4>Configuration</h4>
        <div class="tablewrap"><table class="t"><tbody>
          <tr><td>Compute</td><td>${fmt(c.systems)} × ${esc(p.label)}${p.family === "nvl72" ? ` (${fmt(c.trays)} trays)` : ""} · ${fmt(c.gpus)} GPUs${c.gpuMemTB ? ` · ${fmt(c.gpuMemTB, 1)} TB GPU memory` : ""}</td></tr>
          <tr><td>Compute fabric</td><td>${esc(p.compute.tech)} · ${fmt(c.compute.leaves)} leaf, ${fmt(c.compute.spines)} spine${c.compute.core ? `, ${c.compute.core} core` : ""} (${esc(p.compute.switch)})</td></tr>
          <tr><td>Storage</td><td>${esc(R.workload.tier)} tier · ${fmt(c.storage.target)} GB/s read target · ${fmt(c.storage.appliances)} appliances (partner-specific)</td></tr>
          <tr><td>Racks</td><td>${fmt(c.racks.compute)} compute + ${fmt(c.racks.mgmt)} network / management · ${kw(c.racks.rackKw)} per compute rack</td></tr>
          <tr><td>Power</td><td>${kw(R.power.itKw)} IT · ${kw(R.power.facilityKw)} facility (PUE ${R.power.pue}) · ${fmt(R.power.annualMWh)} MWh / year</td></tr>
          <tr><td>Cooling</td><td>${esc(R.cooling.mode)}</td></tr>
          <tr><td>Cabling</td><td>${fmt(c.cablesTotal)} cables · ${fmt(c.transceivers)} optics · ${fmt(c.switches)} switches</td></tr>
        </tbody></table></div>
        <h4>Bill of materials</h4>
        <div class="tablewrap"><table class="t"><thead><tr><th>Item</th><th>Model</th><th class="n">Qty</th><th>Source</th></tr></thead><tbody>${grp.map((g) => `<tr class="grp"><td colspan="4">${esc(g)}</td></tr>` + R.bom.filter((b) => b.group === g).map((b) => `<tr><td>${esc(b.item)}</td><td>${esc(b.model)}</td><td class="n">${fmt(b.qty)}</td><td>${srcPill(b.src)}</td></tr>`).join("")).join("")}</tbody></table></div>
        <h4>Decisions required</h4>
        ${req.length ? `<ul>${req.map((f) => `<li><b>${f.sev === "blocker" ? "Blocker" : "Approval"} — ${esc(f.title)}.</b> ${esc(f.detail)}</li>`).join("")}</ul>` : `<p>None: the configuration follows the reference architecture.</p>`}
        <h4>Workload fit</h4><ul>${R.workload.notes.map((n) => `<li>${esc(n.text)}</li>`).join("")}</ul>
        <h4>Sources</h4><ul><li><a href="${esc(p.ra.url)}" target="_blank" rel="noopener">${esc(p.ra.title)}</a>, ${esc(p.ra.doc)} (${esc(p.ra.date)})</li>${p.dc ? `<li><a href="${esc(p.dc.url)}" target="_blank" rel="noopener">${esc(p.dc.title)}</a>, ${esc(p.dc.doc)}</li>` : ""}</ul>
        ${p.raNotes ? `<h4>Known inconsistencies in the reference architecture</h4><ul>${p.raNotes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
        <p class="disclaimer">Independent planning estimate based on NVIDIA's public DGX SuperPOD reference architectures. Not an NVIDIA document or quotation. Lines marked DERIVED, CHOICE or NON-RA must be confirmed with NVIDIA or an NVIDIA partner before ordering.</p>
      </article>`;
    $("copymd").onclick = () => copy(proposalMarkdown(), "Proposal copied as Markdown");
    wireDownloads();
  }

  // ------------------------------------------------------------------ exports
  function bomCSV() {
    const q = (s) => `"${String(s).replace(/"/g, '""')}"`;
    return ["group,item,model,qty,source,reference"].concat(R.bom.map((b) => [b.group, b.item, b.model, b.qty, b.src, b.ref].map(q).join(","))).join("\n");
  }
  const fname = (ext) => `superpod-${R.profile.id}-${R.cfg.sus}su-${R.counts.gpus}gpu${cfg.preparedFor ? "-" + cfg.preparedFor.toLowerCase().replace(/[^a-z0-9]+/g, "-") : ""}.${ext}`;
  const EXPORTS = { md: ["Download proposal (.md)", () => ({ filename: fname("md"), data: proposalMarkdown() })],
                    csv: ["Download BOM (.csv)", () => ({ filename: fname("csv"), data: bomCSV() })],
                    air: ["NVIDIA Air topology (.json)", () => ({ filename: fname("air.json"), data: JSON.stringify(R.air, null, 2) })] };
  function dlButtons(keys) { return keys.map((k) => `<button type="button" class="btn" data-dl="${k}">${EXPORTS[k][0]}</button>`).join(""); }
  function wireDownloads() {
    $("pane").querySelectorAll("[data-dl]").forEach((b) => {
      b.onclick = async () => {
        const { filename, data } = EXPORTS[b.dataset.dl][1]();
        if (caps.downloads) {
          try { await caps.downloads.save({ filename, data }); toast("Saved " + filename); return; }
          catch (e) { if (e && e.code === "declined") return; if (e && e.code === "rate_limited") { toast("A save prompt is already open"); return; } }
        }
        copy(data, `Downloads are unavailable here — ${filename} copied to the clipboard instead`);
      };
    });
  }
  async function copy(text, msg) {
    try { await navigator.clipboard.writeText(text); toast(msg); }
    catch { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); toast("Press Ctrl/⌘+C to copy"); setTimeout(() => ta.remove(), 8000); }
  }

  // ------------------------------------------------------------------ as built (NetBox export)
  const ASB = (() => { try { return JSON.parse($("asbuilt").textContent); } catch { return []; } })();
  let asSite = store.get("asSite", 0), asFab = store.get("asFab", "compute");
  function asbuilt() {
    if (!ASB.length) { $("pane").innerHTML = `<p class="hint">No NetBox export embedded.</p>`; return; }
    const s = ASB[asSite] || ASB[0];
    const fabs = [...new Set(s.links.map((l) => l[4]))];
    if (!fabs.includes(asFab)) asFab = fabs[0];
    $("pane").innerHTML = `
      <p class="hint">Reference builds generated by this project's IaC tool and loaded into NetBox: every device and cable, folded by rack. Use it to show what the design looks like as records.</p>
      <div class="row"><div class="seg" id="asSite">${ASB.map((x, i) => `<button type="button" data-i="${i}" aria-pressed="${i === asSite}">${esc(x.site)} · ${esc(x.name)}</button>`).join("")}</div>
        <div class="seg" id="asFab">${fabs.map((f) => `<button type="button" data-f="${f}" aria-pressed="${f === asFab}">${FAB[f] || f}</button>`).join("")}</div></div>
      <div class="topo"><div class="stage"><div id="cy2" aria-label="As-built topology"></div></div><div class="card insp" id="insp2"><h2>${esc(s.name)}</h2><p class="hint">${esc(s.description)}</p><div class="row2"><span>devices</span><b class="num">${fmt(s.devices.length)}</b></div><div class="row2"><span>cables (non-power)</span><b class="num">${fmt(s.links.length)}</b></div></div></div>`;
    $("asSite").onclick = (e) => { const b = e.target.closest("[data-i]"); if (b) { asSite = +b.dataset.i; store.set("asSite", asSite); asbuilt(); } };
    $("asFab").onclick = (e) => { const b = e.target.closest("[data-f]"); if (b) { asFab = b.dataset.f; store.set("asFab", asFab); asbuilt(); } };
    const dev = new Map(s.devices.map((d) => [d[0], { name: d[0], role: d[1], rack: d[3], tier: d[4] }]));
    const fold = new Set(["dgx-compute", "gb-compute-tray", "gb-nvlink-switch", "gb-power-shelf", "pdu"]);
    const nid = (d) => (d.rack && fold.has(d.role) ? `${d.rack}|${d.role}` : d.name);
    const nodes = new Map(), edges = new Map();
    for (const l of s.links) {
      if (l[4] !== asFab) continue;
      const a = dev.get(l[0]), b = dev.get(l[2]); if (!a || !b) continue;
      const ia = nid(a), ib = nid(b);
      for (const [id, d] of [[ia, a], [ib, b]]) if (!nodes.has(id)) nodes.set(id, { id, label: id.includes("|") ? `${d.rack.replace(/^(dgx|gb)-/, "")}\n${d.role.replace(/^(dgx|gb)-/, "")}` : d.name, tier: d.tier, kind: d.tier <= 0 ? "spine" : d.tier === 1 ? "leaf" : "systems", count: 1 });
      if (ia === ib) continue;
      const k = [ia, ib].sort().join("~");
      if (!edges.has(k)) edges.set(k, { s: ia, t: ib, n: 0, f: asFab });
      edges.get(k).n++;
    }
    const g = { nodes: [...nodes.values()], edges: [...edges.values()] };
    drawGraph(g, "cy2", "insp2");
  }

  // ------------------------------------------------------------------ scenarios (db) + capabilities
  function renderScen() {
    const opts = caps.scenarios.map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join("");
    $("scen").innerHTML = caps.db
      ? `<select class="sel" id="scSel" aria-label="Saved scenarios"><option value="">Saved scenarios (${caps.scenarios.length})</option>${opts}</select>
         <button type="button" class="btn" id="scLoad">Load</button>
         ${caps.canWrite ? `<button type="button" class="btn primary" id="scSave">Save scenario</button><button type="button" class="btn" id="scDel">Delete</button>` : ""}`
      : `<span class="hint">Scenarios unavailable</span>`;
    if (!caps.db) return;
    $("scLoad").onclick = () => { const s = caps.scenarios.find((x) => x.id === $("scSel").value); if (s) { cfg = sanitize(s.cfg); store.set("cfg", cfg); render(); toast("Loaded " + s.name); } };
    if (caps.canWrite) {
      $("scSave").onclick = async () => {
        const name = (cfg.preparedFor ? cfg.preparedFor + " — " : "") + `${PROFILES[cfg.gen].label} ${cfg.sus} SU ${cfg.workload}`;
        const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 80);
        try { await caps.db.collection("scenarios").doc(id).set({ name, cfg: Object.assign({}, cfg), gpus: R.counts.gpus, savedAt: new Date().toISOString() }); toast("Saved: " + name); }
        catch (e) { toast(e && e.code === "quota_exceeded" ? "Scenario store is full — delete some first" : "Could not save the scenario"); }
      };
      $("scDel").onclick = async () => { const id = $("scSel").value; if (!id) { toast("Pick a scenario to delete"); return; } try { await caps.db.collection("scenarios").doc(id).delete(); toast("Deleted"); } catch { toast("Could not delete"); } };
    }
  }

  // Fallback scenario store for pages opened outside the claude.ai artifact host: the same
  // minimal db surface the code above uses (collection().doc().set/delete, orderBy/limit/
  // onSnapshot), backed by localStorage. Every storage touch is try/catch'd; when storage is
  // blocked it degrades to an in-memory list, and the page still works with neither.
  function localScenarioDb() {
    const KEY = "atlas.scenarios";
    let mem = [];                                   // used when localStorage is unavailable
    const read = () => { try { const v = JSON.parse(localStorage.getItem(KEY) || "null"); if (Array.isArray(v)) return v; } catch { /* blocked or corrupt */ } return mem; };
    const write = (rows) => { mem = rows; try { localStorage.setItem(KEY, JSON.stringify(rows)); } catch { /* quota or blocked: memory only */ } };
    const listeners = new Set();
    const notify = () => { const rows = read().slice().sort((a, b) => String(b.savedAt).localeCompare(String(a.savedAt))); listeners.forEach((f) => f({ docs: rows.map((r) => ({ id: r.id, data: () => r })) })); };
    const coll = {
      doc: (id) => ({
        set: async (data) => { write(read().filter((r) => r.id !== id).concat([Object.assign({}, data, { id })])); notify(); },
        delete: async () => { write(read().filter((r) => r.id !== id)); notify(); },
      }),
      orderBy: () => coll, limit: () => coll,
      onSnapshot: (ok) => { listeners.add(ok); ok({ docs: [] }); notify(); return () => listeners.delete(ok); },
    };
    return { collection: () => coll };
  }

  async function initCaps() {
    if (!window.claude || !window.claude.use) {
      try { caps.db = localScenarioDb(); caps.canWrite = true; caps.local = true;
            caps.db.collection("scenarios").orderBy("savedAt", "desc").limit(200).onSnapshot((snap) => { caps.scenarios = snap.docs.map((d) => Object.assign({ id: d.id }, d.data())); renderScen(); }); }
      catch { caps.db = null; }
      renderScen(); return;
    }
    const [db, dl, user] = await Promise.all(["db", "downloads", "user"].map((n) => window.claude.use(n).catch(() => null)));
    caps.db = db; caps.downloads = dl; caps.user = user;
    if (user) { try { const w = await user.can("data.write"); caps.canWrite = w === null ? true : !!w; } catch { caps.canWrite = false; } }
    if (db) db.collection("scenarios").orderBy("savedAt", "desc").limit(200).onSnapshot(
      (snap) => { caps.scenarios = snap.docs.map((d) => Object.assign({ id: d.id }, d.data())); renderScen(); },
      () => { caps.db = null; renderScen(); });
    renderScen();
  }

  // ------------------------------------------------------------------ main
  function render() {
    R = Atlas.configure(cfg);
    renderRail(); renderCounters(); renderTabs(); renderPane();
  }
  wireRail();
  render();
  initCaps();
  const rerenderTheme = () => { if (tab === "topology" || tab === "asbuilt" || tab === "racks" || tab === "power") renderPane(); };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rerenderTheme);
  new MutationObserver(rerenderTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.addEventListener("hashchange", () => { const t = location.hash.slice(1); if (TABS.some(([k]) => k === t)) { tab = t; renderTabs(); renderPane(); } });
})();
