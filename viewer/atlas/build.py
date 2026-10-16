#!/usr/bin/env python3
"""Build the single-file SuperPOD Fabric Atlas page: inline app.css, profiles.js, engine.js,
app.js and the NetBox as-built graphs (docs/**/topology-graph.json) into index.html.

Usage: python3 viewer/atlas/build.py      -> viewer/dist/fabric-atlas.html (the published file)
Test the engine first: node --test viewer/atlas/test.mjs
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRI = "sha512-SQebVa91Tn1DeP45Wo74monK/I9wiQg59uKc7P8vp3T7KQ9l5e8IMjZ1GJTgZehUVQt7eS61DTqldQUb1EHfnw=="  # cytoscape 3.34.3 (cdnjs)

graphs = [ROOT / "docs" / "topology-graph.json", *sorted((ROOT / "docs").glob("*/topology-graph.json"))]
asbuilt = json.dumps([json.loads(p.read_text()) for p in graphs if p.exists()], separators=(",", ":")).replace("</", "<\\/")
page = (HERE / "index.html").read_text()
for token, name in (("/*__CSS__*/", "app.css"), ("/*__PROFILES__*/", "profiles.js"), ("/*__ENGINE__*/", "engine.js"), ("/*__APP__*/", "app.js")):
    body = (HERE / name).read_text()
    assert "</script" not in body.lower() and "</style" not in body.lower(), name
    page = page.replace(token, body)
page = page.replace("__SRI__", SRI).replace("__ASBUILT__", asbuilt)
out = ROOT / "viewer" / "dist" / "fabric-atlas.html"
out.parent.mkdir(exist_ok=True)
out.write_text(page)
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KiB)")
