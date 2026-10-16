/* SuperPOD Atlas — configuration engine. Pure: runs in the page and under node (tests).
 *
 *   configure(cfg) -> { profile, cfg, counts, bom, racks, power, cooling, graph, flags, workload, air }
 *
 * Every BOM line carries `src`:
 *   RA       stated in the reference architecture for this size
 *   DERIVED  computed from RA values by the rule written next to it (it reproduces the RA wherever both exist)
 *   CHOICE   an assumption the RA leaves open (vendor, count, power) — confirm with NVIDIA / the partner
 *   NON-RA   a deviation the user selected — needs design approval
 * Flags: blocker (not supported), approval (sign-off needed), info (context, RA gaps).
 */
(function (root) {
  const A = root.ATLAS || require("./profiles.js");
  const P = A.PROFILES;

  const DEFAULTS = { gen: "h200", sus: 2, populated: null, cooling: "auto", workload: "training", storageTier: "auto",
                     density: null, taper: "none", pue: null, preparedFor: "", preparedBy: "", site: "" };
  const APPLIANCE_READ = 30;   // CHOICE: reference storage appliance, 30 GB/s read, 8 × 400G ports
  const ceil = Math.ceil, gcd = (a, b) => (b ? gcd(b, a % b) : a);

  /** Smallest spine count that divides each leaf's uplinks evenly and has enough ports.
   *  Reproduces the RA tables: H-series 1–4 SU (4, 8, 16, 16), B300 XDR (4, 8, 18, 36), GB200 1 SU (9). */
  function spineCount(up, total, ports) {
    for (let s = 1; s <= up; s++) if (up % s === 0 && s * ports >= total) return s;
    return null;
  }

  function configure(cfgIn) {
    const cfg = Object.assign({}, DEFAULTS, cfgIn || {});
    const p = P[cfg.gen];
    if (!p) throw new Error("unknown generation " + cfg.gen);
    cfg.sus = Math.max(1, Math.round(+cfg.sus || 1));
    const pos = (v) => (v === null || v === "" || !isFinite(+v) || +v <= 0 ? null : +v);
    cfg.populated = pos(cfg.populated) && Math.round(pos(cfg.populated));
    cfg.density = pos(cfg.density) && Math.round(pos(cfg.density));
    cfg.pue = pos(cfg.pue);
    const o = { profile: p, cfg, bom: [], flags: [], racks: [], graph: {}, counts: { cables: {} } };
    if (cfg.pue !== null && cfg.pue < 1) { cfg.pue = null; o.flags.push({ sev: "info", title: "PUE below 1 ignored", detail: "A PUE cannot be lower than 1; the default assumption is used.", ref: "" }); }
    o.add = (group, item, model, qty, src, ref, extra) => { if (qty > 0) o.bom.push(Object.assign({ group, item, model, qty, src, ref }, extra || {})); return qty; };
    o.flag = (sev, title, detail, ref) => o.flags.push({ sev, title, detail, ref: ref || "" });
    cooling(p, cfg, o);
    workload(p, cfg, o);
    (p.family === "hgx" ? hgx : nvl72)(p, cfg, o);
    finish(p, cfg, o);
    delete o.add; delete o.flag;
    return o;
  }

  // ------------------------------------------------------------------ cooling
  function cooling(p, cfg, o) {
    const mode = cfg.cooling === "auto" ? p.coolingRecommended : cfg.cooling;
    o.coolingMode = mode;
    if (p.coolingNative === "liquid" && mode !== "liquid")
      o.flag("blocker", `${p.label} needs direct liquid cooling`,
        "NVL72 racks are hybrid-cooled: GPUs and CPUs on cold plates, the rest on air. They cannot run in an air-only hall.", p.ra.doc);
    if (p.coolingNative === "air" && mode === "liquid")
      o.flag("blocker", `${p.label} is an air-cooled system`,
        "There is no direct-liquid DGX variant of this system. Choose GB200/GB300 NVL72 for liquid, or rear-door heat exchangers to raise air density.", p.ra.doc);
    if (p.coolingNative === "air" && mode === "air-rdhx" && p.coolingRecommended !== "air-rdhx")
      o.flag("approval", "Rear-door heat exchangers (facility option)",
        "RDHx is a data-centre choice outside this RA; the facility design needs sign-off." + (p.id === "b200" ? " NVIDIA's B200 data-centre guide calls rear-door and in-row coolers 'not typically suitable'." : ""), p.dc ? p.dc.doc : "DC design guide");
    if (p.coolingRecommended === "air-rdhx" && mode === "air")
      o.flag("approval", "Plain air at 4 systems per rack",
        "NVIDIA's B300 data-centre guide recommends active rear-door heat exchangers for the 4-per-rack busbar pattern (passive RDHx not recommended).", "B300 DC best practices");
  }

  // ------------------------------------------------------------------ workload
  function workload(p, cfg, o) {
    const tiers = p.perf.tiers;
    const rec = cfg.workload === "training" ? tiers[tiers.length - 1] : cfg.workload === "inference" ? tiers[0] : tiers[Math.floor((tiers.length - 1) / 2)];
    const tier = cfg.storageTier === "auto" || !tiers.includes(cfg.storageTier) ? rec : cfg.storageTier;
    const w = (o.workload = { focus: cfg.workload, tiers, recommended: rec, tier, notes: [] });
    const note = (src, text) => w.notes.push({ src, text });
    if (cfg.workload === "training") note("RA", "SuperPOD RAs are built for multi-node training: a rail-optimised, non-blocking compute fabric and a dedicated high-performance storage fabric.");
    if (cfg.workload === "inference") {
      note("ADVISORY", "Inference needs less storage bandwidth and often tolerates a tapered fabric. The RA defines neither, so both are flagged for approval when selected.");
      note("ADVISORY", p.family === "nvl72" ? "NVL72 puts 72 GPUs in one NVLink domain — a strong fit for very large models, long context and disaggregated serving."
                                            : "Each system is an 8-GPU NVLink domain; models larger than one node need tensor or pipeline parallelism over the fabric.");
    }
    if (cfg.workload === "mixed") note("ADVISORY", "Mixed fine-tuning and serving: the RA fabric stays intact and storage is sized at the middle tier.");
    note("RA", `Storage sized for the "${tier}" tier of ${p.perf.ref}.`);
    if (p.perf.borrowed) o.flag("info", "Storage guideline borrowed", p.perf.borrowed, p.perf.ref);
    if (tiers.indexOf(tier) < tiers.indexOf(rec))
      o.flag("approval", `Storage below the ${cfg.workload} recommendation`, `"${tier}" selected, "${rec}" recommended. Checkpointing and data loading may idle the GPUs.`, p.perf.ref);
    if (cfg.taper !== "none")
      o.flag("approval", `Compute fabric tapered ${cfg.taper} (non-RA)`,
        "The RA specifies a non-blocking, rail-optimised fat tree. Tapering cuts spine switches and optics but slows collective traffic between SUs.", p.ra.doc);
  }

  // ------------------------------------------------------------------ 8-GPU systems
  function hgx(p, cfg, o) {
    const cp = p.compute, S = p.su, sus = cfg.sus, rails = p.rails, sys = p.system;
    const row = S.table[sus], big = S.beyond && S.beyond[sus];
    const r1 = S.table[1];
    let nodes, leaves, spines, core = 0, nodeLeaf, leafSpine, src = "RA", ref = S.ref;
    if (row || big) {
      [nodes, leaves, spines, core, nodeLeaf, leafSpine] = row || big;
      if (big) o.flag("approval", `${sus} SUs uses the RA's 'larger SuperPOD' table`, "These sizes are listed but not fully tested; NVIDIA designs them per project (UFM placement, core layer, cabling).", S.ref);
    } else {
      leaves = sus * cp.leavesPerSU;
      const up = cp.ports / 2;
      spines = spineCount(up, leaves * up, cp.ports);
      nodes = sus * S.systems - p.displaced;
      nodeLeaf = nodes * rails + (p.displaced ? 4 : 0);
      leafSpine = leaves * (r1[5] / r1[1]);
      src = "DERIVED";
      o.flag("approval", `No RA row for ${sus} SUs`, "Counts derived with the RA's non-blocking fat-tree rule (it reproduces every RA row); confirm with NVIDIA.", S.ref);
      if (!spines) { o.flag("blocker", "Beyond a two-tier fabric", "This size needs a core layer the RA does not size here. Pick an SU count from the RA table.", S.ref); spines = ceil(leaves * up / cp.ports); }
    }
    if (sus > S.maxTested && row) o.flag("approval", `${sus} SUs is beyond the RA's validated focus (${S.maxTested} SUs)`, "The table lists this size; NVIDIA validates it per project.", S.ref);
    const ufmLinks = Math.max(0, nodeLeaf - nodes * rails);
    if (p.displaced && (row || !big)) o.flag("info", `${sus * S.systems - nodes} system slot given to UFM`, `The RA removes one system per pod so the UFM pair can reach the compute leaves: ${nodes} of ${sus * S.systems} slots.`, S.ref);
    const systems = cfg.populated ? Math.min(+cfg.populated, nodes) : nodes;
    if (cfg.populated > nodes) o.flag("info", `Populate capped at ${nodes} systems`, `${cfg.populated} requested; ${sus} SU holds ${nodes}. Add SUs for more.`, S.ref);
    if (systems < nodes) o.flag("info", `Partially populated: ${systems} of ${nodes} systems`, "Build the full SU fabric (every leaf and leaf-spine cable) and leave the empty slots unused.", p.ra.doc + " 'Network Fabrics'");
    const taper = cfg.taper === "2:1" ? 2 : 1;
    if (taper > 1) { spines = ceil(spines / 2); leafSpine = ceil(leafSpine / 2); if (core) core = ceil(core / 2); }
    const nsrc = (base) => (taper > 1 ? "NON-RA" : base);

    o.counts.systems = systems; o.counts.gpus = systems * sys.gpus; o.counts.sus = sus;
    o.add("Compute", p.label, sys.gpu, systems, "RA", sys.ref, { w: sys.kw * 1000, u: sys.u, kind: "system" });
    o.add("Compute fabric", `Leaf switches (${cp.leavesPerSU} per SU)`, cp.switch, leaves, src, ref, { w: cp.w, u: cp.u, kind: "switch" });
    o.add("Compute fabric", "Spine switches", cp.switch, spines, nsrc(src), ref, { w: cp.w, u: cp.u, kind: "switch" });
    o.add("Compute fabric", "Core switches", cp.switch, core, nsrc("RA"), ref, { w: cp.w, u: cp.u, kind: "switch" });
    const cNode = systems * rails;
    o.add("Cables", "Compute: system → rail leaf", cp.cable, cNode, "RA", ref);
    o.add("Cables", "Compute: UFM → leaf", "NDR 200G", ufmLinks, "RA", ref);
    o.add("Cables", "Compute: leaf → spine", cp.cable, leafSpine, nsrc(src), ref);
    o.add("Cables", "Compute: spine → core", cp.cable, core ? leafSpine : 0, nsrc("DERIVED"), ref);
    const cCables = o.bom.filter((b) => b.item.startsWith("Compute:")).reduce((a, b) => a + b.qty, 0);
    o.counts.cables.compute = cCables;
    o.add("Transceivers", "System OSFP (compute)", cp.cable, systems * sys.sysOsfp, "DERIVED", `${sys.sysOsfp} per system`);
    const lpc = cp.lanesPerCable || 1, portsPerCage = cp.ports / cp.cages;
    const usedPorts = (cNode + ufmLinks) * lpc + 2 * leafSpine * lpc + (core ? 2 * leafSpine * lpc : 0);
    o.add("Transceivers", "Switch OSFP (compute, ports in use)", cp.cable, ceil(usedPorts / portsPerCage), "DERIVED", `ports in use / ${portsPerCage} per cage (H100 RA Table 8 counts every cage: 1,536 at 4 SU)`);

    const ufm = o.add("Management", "UFM appliances", p.ufm.model, p.ufm.count, "RA", p.ufm.ref, { w: A.W.UFM, u: 1, kind: "mgmt" });
    const mgmt = o.add("Management", "Control-plane servers (BCM, Slurm / K8s)", p.mgmt.model, p.mgmt.count, "RA", p.mgmt.ref, { w: A.W.MGMT, u: 2, kind: "mgmt" });

    // storage fabric — DERIVED: DGX-facing leaves 32 down / 24 up (≈4:3), device leaf 1:1, spines by the divisor rule
    const st = p.storage, tierPerf = p.perf.perSU[o.workload.tier], target = tierPerf[0] * sus;
    const appl = Math.max(2, ceil(target / APPLIANCE_READ));
    const dgxLeaves = 2 * ceil(systems / 32), hpsPorts = appl * 8, devDown = hpsPorts + 4 + 2 * mgmt;
    let nDev = 1; while (ceil(devDown / nDev) + ceil(hpsPorts / nDev) > st.ports) nDev++;
    const devUp = ceil(hpsPorts / nDev), stUp = dgxLeaves * 24 + nDev * devUp;
    const stSpines = spineCount(gcd(24, devUp), stUp, st.ports) || ceil(stUp / st.ports);
    o.add("Storage", "High-performance storage appliances", `Partner-certified (${APPLIANCE_READ} GB/s read, 8 × 400G each)`, appl, "CHOICE",
      `${p.perf.ref}: "${o.workload.tier}" = ${tierPerf[0]} GB/s read per SU → ${target} GB/s`, { w: A.W.HPS, u: 2, kind: "storage" });
    o.add("Storage fabric", "Storage leaves (DGX A/B + device)", st.switch, dgxLeaves + nDev, "DERIVED", "RA 'Storage Fabric' ratios", { w: st.w, u: 1, kind: "switch" });
    o.add("Storage fabric", "Storage spines", st.switch, stSpines, "DERIVED", "RA 'Storage Fabric' ratios", { w: st.w, u: 1, kind: "switch" });
    o.counts.cables.storage = 2 * systems + stUp + hpsPorts + 4 + 2 * mgmt;
    o.add("Cables", "Storage: system → leaf (2 per system)", "NDR 400G", 2 * systems, "RA", st.ref);
    o.add("Cables", "Storage: leaf → spine", "NDR 400G", stUp, "DERIVED", st.ref);
    o.add("Cables", "Storage: appliance links", "NDR 400G → 2 × 200G", hpsPorts, "CHOICE", "RA cable table note: 'depend on specific storage selected'");
    o.add("Transceivers", "System QSFP112 (storage)", "400G", 2 * systems, "RA", "RA Table 8 (2 per system)");
    if (p.storageRef) o.flag("info", `RA storage-fabric figure: ${p.storageRef.count} switches at ${p.storageRef.sus} SU`,
      `This tool derives ${dgxLeaves + nDev + stSpines} for ${sus} SU from the RA's port ratios (4:3 DGX side, 1:1 storage side) and the selected storage tier. ${p.storageRef.text}.`, p.storage.ref);
    o.flag("info", "Storage count and vendor are partner-specific", `Sized for the "${o.workload.tier}" tier with a reference appliance; the certified storage partner sets the real count and cabling.`, "RA cable table note 2");

    // in-band Ethernet
    const ibL = 2 * ceil(p.inband.leaves(sus) / 2), ibS = p.inband.spines;   // MLAG pairs: always even
    const atRef = sus === p.refSU, refSrc = atRef ? "RA" : "DERIVED";
    o.add("In-band Ethernet", "In-band leaves", p.inband.switch, ibL, (p.inband.raSizes || [p.refSU]).includes(sus) ? "RA" : "DERIVED", p.inband.ref, { w: p.inband.w, u: p.inband.u, kind: "switch" });
    o.add("In-band Ethernet", "In-band spines", p.inband.switch, ibS, "RA", p.inband.ref, { w: p.inband.w, u: p.inband.u, kind: "switch" });
    const ibX = p.inband.extra ? o.add("In-band Ethernet", p.inband.extra.item, p.inband.extra.model, p.inband.extra.count, refSrc, p.inband.ref, { w: p.inband.extra.w, u: p.inband.extra.u, kind: "switch" }) : 0;

    // racks, power distribution
    const def = p.density.def, perRack = +cfg.density || def;
    const slots = cfg.populated ? systems : sus * S.systems;
    const cRacks = ceil(slots / perRack), mRacks = Math.max(2, ceil(p.racks.mgmtPerSU * sus));
    const rackKw = perRack * sys.kw;
    if (perRack !== def) {
      const known = p.density.options[perRack];
      if (perRack > 4) o.flag("blocker", `${perRack} systems per rack`, "NVIDIA does not support more than 4 DGX per rack (thermal and power).", "DCG Table 8 note 3");
      else o.flag("approval", `${perRack} systems per rack (RA: ${def})`,
        `${rackKw.toFixed(1)} kW per rack${known ? ` — pattern from ${known}` : " — not a documented pattern"}. Power distribution, cooling and floor loading need facility sign-off.`, p.density.ref);
    }
    const pdus = cRacks * p.racks.pdusCompute + mRacks * p.racks.pdusMgmt;
    const busbarRacks = p.racks.powerShelves ? cRacks + ceil(mRacks * (p.racks.busbarMgmtShare || 0)) : 0;
    const shelves = busbarRacks * (p.racks.powerShelves || 0);
    o.add("Racks & power", `Compute racks (${perRack} systems each)`, p.id === "b300e" ? "MGX rack with 54 V busbar" : "48U, 600 × 1200 mm", cRacks, perRack === def ? (atRef || !cfg.populated ? "RA" : "DERIVED") : "NON-RA", p.density.ref);
    o.add("Racks & power", "Network / management / storage racks", p.id === "b300e" ? "MGX rack (half with busbar)" : "48U", mRacks, refSrc, p.racks.ref);
    o.add("Racks & power", "Rack PDUs", p.id === "b300e" ? "Raritan PX4 (MGX)" : "Raritan PX3 series (415 V three-phase)", pdus, refSrc, p.racks.ref);
    o.add("Racks & power", "Busbar power shelves (33 kW)", "DGX power shelf", shelves, refSrc, p.racks.ref);
    if (p.id === "b300e" && perRack !== def)
      o.flag("approval", "Low-density B300 racks keep the busbar BOM", "The DC guide's 2-per-rack pattern uses AC power; this BOM still lists MGX busbar racks and power shelves. Confirm the power design.", p.density.ref);

    // OOB
    const netSw = leaves + spines + core + dgxLeaves + nDev + stSpines + ibL + ibS + ibX;
    const oobPorts = systems * p.oob.perSystem + netSw + mgmt + ufm + appl * 2 + pdus + shelves;
    // RA count at the RA's reference size; elsewhere scaled by management-port count (the RA packs
    // switches per rack row, so plain ports / 48 under-counts).
    o.counts.oobPorts = oobPorts;
    let oob = ceil(oobPorts / p.oob.ports), oobSrc = "DERIVED", oobRef = `${oobPorts} management ports / 48`;
    if (p.oob.raCount) {
      const refPorts = atRef ? oobPorts : configure({ gen: p.id, sus: p.refSU, workload: cfg.workload, _inner: true }).counts.oobPorts;
      oob = atRef ? p.oob.raCount : Math.max(1, ceil(p.oob.raCount * oobPorts / refPorts));
      oobSrc = atRef ? "RA" : "DERIVED";
      oobRef = atRef ? p.oob.ref : `RA ${p.oob.raCount} at ${p.refSU} SU, scaled by management ports (${oobPorts} vs ${refPorts})`;
    }
    o.add("Out-of-band", "OOB switches (48 × 1 GbE)", p.oob.switch, oob, oobSrc, oobRef, { w: p.oob.w, u: 1, kind: "switch" });
    o.counts.cables.inband = 2 * systems + 2 * mgmt + ibL * 4 + (ibL / 2 + 1) * 2 + 12 + 2 * oob;
    o.counts.cables.oob = oobPorts;
    o.add("Cables", "In-band: system links (2 per system)", "400G / 100G", 2 * systems, p.inband.linksDerived ? "DERIVED" : "RA", p.inband.linksDerived || p.inband.ref);
    o.add("Cables", "In-band: leaf, spine, ISL, DC edge, OOB uplinks", "100–400G", o.counts.cables.inband - 2 * systems, "DERIVED", p.inband.ref);
    o.add("Cables", "OOB: management ports", "Cat6 1G", oobPorts, "DERIVED", p.oob.ref);

    o.counts.compute = { leaves, spines, core, rails, ufmLinks };
    o.counts.racks = { compute: cRacks, mgmt: mRacks, perRack, rackKw, budget: perRack === def ? p.density.kwBudget : Math.max(rackKw, p.density.kwBudget) };
    o.counts.storage = { appliances: appl, target, leaves: dgxLeaves + nDev, spines: stSpines };

    // typical elevations
    const items = [];
    let u = 3;
    for (let i = 0; i < perRack; i++) { items.push({ u, h: sys.u, label: `${p.short} system ${i + 1}`, kind: "system" }); u += sys.u + (i % 2 === 0 && perRack > 1 ? 3 : 0); }
    if (p.racks.powerShelves) for (let i = 0; i < p.racks.powerShelves; i++) items.push({ u: 46 - i, h: 1, label: "Power shelf 33 kW", kind: "power" });
    else for (let i = 0; i < p.racks.pdusCompute; i++) items.push({ u: 46 - i * 2, h: 2, label: "rPDU", kind: "power" });
    o.racks.push({ key: "compute", title: `Compute rack`, count: cRacks, kw: rackKw, budget: o.counts.racks.budget, u: 48, items,
                   note: `${perRack} × ${p.label} · ${p.density.ref}` });
    const m = []; let top = 44;
    const put = (n, h, label, kind) => { for (let i = 0; i < n && top - h >= 1; i++) { m.push({ u: top - h + 1, h, label, kind }); top -= h; } };
    put(Math.min(8, leaves), cp.u, "Compute leaf", "ib"); put(Math.min(4, spines), cp.u, "Compute spine", "ib"); put(2, 1, "UFM", "mgmt");
    put(2, p.inband.u, "In-band switch", "eth"); put(1, 1, "OOB switch", "oob"); put(3, 2, "Control-plane server", "mgmt");
    o.racks.push({ key: "mgmt", title: "Network / management rack", count: mRacks, kw: null, budget: p.racks.mgmtBudget || null, u: 48, items: m, note: "typical layout after the RA's management-rack figure" });

    o.graph = hgxGraph(p, o, { sus, leaves, spines, core, systems, rails, dgxLeaves, nDev, stSpines, appl, ibL, ibS, oob, mgmt, taper });
  }

  function hgxGraph(p, o, c) {
    const per = []; let left = c.systems;
    for (let s = 1; s <= c.sus; s++) { const n = Math.min(p.su.systems, left); per.push(n); left -= n; }
    const lpsu = c.leaves / c.sus, G = {};
    const grpLeaves = c.leaves > 40, grpSpines = c.spines > 18;
    const cn = [], ce = [];
    if (grpSpines) cn.push({ id: "sp", label: `${c.spines} spines`, tier: 0, kind: "spine", count: c.spines });
    else for (let i = 1; i <= c.spines; i++) cn.push({ id: "sp" + i, label: `spine ${i}`, tier: 0, kind: "spine" });
    if (c.core) cn.push({ id: "core", label: `${c.core} core`, tier: -1, kind: "core", count: c.core });
    for (let s = 1; s <= c.sus; s++) {
      cn.push({ id: `S${s}`, label: `SU${s}\n${per[s - 1]} × ${p.short}`, tier: 2, kind: "systems", count: per[s - 1] });
      if (grpLeaves) { cn.push({ id: `L${s}`, label: `SU${s} leaves ×${lpsu}`, tier: 1, kind: "leaf", count: lpsu }); ce.push({ s: `S${s}`, t: `L${s}`, n: per[s - 1] * c.rails, f: "compute" }); }
      else for (let l = 1; l <= lpsu; l++) {
        const rail = ((l - 1) % c.rails) + 1, plane = lpsu > c.rails ? (l > c.rails ? "b" : "a") : "";
        cn.push({ id: `L${s}.${l}`, label: `SU${s} rail ${rail}${plane}`, tier: 1, kind: "leaf", rail });
        ce.push({ s: `S${s}`, t: `L${s}.${l}`, n: per[s - 1], f: "compute", rail });
      }
    }
    const L = cn.filter((n) => n.kind === "leaf"), SP = cn.filter((n) => n.kind === "spine");
    const upPerLeaf = (p.compute.ports / 2) / c.taper;
    for (const l of L) for (const s of SP) ce.push({ s: l.id, t: s.id, n: (upPerLeaf * (l.count || 1)) / (grpSpines ? 1 : c.spines), f: "compute" });
    if (c.core) for (const s of SP) ce.push({ s: s.id, t: "core", n: (c.leaves * upPerLeaf) / SP.length, f: "compute" });
    if (p.displaced) { cn.push({ id: "ufm", label: "UFM ×2", tier: 1, kind: "mgmt" }); ce.push({ s: "ufm", t: L[L.length - 1].id, n: 4, f: "compute" }); }
    G.compute = { nodes: cn, edges: ce, title: "Compute fabric" };

    const sn = [], se = [];
    for (let i = 1; i <= c.stSpines; i++) sn.push({ id: "ss" + i, label: `storage spine ${i}`, tier: 0, kind: "spine" });
    for (let s = 1; s <= c.sus; s++) {
      const k = 2 * ceil(per[s - 1] / 32);
      sn.push({ id: `S${s}`, label: `SU${s}\n${per[s - 1]} × ${p.short}`, tier: 2, kind: "systems", count: per[s - 1] });
      sn.push({ id: `sl${s}`, label: `SU${s} storage leaves ×${k}`, tier: 1, kind: "leaf", count: k });
      se.push({ s: `S${s}`, t: `sl${s}`, n: 2 * per[s - 1], f: "storage" });
      for (let i = 1; i <= c.stSpines; i++) se.push({ s: `sl${s}`, t: "ss" + i, n: (k * 24) / c.stSpines, f: "storage" });
    }
    sn.push({ id: "sd", label: `device leaves ×${c.nDev}`, tier: 1, kind: "leaf", count: c.nDev });
    for (let i = 1; i <= c.stSpines; i++) se.push({ s: "sd", t: "ss" + i, n: ceil(c.appl * 8 / c.stSpines), f: "storage" });
    sn.push({ id: "hps", label: `storage ×${c.appl}`, tier: 2, kind: "storage", count: c.appl }, { id: "mg", label: `control ×${c.mgmt}`, tier: 2, kind: "mgmt" }, { id: "ufmS", label: "UFM (storage)", tier: 2, kind: "mgmt" });
    se.push({ s: "hps", t: "sd", n: c.appl * 8, f: "storage" }, { s: "mg", t: "sd", n: 2 * c.mgmt, f: "storage" }, { s: "ufmS", t: "sd", n: 4, f: "storage" });
    G.storage = { nodes: sn, edges: se, title: "Storage fabric" };

    const inn = [], ine = [];
    inn.push({ id: "dc", label: "DC core / edge", tier: -1, kind: "core" });
    for (let i = 1; i <= c.ibS; i++) { inn.push({ id: "is" + i, label: `in-band spine ${i}`, tier: 0, kind: "spine" }); ine.push({ s: "is" + i, t: "dc", n: 6, f: "inband" }); }
    const pairs = Math.max(1, c.ibL / 2);
    for (let k = 1; k <= pairs; k++) for (const ab of ["a", "b"]) {
      inn.push({ id: `il${k}${ab}`, label: `in-band leaf ${k}${ab}`, tier: 1, kind: "leaf" });
      for (let i = 1; i <= c.ibS; i++) ine.push({ s: `il${k}${ab}`, t: "is" + i, n: 2, f: "inband" });
    }
    for (let s = 1; s <= c.sus; s++) {
      inn.push({ id: `S${s}`, label: `SU${s}\n${per[s - 1]} × ${p.short}`, tier: 2, kind: "systems", count: per[s - 1] });
      const k = Math.min(pairs, ceil(s * pairs / c.sus));
      for (const ab of ["a", "b"]) ine.push({ s: `S${s}`, t: `il${k}${ab}`, n: per[s - 1], f: "inband" });
    }
    inn.push({ id: "mg", label: `control ×${c.mgmt}`, tier: 2, kind: "mgmt" }, { id: "oob", label: `OOB switches ×${c.oob}`, tier: 1, kind: "oob", count: c.oob });
    ine.push({ s: "mg", t: "il1a", n: c.mgmt, f: "inband" }, { s: "mg", t: "il1b", n: c.mgmt, f: "inband" });
    for (let i = 1; i <= c.ibS; i++) ine.push({ s: "oob", t: "is" + i, n: c.oob, f: "oob" });
    G.inband = { nodes: inn, edges: ine, title: "In-band + OOB" };
    return G;
  }

  // ------------------------------------------------------------------ NVL72 racks
  function nvl72(p, cfg, o) {
    const s = p.system, cp = p.compute, et = p.ethernet, sus = cfg.sus;
    const full = sus * p.racksPerSU;
    const racks = cfg.populated ? Math.max(1, Math.min(ceil(+cfg.populated / s.gpus), full)) : full;
    const trays = racks * s.trays, gpus = trays * s.gpusPerTray;
    const trayKw = (s.rackKw - s.nvsTrays * s.nvsKw) / s.trays;
    o.counts.systems = racks; o.counts.gpus = gpus; o.counts.sus = sus; o.counts.trays = trays;
    if (cfg.populated > full * s.gpus) o.flag("info", `Populate capped at ${full * s.gpus} GPUs`, `${cfg.populated} GPUs requested; ${sus} SU holds ${full * s.gpus}. Add SUs for more.`, p.ra.doc);
    if (racks < full) o.flag("info", `Partially populated: ${racks} of ${full} racks`, "Build the full SU fabric and leave the missing racks' leaf ports unused.", p.ra.doc);
    if (sus > 16) o.flag("blocker", "Beyond the RA's scale-out tables (16 SUs)", "Pick 16 SUs or fewer; larger pods need a design the RA does not size.", cp.ref);
    if (sus > cp.maxTested) o.flag("approval", `${sus} SUs is beyond the fully tested size (${cp.maxTested} SUs)`, "Counts follow the RA scale-out tables; NVIDIA validates larger pods per project.", cp.ref);
    o.add("Compute", `${p.label} rack`, `${s.trays} compute trays · ${s.nvsTrays} NVLink switch trays · ${s.shelves} power shelves`, racks, "RA", s.ref, { kind: "rack" });
    o.add("Compute", "Compute trays", `${s.gpusPerTray} × ${s.gpu}, 2 Grace CPUs`, trays, "RA", s.ref, { w: trayKw * 1000, u: 1, kind: "tray" });
    o.add("Compute", "NVLink switch trays", "2 × NVLink switch chips", racks * s.nvsTrays, "RA", s.ref, { w: s.nvsKw * 1000, u: 1, kind: "tray" });
    o.add("Compute", "Power shelves", `${s.shelfKw} kW (6 × 5.5 kW PSU)`, racks * s.shelves, "RA", s.ref);
    if (s.rackKwSrc === "choice") o.flag("info", "Rack power is an estimate", `The ${p.short} RA gives only the SU TDP (${p.suMW} MW); ${s.rackKw} kW per rack is a working figure.`, p.ra.doc);

    const leavesPerSU = (cp.rails * p.racksPerSU) / cp.racksPerLeaf;
    const leaves = sus * leavesPerSU, down = cp.racksPerLeaf * s.trays, up = down;
    let spines = cp.spines[sus], spSrc = "RA";
    if (!spines) {
      spines = spineCount(up, leaves * up, cp.ports) || ceil(leaves * up / cp.ports); spSrc = "DERIVED";
      o.flag("info", `No RA spine count for ${sus} SU`, `Derived: ${leaves} leaves × ${up} uplinks over ${cp.ports}-port spines = ${spines} (the same rule reproduces the RA's figures).`, cp.ref);
    }
    let core = cp.core[sus] || 0;
    const taper = cfg.taper === "2:1" ? 2 : 1;
    if (taper > 1) { spines = ceil(spines / 2); core = ceil(core / 2); }
    const fullLeaf = down + up >= cp.ports;
    const ufm = p.ufm.count;
    o.add("Compute fabric", `Leaf switches (${cp.rails} rails, ${leavesPerSU} per SU)`, cp.switch, leaves, "RA", cp.ref, { w: cp.w, u: cp.u, kind: "switch" });
    o.add("Compute fabric", "Spine switches", cp.switch, spines, taper > 1 ? "NON-RA" : spSrc, cp.ref, { w: cp.w, u: cp.u, kind: "switch" });
    o.add("Compute fabric", "Core switches", cp.switch, core, taper > 1 ? "NON-RA" : "RA", cp.ref, { w: cp.w, u: cp.u, kind: "switch" });
    o.add("Management", "UFM appliances", p.ufm.model, ufm, "RA", p.ufm.ref, { w: A.W.UFM, u: 1, kind: "mgmt" });
    if (fullLeaf) o.flag("info", "UFM port budget on a full leaf",
      `The RA attaches the UFM pair to compute leaves, but a ${cp.ports}-port leaf is exactly ${down} down + ${up} up. Each UFM takes one uplink, so two leaves run at ${down}:${up - 1}.`, cp.ref);
    const trayLeaf = trays * cp.rails, leafSpine = ceil((leaves * up - (fullLeaf ? ufm : 0)) / taper);
    o.counts.cables.compute = trayLeaf + leafSpine + ufm + (core ? leafSpine : 0);
    o.counts.cables.nvlink = racks * s.trays * s.nvsTrays;
    o.add("Cables", "Compute: tray → rail leaf", cp.cable, trayLeaf, "RA", cp.ref);
    o.add("Cables", "Compute: leaf → spine", cp.cable, leafSpine, taper > 1 ? "NON-RA" : "DERIVED", cp.ref);
    o.add("Cables", "Compute: spine → core", cp.cable, core ? leafSpine : 0, "DERIVED", cp.ref);
    o.add("Cables", "Compute: UFM → leaf", cp.cable, ufm, "RA", p.ufm.ref);
    o.add("Cables", "NVLink: tray ↔ switch tray (in-rack spine)", "NVLink copper cartridge", o.counts.cables.nvlink, "RA", "RA 'NVLink Switch Tray' (one entry per tray/switch-tray pair)");
    o.add("Transceivers", "Compute OSFP (tray side)", cp.cable, trayLeaf, "DERIVED", `${cp.rails} per tray`);
    const ppc = cp.ports / cp.cages;
    o.add("Transceivers", "Switch OSFP (compute, ports in use)", cp.cable, ceil((trayLeaf + ufm + 2 * leafSpine + (core ? 2 * leafSpine : 0)) / ppc), "DERIVED", `ports in use / ${ppc} per cage`);

    const keyAt = (t) => { const ks = Object.keys(t).map(Number).sort((a, b) => a - b); let v = null; for (const k of ks) if (k <= sus) v = t[k]; return v; };
    const eL = sus * et.computeLeavesPerSU, sL = keyAt(et.storageLeaves) || 2, mL = et.mgmtLeaves;
    let eS = et.spines[sus], eSrc = "RA";
    if (!eS) { eS = Math.max(2, 2 * sus); eSrc = "DERIVED"; o.flag("info", `No RA Ethernet spine count for ${sus} SU`, `Using ${eS} (2 per SU, consistent with the RA's scale-out table).`, et.ref); }
    const eSS = et.superSpines[sus] || 0;
    o.add("Ethernet fabric", "Compute leaves (BlueField-3 storage + in-band)", et.switch, eL, "RA", et.ref, { w: et.w, u: 2, kind: "switch" });
    o.add("Ethernet fabric", "Storage / control leaves", et.switch, sL, et.storageLeaves[sus] ? "RA" : "DERIVED", et.ref, { w: et.w, u: 2, kind: "switch" });
    o.add("Ethernet fabric", "Management leaves", `NVIDIA ${et.mgmtLeafModel}`, mL, "RA", et.ref, { w: et.mgmtLeafModel === "SN2201" ? A.W.SN2201 : et.w, u: et.mgmtLeafModel === "SN2201" ? 1 : 2, kind: "switch" });
    o.add("Ethernet fabric", "Spines", et.switch, eS, eSrc, et.ref, { w: et.w, u: 2, kind: "switch" });
    o.add("Ethernet fabric", "Super-spines", et.switch, eSS, "RA", et.ref, { w: et.w, u: 2, kind: "switch" });
    o.add("Ethernet fabric", "OOB aggregation spines", "NVIDIA SN4600C (model: choice)", et.oobSpines, "RA", et.ref, { w: A.W.SN4600C, u: 2, kind: "switch" });
    const tierPerf = p.perf.perSU[o.workload.tier], target = tierPerf[0] * sus, appl = Math.max(2, ceil(target / APPLIANCE_READ));
    o.add("Storage", "RoCE storage appliances", `Partner-certified (${APPLIANCE_READ} GB/s read each)`, appl, "CHOICE",
      `${p.perf.ref}: "${o.workload.tier}" = ${tierPerf[0]} GB/s read per SU → ${target} GB/s`, { w: A.W.HPS, u: 2, kind: "storage" });
    const mgmt = o.add("Management", "Control-plane servers", p.mgmt.model, p.mgmt.count, p.mgmt.ref.startsWith("choice") ? "CHOICE" : "RA", p.mgmt.ref, { w: A.W.MGMT, u: 2, kind: "mgmt" });
    o.counts.cables.inband = trays * 2 + (eL + mL) * et.leafUplinks + mgmt * 2 + 4 + eS * (eSS ? 28 : 0);
    o.counts.cables.storage = appl * 8;
    o.add("Cables", "Ethernet: tray BlueField-3 → compute leaf", "400G", trays * 2, "RA", et.ref);
    o.add("Cables", "Ethernet: leaf → spine / super-spine", "400–800G", o.counts.cables.inband - trays * 2, "DERIVED", et.ref);
    o.add("Cables", "Ethernet: storage appliances", "400G", appl * 8, "CHOICE", "vendor-specific");

    const perRackOob = s.trays * 3 + s.nvsTrays * 3 + s.shelves;
    const rackOob = racks * ceil(perRackOob / o_ports(p));
    const mRacks = Math.max(3, ceil(p.racks.mgmtPerSU * sus));
    const netSw = leaves + spines + core + eL + sL + mL + eS + eSS + et.oobSpines;
    const mgPorts = netSw + mgmt + ufm + appl * 2 + mRacks * p.racks.pdusMgmt;
    const mgOob = ceil(mgPorts / o_ports(p));
    o.add("Out-of-band", "OOB switches in compute racks (2 per rack)", p.oob.switch, rackOob, "RA", p.oob.ref, { w: A.W.SN2201, u: 1, kind: "switch" });
    o.add("Out-of-band", "OOB switches for network / management", p.oob.switch, mgOob, "DERIVED", `${mgPorts} ports / 48`, { w: A.W.SN2201, u: 1, kind: "switch" });
    o.counts.cables.oob = racks * perRackOob + mgPorts + 2 * (rackOob + mgOob);
    o.add("Cables", "OOB: BMC, BlueField BMC, LOM, COMe, shelves, switches", "Cat6 1G", o.counts.cables.oob, "DERIVED", p.oob.ref);
    o.add("Racks & power", "Network / management / storage racks", "48U", mRacks, "CHOICE", "sized for switches, UFM, control plane and storage");
    o.add("Racks & power", "Power feeds for NVL72 shelves", "415 V 63 A three-phase", racks * s.shelves, "CHOICE", "one per 33 kW shelf");
    o.add("Racks & power", "Rack PDUs (network / management racks)", "Raritan PX3 series", mRacks * p.racks.pdusMgmt, "CHOICE", "3 per rack, N+1");
    o.flag("info", "NVL72 rack elevation is not in the RA", "Positions follow the common NVL72 pattern: shelves top and bottom, trays around the NVLink switch trays.", p.ra.doc);
    o.flag("info", "Control-plane and storage counts are assumptions", "The NVL72 RAs draw these in figures without a bill of materials; confirm with NVIDIA and the storage partner.", p.ra.doc);

    o.counts.compute = { leaves, spines, core, rails: cp.rails };
    o.counts.racks = { compute: racks, mgmt: mRacks, perRack: 1, rackKw: s.rackKw, budget: p.rack.kwBudget };
    o.counts.storage = { appliances: appl, target, leaves: sL };
    const items = [];
    [2, 3, 4, 5, 33, 34, 35, 36].forEach((u, i) => items.push({ u, h: 1, label: `Power shelf ${i + 1}`, kind: "power" }));
    for (let i = 0; i < 10; i++) items.push({ u: 32 - i, h: 1, label: `Compute tray ${i + 1}`, kind: "system" });
    for (let i = 0; i < 8; i++) items.push({ u: 13 - i, h: 1, label: `Compute tray ${i + 11}`, kind: "system" });
    for (let i = 0; i < 9; i++) items.push({ u: 22 - i, h: 1, label: `NVLink switch tray ${i + 1}`, kind: "nvlink" });
    items.push({ u: 38, h: 1, label: "OOB switch a", kind: "oob" }, { u: 39, h: 1, label: "OOB switch b", kind: "oob" });
    o.racks.push({ key: "compute", title: `${p.label} rack`, count: racks, kw: s.rackKw, budget: p.rack.kwBudget, u: 48, items, note: "elevation: common NVL72 pattern (not in RA)" });
    const m = []; let top = 44;
    const put = (n, h, label, kind) => { for (let i = 0; i < n && top - h >= 1; i++) { m.push({ u: top - h + 1, h, label, kind }); top -= h; } };
    put(Math.min(cp.u > 1 ? 4 : 16, leaves), cp.u, "Compute leaf", "ib"); put(Math.min(cp.u > 1 ? 2 : 9, spines), cp.u, "Compute spine", "ib"); put(1, 1, "UFM", "mgmt");
    o.racks.push({ key: "mgmt", title: "Network / management rack", count: mRacks, kw: null, budget: 40, u: 48, items: m, note: "typical (CHOICE)" });

    // graphs
    const G = {}, cn = [], ce = [];
    const suR = []; let left = racks;
    for (let u = 1; u <= sus; u++) { const n = Math.min(p.racksPerSU, left); suR.push(n); left -= n; }
    const grpSp = spines > 18, grp = sus > 2 || leavesPerSU > 8 && sus > 1;
    if (grpSp) cn.push({ id: "sp", label: `${spines} spines`, tier: 0, kind: "spine", count: spines });
    else for (let i = 1; i <= spines; i++) cn.push({ id: "sp" + i, label: `spine ${i}`, tier: 0, kind: "spine" });
    if (core) cn.push({ id: "core", label: `${core} core`, tier: -1, kind: "core", count: core });
    for (let u = 1; u <= sus; u++) {
      if (grp) {
        cn.push({ id: `R${u}`, label: `SU${u}\n${suR[u - 1]} × NVL72`, tier: 2, kind: "systems", count: suR[u - 1] });
        for (let r = 1; r <= cp.rails; r++) { cn.push({ id: `L${u}.${r}`, label: `SU${u} rail ${r} ×${leavesPerSU / cp.rails}`, tier: 1, kind: "leaf", rail: r, count: leavesPerSU / cp.rails });
          ce.push({ s: `R${u}`, t: `L${u}.${r}`, n: suR[u - 1] * s.trays, f: "compute", rail: r }); }
      } else {
        const lpr = leavesPerSU / cp.rails;
        for (let r = 1; r <= cp.rails; r++) for (let l = 1; l <= lpr; l++) cn.push({ id: `L${u}.${r}.${l}`, label: `SU${u} R${r}-L${l}`, tier: 1, kind: "leaf", rail: r });
        for (let k = 1; k <= suR[u - 1]; k++) {
          cn.push({ id: `R${u}.${k}`, label: `SU${u} rack ${k}\n72 GPU`, tier: 2, kind: "systems" });
          const l = ceil(k / cp.racksPerLeaf);
          for (let r = 1; r <= cp.rails; r++) ce.push({ s: `R${u}.${k}`, t: `L${u}.${r}.${l}`, n: s.trays, f: "compute", rail: r });
        }
      }
    }
    const LL = cn.filter((n) => n.kind === "leaf"), SS = cn.filter((n) => n.kind === "spine");
    for (const l of LL) for (const sp of SS) ce.push({ s: l.id, t: sp.id, n: ((up / taper) * (l.count || 1)) / (grpSp ? 1 : spines), f: "compute" });
    if (core) for (const sp of SS) ce.push({ s: sp.id, t: "core", n: leafSpine / SS.length, f: "compute" });
    cn.push({ id: "ufm", label: "UFM ×2", tier: 1, kind: "mgmt" });
    ce.push({ s: "ufm", t: LL[LL.length - 1].id, n: ufm, f: "compute" });
    G.compute = { nodes: cn, edges: ce, title: "Compute fabric" };
    const nn = [], ne = [];
    for (let i = 1; i <= s.nvsTrays; i++) nn.push({ id: "nvs" + i, label: `NVLink tray ${i}`, tier: 0, kind: "spine" });
    for (let t = 1; t <= s.trays; t++) { nn.push({ id: "t" + t, label: `tray ${t}`, tier: 1, kind: "systems" }); for (let i = 1; i <= s.nvsTrays; i++) ne.push({ s: "t" + t, t: "nvs" + i, n: 1, f: "nvlink" }); }
    G.nvlink = { nodes: nn, edges: ne, title: "NVLink (one NVL72 rack)" };
    const en = [], ee = [];
    en.push({ id: "dc", label: "customer edge", tier: -2, kind: "core" });
    if (eSS) { en.push({ id: "ess", label: `super-spines ×${eSS}`, tier: -1, kind: "core", count: eSS }); ee.push({ s: "ess", t: "dc", n: 4, f: "inband" }); }
    for (let i = 1; i <= eS; i++) { en.push({ id: "es" + i, label: `Eth spine ${i}`, tier: 0, kind: "spine" }); ee.push({ s: "es" + i, t: eSS ? "ess" : "dc", n: eSS ? 28 : 1, f: "inband" }); }
    const leafSet = [];
    for (let u = 1; u <= sus; u++) leafSet.push({ id: `el${u}`, label: `SU${u} compute leaves ×${et.computeLeavesPerSU}`, up: et.leafUplinks * et.computeLeavesPerSU, f: "inband" });
    leafSet.push({ id: "esl", label: `storage leaves ×${sL}`, up: appl * 8, f: "storage-eth" }, { id: "eml", label: `mgmt leaves ×${mL}`, up: et.leafUplinks * mL, f: "inband" });
    for (const l of leafSet) { en.push({ id: l.id, label: l.label, tier: 1, kind: "leaf" }); for (let i = 1; i <= eS; i++) ee.push({ s: l.id, t: "es" + i, n: l.up / eS, f: l.f }); }
    for (let u = 1; u <= sus; u++) { en.push({ id: `T${u}`, label: `SU${u}\n${suR[u - 1] * s.trays} trays`, tier: 2, kind: "systems" }); ee.push({ s: `T${u}`, t: `el${u}`, n: suR[u - 1] * s.trays * 2, f: "storage-eth" }); }
    en.push({ id: "hps", label: `storage ×${appl}`, tier: 2, kind: "storage" }, { id: "mg", label: `control ×${mgmt}`, tier: 2, kind: "mgmt" });
    ee.push({ s: "hps", t: "esl", n: appl * 8, f: "storage-eth" }, { s: "mg", t: "eml", n: mgmt * 2, f: "inband" });
    en.push({ id: "oob", label: `OOB switches ×${rackOob + mgOob}`, tier: 1, kind: "oob" });
    ee.push({ s: "oob", t: "es1", n: 2 * (rackOob + mgOob), f: "oob" });
    G.ethernet = { nodes: en, edges: ee, title: "Ethernet (storage + in-band + OOB)" };
    o.graph = G;
  }
  const o_ports = (p) => p.oob.ports || 48;

  // ------------------------------------------------------------------ totals
  function finish(p, cfg, o) {
    const c = o.counts;
    c.switches = o.bom.filter((b) => b.kind === "switch").reduce((a, b) => a + b.qty, 0);
    c.cablesTotal = Object.values(c.cables).reduce((a, b) => a + b, 0);
    c.transceivers = o.bom.filter((b) => b.group === "Transceivers").reduce((a, b) => a + b.qty, 0);
    c.racksTotal = c.racks.compute + c.racks.mgmt;
    c.gpuMemTB = p.system.memGB ? (c.systems * p.system.memGB) / 1000 : null;
    c.fp8PF = p.system.fp8PF ? c.systems * p.system.fp8PF : null;
    const itKw = o.bom.reduce((a, b) => a + (b.w ? (b.w * b.qty) / 1000 : 0), 0);
    const computeKw = p.family === "nvl72" ? c.racks.compute * p.system.rackKw : c.systems * p.system.kw;
    const liquid = o.coolingMode === "liquid";
    const pue = +cfg.pue || (liquid ? 1.15 : o.coolingMode === "air-rdhx" ? 1.3 : 1.4);
    o.power = { itKw, computeKw, pue, pueSrc: cfg.pue ? "input" : "assumption", facilityKw: itKw * pue,
                annualMWh: (itKw * pue * 8760) / 1000 };
    o.cooling = liquid ? { mode: "Hybrid: direct liquid (compute racks) + air (network / management racks)", liquidKw: computeKw * 0.85, airKw: itKw - computeKw * 0.85, liquidSrc: "85 % liquid capture is an assumption" }
      : { mode: o.coolingMode === "air-rdhx" ? "Air, rear-door heat exchangers" : "Air", liquidKw: 0, airKw: itKw,
          cfm: p.cfmPerKw ? Math.round(itKw * p.cfmPerKw) : null, cfmPerKw: p.cfmPerKw, cfmRef: p.dc ? p.dc.doc : "" };
    if (!cfg.pue) o.flag("info", `PUE ${pue} is an assumption`, "Enter the facility's design PUE for a real energy estimate.", "not in the RA");
    if (c.racks.rackKw > c.racks.budget) o.flag("approval", "Rack power above the reference budget", `${c.racks.rackKw.toFixed(1)} kW per rack against ${c.racks.budget} kW.`, p.density ? p.density.ref : p.rack.ref);
    const rank = { blocker: 0, approval: 1, info: 2 };
    o.flags.sort((a, b) => rank[a.sev] - rank[b.sev]);
    c.flags = { blocker: o.flags.filter((f) => f.sev === "blocker").length, approval: o.flags.filter((f) => f.sev === "approval").length, info: o.flags.filter((f) => f.sev === "info").length };
    c.bomSrc = o.bom.reduce((a, b) => ((a[b.src] = (a[b.src] || 0) + 1), a), {});
    o.air = airTopology(p, o);
  }

  /** NVIDIA Air JSON (dsx-air.nvidia.com): the Ethernet slice as Cumulus VX + Ubuntu VMs, ≤ 4 spines, ≤ 8 leaves. */
  function airTopology(p, o) {
    const g = o.graph.inband || o.graph.ethernet, nodes = {}, links = [], ports = {};
    const sw = (n) => (nodes[n] = { os: "cumulus-vx-5.16.1", cpu: 2, memory: 4096, storage: 20 });
    const host = (n) => (nodes[n] = { os: "generic/ubuntu2404", cpu: 2, memory: 2048, storage: 10 });
    const port = (n) => { ports[n] = (ports[n] || 0) + 1; return (nodes[n].os.startsWith("cumulus") ? "swp" : "eth") + ports[n]; };
    const link = (a, b) => links.push([{ node: a, interface: port(a) }, { node: b, interface: port(b) }]);
    const clean = (id) => id.replace(/[^a-z0-9-]/gi, "-").toLowerCase();
    const spines = g.nodes.filter((n) => n.kind === "spine").slice(0, 4).map((n) => clean(n.id));
    const leaves = g.nodes.filter((n) => n.kind === "leaf").slice(0, 8).map((n) => clean(n.id));
    spines.forEach(sw); leaves.forEach(sw);
    leaves.forEach((l) => spines.forEach((s) => link(l, s)));
    leaves.forEach((l, i) => { const h = `server${String(i + 1).padStart(2, "0")}`; host(h); link(h, l); });
    return { format: "JSON", title: `${p.label} Ethernet slice`, ztp: null, content: { nodes, links } };
  }

  const api = { configure, DEFAULTS, spineCount };
  root.Atlas = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
