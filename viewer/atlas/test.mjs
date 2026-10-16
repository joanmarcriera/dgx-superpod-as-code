// Engine tests: every RA table row must be reproduced; key flags must fire.  node --test viewer/atlas/test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { PROFILES } = require("./profiles.js");
const { configure, spineCount } = require("./engine.js");
const bom = (r, item) => r.bom.filter((b) => b.item.startsWith(item)).reduce((a, b) => a + b.qty, 0);

test("H-series and B200 reproduce RA Table 4 (1–4 SU)", () => {
  const T = { 1: [31, 8, 4, 252, 256], 2: [63, 16, 8, 508, 512], 3: [95, 24, 16, 764, 768], 4: [127, 32, 16, 1020, 1024] };
  for (const gen of ["h100", "h200", "b200"]) for (const [s, [n, l, sp, cu, ls]] of Object.entries(T)) {
    const r = configure({ gen, sus: +s });
    assert.equal(r.counts.systems, n, `${gen} ${s}`); assert.equal(r.counts.gpus, n * 8);
    assert.equal(bom(r, "Leaf switches"), l); assert.equal(bom(r, "Spine switches"), sp);
    assert.equal(bom(r, "Compute: system") + bom(r, "Compute: UFM"), cu); assert.equal(bom(r, "Compute: leaf"), ls);
  }
});

test("the derived spine rule matches every RA row it could have produced", () => {
  assert.deepEqual([1, 2, 3, 4].map((s) => spineCount(32, s * 8 * 32, 64)), [4, 8, 16, 16]);      // H/B200 Table 4
  assert.deepEqual([1, 2, 4, 8].map((s) => spineCount(72, s * 8 * 72, 144)), [4, 8, 18, 36]);     // B300 XDR Table 3
  assert.deepEqual([1, 2, 4].map((s) => spineCount(64, s * 16 * 64, 128)), [8, 16, 32]);          // B300 Ethernet Table 3
  assert.equal(spineCount(18, 32 * 18, 64), 9);                                                    // GB200 Fig. 9
  assert.equal(spineCount(72, 8 * 72, 144), 4);                                                    // GB300 1 SU (derived)
});

test("B300 variants follow their own tables", () => {
  const x = configure({ gen: "b300x", sus: 4 });
  assert.equal(x.counts.systems, 288); assert.equal(bom(x, "Spine switches"), 18);
  const e = configure({ gen: "b300e", sus: 2 });
  assert.equal(e.counts.systems, 128); assert.equal(bom(e, "Leaf switches"), 32); assert.equal(bom(e, "Spine switches"), 16);
  assert.ok(bom(e, "Busbar power shelves") > 0);
});

test("NVL72 generations", () => {
  const g3 = configure({ gen: "gb300", sus: 1 });
  assert.equal(g3.counts.gpus, 576); assert.equal(bom(g3, "Leaf switches"), 8); assert.equal(bom(g3, "Spine switches"), 4);
  assert.ok(g3.flags.some((f) => /UFM port budget/.test(f.title) && f.sev === "info"));
  const g3b = configure({ gen: "gb300", sus: 4 });
  assert.equal(bom(g3b, "Spine switches"), 18);
  const g2 = configure({ gen: "gb200", sus: 1 });
  assert.equal(bom(g2, "Leaf switches"), 32); assert.equal(bom(g2, "Spine switches"), 9);
  assert.ok(!g2.flags.some((f) => /UFM port budget/.test(f.title)));
  const g2b = configure({ gen: "gb200", sus: 2 });
  assert.equal(bom(g2b, "Spine switches"), 48); assert.equal(bom(g2b, "Core switches"), 18);
});

test("cooling and density rules", () => {
  assert.ok(configure({ gen: "gb300", cooling: "air" }).flags.some((f) => f.sev === "blocker"));
  assert.ok(configure({ gen: "h200", cooling: "liquid" }).flags.some((f) => f.sev === "blocker"));
  assert.ok(configure({ gen: "h200", cooling: "air-rdhx" }).flags.some((f) => f.sev === "approval"));
  assert.ok(configure({ gen: "b300e", cooling: "air" }).flags.some((f) => /Plain air/.test(f.title)));
  assert.ok(configure({ gen: "h200", density: 6 }).flags.some((f) => f.sev === "blocker"));
  const d4 = configure({ gen: "h200", density: 4 });
  assert.ok(d4.flags.some((f) => f.sev === "approval" && /systems per rack/.test(f.title)));
  assert.equal(d4.counts.racks.compute, 16);
});

