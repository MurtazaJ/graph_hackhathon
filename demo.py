"""Run the queries in queries.cypher and print the results as tables.

    uv run demo.py              # all queries, via the Aura MCP server
    uv run demo.py 2 5          # only Q2 and Q5
    uv run demo.py --via bolt   # via the Python driver (.env)
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from load import BoltRunner, McpRunner

QUERIES = Path(__file__).parent / "queries.cypher"

# Picks the default $fanId / $eventId for Q1 / Q2.
PICK_FAN = """
MATCH (f:Fan)-[click:CLICKED]->(:Campaign)-[:PROMOTES]->(e:Event)<-[:FOR_EVENT]-(o:Order)<-[:PLACED]-(f)
WHERE date(click.at) <= o.orderDate <= date(click.at) + duration({days: 7})
WITH DISTINCT f
RETURN f.fanId AS fanId ORDER BY COUNT { (f)-[:PLACED]->() } DESC, fanId LIMIT 1"""
PICK_EVENT = """
MATCH (a:Artist)-[:PERFORMS_AT {billing: 'headliner'}]->(e:Event {type: 'concert'})
WHERE e.date > date() AND NOT EXISTS { (:Campaign)-[:PROMOTES]->(e) }
RETURN e.eventId AS eventId ORDER BY a.popularity DESC, e.date LIMIT 1"""


def parse_queries() -> list[tuple[str, str]]:
    blocks = re.split(r"^// (Q\d+: .*)$", QUERIES.read_text(encoding="utf-8"), flags=re.M)
    return [(title, body.strip().rstrip(";")) for title, body in zip(blocks[1::2], blocks[2::2])]


def rows_of(result) -> list[dict]:
    if isinstance(result, dict):
        result = next((v for v in result.values() if isinstance(v, list)), [result])
    return result if isinstance(result, list) else []


def print_table(rows: list[dict]) -> None:
    if not rows:
        print("  (no rows)")
        return
    cols = list(rows[0])
    cells = [[str(r.get(c, "")) for c in cols] for r in rows]
    widths = [min(48, max(len(c), *(len(row[i]) for row in cells))) for i, c in enumerate(cols)]
    fmt = "  " + "  ".join(f"{{:<{w}.{w}}}" for w in widths)
    print(fmt.format(*cols))
    print(fmt.format(*("-" * w for w in widths)))
    for row in cells:
        print(fmt.format(*row))


async def main(via: str, only: set[int]) -> None:
    async with (McpRunner() if via == "mcp" else BoltRunner()) as db:
        params = {
            "fanId": rows_of(await db.read(PICK_FAN))[0]["fanId"],
            "eventId": rows_of(await db.read(PICK_EVENT))[0]["eventId"],
        }
        print(f"params: {params}")
        for title, query in parse_queries():
            if only and int(title[1 : title.index(":")]) not in only:
                continue
            used = {k: v for k, v in params.items() if f"${k}" in query}
            print(f"\n=== {title}")
            print_table(rows_of(await db.read(query, used)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("only", nargs="*", type=int, help="query numbers to run (default: all)")
    parser.add_argument("--via", choices=["mcp", "bolt"], default="mcp")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # artist names contain umlauts and dashes
    asyncio.run(main(args.via, set(args.only)))
