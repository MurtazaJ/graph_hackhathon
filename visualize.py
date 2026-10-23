"""Build an interactive graph view (graph.html) from the live database and open it.

    uv run visualize.py                 # schema + journey of the demo fan
    uv run visualize.py --fan F00042    # journey of another fan
    uv run visualize.py --via bolt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import webbrowser
from pathlib import Path

from demo import PICK_FAN, rows_of
from load import BoltRunner, McpRunner

OUT = Path(__file__).parent / "graph.html"

SCHEMA_RELS = """
MATCH (a)-[r]->(b)
RETURN labels(a)[0] AS source, type(r) AS type, labels(b)[0] AS target, count(*) AS count"""
SCHEMA_NODES = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"

# Temporal values are stringified because the MCP server can't serialize them.
JOURNEY = """
MATCH (f:Fan {fanId: $fanId})
CALL (f) {
  MATCH p = (f)-[:LIVES_IN|FOLLOWS|INTERESTED_IN]->() RETURN p
  UNION
  MATCH p = (f)-[:FOLLOWS]->(:Artist)-[:PLAYS_GENRE]->(:Genre) RETURN p
  UNION
  MATCH p = (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)-[:HELD_AT]->(:Venue)-[:IN_CITY]->(:City) RETURN p
  UNION
  MATCH p = (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)<-[:PERFORMS_AT {billing: 'headliner'}]-(:Artist)-[:PLAYS_GENRE]->(:Genre) RETURN p
  UNION
  MATCH p = (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)-[:EDITION_OF]->(:Festival) RETURN p
  UNION
  MATCH p = (f)-[:RECEIVED|OPENED|CLICKED]->(:Campaign)-[:PROMOTES]->(:Event) RETURN p
}
UNWIND relationships(p) AS r
WITH DISTINCT r
WITH r, startNode(r) AS a, endNode(r) AS b
RETURN elementId(a) AS sourceId, labels(a)[0] AS sourceLabel,
       a {.*, date: toString(a.date), onSaleDate: toString(a.onSaleDate), orderDate: toString(a.orderDate),
          signupDate: toString(a.signupDate), sentAt: toString(a.sentAt)} AS sourceProps,
       type(r) AS type, r {.*, at: toString(r.at), since: toString(r.since)} AS relProps,
       elementId(b) AS targetId, labels(b)[0] AS targetLabel,
       b {.*, date: toString(b.date), onSaleDate: toString(b.onSaleDate), orderDate: toString(b.orderDate),
          signupDate: toString(b.signupDate), sentAt: toString(b.sentAt)} AS targetProps"""

EMAIL_STRENGTH = {"RECEIVED": 1, "OPENED": 2, "CLICKED": 3}


def caption(label: str, props: dict) -> str:
    if label == "Fan":
        return f"{props.get('firstName', '')} {props.get('lastName', '')}".strip()
    if label == "Order":
        return f"€{props.get('totalEur', 0):.0f} · {props.get('orderDate', '')}"
    return str(props.get("name") or props.get("campaignId") or label)


def clean(props: dict) -> dict:
    return {k: v for k, v in (props or {}).items() if v is not None and v != {}}


def build_journey(rows: list[dict]) -> dict:
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    for row in rows:
        for side in ("source", "target"):
            nid, label, props = row[f"{side}Id"], row[f"{side}Label"], clean(row[f"{side}Props"])
            nodes[nid] = {"id": nid, "label": label, "caption": caption(label, props), "props": props}
        key = (row["sourceId"], row["targetId"])
        rel_type = row["type"]
        if rel_type in EMAIL_STRENGTH:
            # Show only the furthest email step per campaign: received < opened < clicked.
            current = edges.get(key)
            if current and EMAIL_STRENGTH.get(current["type"], 0) >= EMAIL_STRENGTH[rel_type]:
                continue
        else:
            key = (*key, rel_type)
        edges[key] = {"from": row["sourceId"], "to": row["targetId"], "type": rel_type, "props": clean(row["relProps"])}
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def build_schema(node_rows: list[dict], rel_rows: list[dict]) -> dict:
    nodes = [
        {"id": r["label"], "label": r["label"], "caption": f"{r['label']}\n{r['count']:,}", "count": r["count"], "props": {"nodes": r["count"]}}
        for r in node_rows
    ]
    edges = [
        {"from": r["source"], "to": r["target"], "type": f"{r['type']}\n{r['count']:,}", "props": {"relationships": r["count"]}}
        for r in rel_rows
    ]
    return {"nodes": nodes, "edges": edges}


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Fan Journey Graph</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  :root { --bg: #0f1419; --panel: #182029; --text: #e6e9ee; --muted: #8b96a5; --line: #2a3542; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.4 system-ui, -apple-system, Segoe UI, sans-serif; background: var(--bg); color: var(--text); display: flex; height: 100vh; }
  #main { flex: 1; display: flex; flex-direction: column; }
  header { padding: 12px 16px; border-bottom: 1px solid var(--line); display: flex; gap: 16px; align-items: center; }
  h1 { font-size: 16px; margin: 0; font-weight: 600; }
  .tabs button { background: transparent; color: var(--muted); border: 1px solid var(--line); padding: 6px 12px; border-radius: 6px; cursor: pointer; font: inherit; }
  .tabs button.active { color: var(--text); border-color: #4a90d9; background: #1d2a38; }
  .hint { color: var(--muted); font-size: 12px; margin-left: auto; }
  #graph { flex: 1; }
  aside { width: 320px; border-left: 1px solid var(--line); background: var(--panel); padding: 16px; overflow-y: auto; }
  aside h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 0 0 8px; }
  .legend div { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .dot { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  table { width: 100%; border-collapse: collapse; margin-top: 4px; }
  td { padding: 4px 0; vertical-align: top; border-bottom: 1px solid var(--line); word-break: break-word; }
  td:first-child { color: var(--muted); width: 40%; padding-right: 8px; }
  #details-title { font-weight: 600; margin-bottom: 4px; }
  section + section { margin-top: 20px; }
</style>
</head>
<body>
<div id="main">
  <header>
    <h1>Fan Journey Graph</h1>
    <div class="tabs">
      <button data-view="journey" class="active">Fan journey: __FAN__</button>
      <button data-view="schema">Schema</button>
    </div>
    <span class="hint">Click a node or relationship for details · scroll to zoom · drag to move</span>
  </header>
  <div id="graph"></div>
</div>
<aside>
  <section><h2>Details</h2><div id="details-title">Nothing selected</div><table id="details"></table></section>
  <section><h2>Legend</h2><div class="legend" id="legend"></div></section>
</aside>
<script>
const DATA = __DATA__;
const COLORS = {
  Fan: "#4a90d9", Order: "#e8a33d", Event: "#d9534f", Artist: "#9b6dd6", Genre: "#5cb85c",
  Venue: "#8d6e63", City: "#7f8c8d", Festival: "#e05fa0", Campaign: "#29b6c6",
};
const EDGE_COLORS = { CLICKED: "#29b6c6", OPENED: "#3d7f88", RECEIVED: "#34404d" };

document.getElementById("legend").innerHTML = Object.entries(COLORS)
  .map(([label, color]) => `<div><span class="dot" style="background:${color}"></span>${label}</div>`).join("")
  + `<div style="margin-top:8px;color:var(--muted)">Email lines: bright = clicked, mid = opened, faint = received only</div>`;

let network;
function render(view) {
  const g = DATA[view];
  const maxCount = Math.max(...g.nodes.map(n => n.count || 1));
  const nodes = g.nodes.map(n => ({
    id: n.id, label: n.caption, raw: n,
    color: { background: COLORS[n.label] || "#999", border: COLORS[n.label] || "#999",
             highlight: { background: "#fff", border: COLORS[n.label] } },
    font: { color: "#e6e9ee", size: view === "schema" ? 16 : 12, multi: false },
    shape: "dot",
    size: view === "schema" ? 14 + 30 * Math.sqrt((n.count || 1) / maxCount) : (n.label === "Fan" ? 30 : n.label === "Campaign" ? 9 : 14),
  }));
  const edges = g.edges.map((e, i) => ({
    id: i, from: e.from, to: e.to, raw: e,
    label: view === "schema" || !EDGE_COLORS[e.type] ? e.type : "",
    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
    color: { color: EDGE_COLORS[e.type] || "#55626f", highlight: "#ffffff" },
    width: e.type === "CLICKED" ? 2.5 : 1,
    font: { color: "#8b96a5", size: 10, strokeWidth: 0, align: "middle" },
    smooth: { type: "dynamic" },
  }));
  if (network) network.destroy();
  network = new vis.Network(document.getElementById("graph"),
    { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) },
    { physics: { solver: "forceAtlas2Based", forceAtlas2Based: { gravitationalConstant: view === "schema" ? -200 : -60, springLength: view === "schema" ? 200 : 90 },
                 stabilization: { iterations: 300 } },
      interaction: { hover: true, tooltipDelay: 150 } });
  network.on("click", params => {
    if (params.nodes.length) show(nodes.find(n => n.id === params.nodes[0]).raw.label, nodes.find(n => n.id === params.nodes[0]).raw.props);
    else if (params.edges.length) { const e = edges.find(x => x.id === params.edges[0]).raw; show(e.type.split("\\n")[0], e.props); }
  });
  show("Nothing selected", {});
}
function show(title, props) {
  document.getElementById("details-title").textContent = title;
  document.getElementById("details").innerHTML = Object.entries(props)
    .map(([k, v]) => `<tr><td>${k}</td><td>${Array.isArray(v) ? v.join(", ") : v}</td></tr>`).join("");
}
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("active", x === b));
  render(b.dataset.view);
});
render("journey");
</script>
</body>
</html>
"""


async def main(via: str, fan_id: str | None) -> None:
    async with (McpRunner() if via == "mcp" else BoltRunner()) as db:
        fan_id = fan_id or rows_of(await db.read(PICK_FAN))[0]["fanId"]
        journey = build_journey(rows_of(await db.read(JOURNEY, {"fanId": fan_id})))
        schema = build_schema(rows_of(await db.read(SCHEMA_NODES)), rows_of(await db.read(SCHEMA_RELS)))
    if not journey["nodes"]:
        raise SystemExit(f"No fan with fanId {fan_id!r}")
    html = HTML.replace("__DATA__", json.dumps({"journey": journey, "schema": schema})).replace("__FAN__", fan_id)
    OUT.write_text(html, encoding="utf-8")
    print(f"{fan_id}: {len(journey['nodes'])} nodes, {len(journey['edges'])} relationships -> {OUT}")
    webbrowser.open(OUT.as_uri())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fan", help="fanId to visualise (default: the demo fan)")
    parser.add_argument("--via", choices=["mcp", "bolt"], default="mcp")
    args = parser.parse_args()
    asyncio.run(main(args.via, args.fan))