test("workload drives storage tier; taper is flagged", () => {
  const t = configure({ gen: "h200", workload: "training" }), i = configure({ gen: "h200", workload: "inference", taper: "2:1" });
  assert.equal(t.workload.tier, "best"); assert.equal(i.workload.tier, "good");
  assert.ok(i.flags.some((f) => /tapered/.test(f.title)));
  assert.ok(bom(i, "Spine switches") < bom(t, "Spine switches"));
  assert.ok(configure({ gen: "h200", workload: "training", storageTier: "good" }).flags.some((f) => /Storage below/.test(f.title)));
});

test("every generation and size builds without NaN and with a graph", () => {
  for (const gen of Object.keys(PROFILES)) for (const sus of [1, 2, 3, 4, 8, 16]) {
    const r = configure({ gen, sus });
    for (const b of r.bom) assert.ok(Number.isFinite(b.qty) && b.qty > 0, `${gen} ${sus} ${b.item} ${b.qty}`);
    assert.ok(Number.isFinite(r.power.itKw) && r.power.itKw > 0);
    for (const g of Object.values(r.graph)) for (const e of g.edges) {
      assert.ok(Number.isFinite(e.n) && e.n > 0, `${gen} ${sus} edge ${e.s}-${e.t} ${e.n}`);
      assert.ok(g.nodes.some((n) => n.id === e.s) && g.nodes.some((n) => n.id === e.t), `${gen} ${sus} dangling ${e.s}-${e.t}`);
    }
  }
});

test("H200 2 SU matches the NetBox build", () => {
  const r = configure({ gen: "h200", sus: 2, workload: "mixed" });
  assert.equal(r.counts.gpus, 504); assert.equal(r.counts.racks.compute, 32);
  assert.equal(bom(r, "In-band leaves") + bom(r, "In-band spines"), 6);
});

test("RA reference BOMs (independent audit, 2026-09-30)", () => {
  const e = configure({ gen: "b300e", sus: 4 });                       // B300 Ethernet RA Table 7
  assert.equal(e.counts.racks.compute + e.counts.racks.mgmt, 80);
  assert.equal(bom(e, "Rack PDUs"), 160); assert.equal(bom(e, "Busbar power shelves"), 288);
  assert.equal(bom(e, "Switch OSFP") + bom(e, "System OSFP"), 6144 + 2048);
  const b = configure({ gen: "b200", sus: 4 });                        // B200 RA Table 7
  assert.equal(b.counts.racks.compute + b.counts.racks.mgmt, 70);
  assert.equal(bom(b, "OOB switches"), 17); assert.equal(bom(b, "In-band leaves (1 GbE devices)"), 2);
  assert.equal(bom(b, "Rack PDUs"), 204);
  const h = configure({ gen: "h100", sus: 4 });                        // H100 RA Table 7
  assert.equal(h.counts.racks.compute + h.counts.racks.mgmt, 38); assert.equal(bom(h, "Rack PDUs"), 108);
  const x = configure({ gen: "b300x", sus: 8 });                       // B300 XDR RA Table 7
  assert.equal(x.counts.racks.compute + x.counts.racks.mgmt, 192); assert.equal(bom(x, "Rack PDUs"), 528);
  assert.equal(bom(x, "Switch OSFP"), 6912);
  assert.equal(bom(configure({ gen: "h200", sus: 2 }), "Rack PDUs") > 0, true);
  const src = (r, item) => r.bom.find((l) => l.item.startsWith(item)).src;
  assert.equal(src(configure({ gen: "h200", sus: 2 }), "Rack PDUs"), "DERIVED");
  assert.equal(src(configure({ gen: "b300x", sus: 4 }), "In-band leaves"), "DERIVED");
  assert.equal(src(configure({ gen: "b300e", sus: 4 }), "In-band: system links"), "DERIVED");
});

test("H200 larger pods come from its Table 3; odd inputs are safe", () => {
  const h = configure({ gen: "h200", sus: 16 });
  assert.equal(h.counts.systems, 512); assert.ok(!h.flags.some((f) => f.sev === "blocker"));
  const odd = configure({ gen: "h200", populated: "abc", density: -3, pue: 0.5 });
  assert.equal(odd.counts.systems, 63); assert.ok(odd.flags.some((f) => /PUE below 1/.test(f.title)));
  assert.ok(configure({ gen: "h200", populated: 999 }).flags.some((f) => /capped/.test(f.title)));
});
