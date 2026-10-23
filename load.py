"""Load the Fan Journey CSVs (data/) into Neo4j.

    uv run load.py                 # via the Aura MCP server (mcp-remote, see mcp_client.py)
    uv run load.py --via bolt      # via the Python driver, credentials from .env
    uv run load.py --reset         # delete existing Fan Journey nodes first

Run `uv run generate.py` first to create data/.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
BATCH = 2000

LABELS = ["City", "Genre", "Artist", "Venue", "Festival", "Event", "Fan", "Order", "Campaign"]

SCHEMA = [
    "CREATE CONSTRAINT city_name_unique IF NOT EXISTS FOR (n:City) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT genre_name_unique IF NOT EXISTS FOR (n:Genre) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT artist_id_unique IF NOT EXISTS FOR (n:Artist) REQUIRE n.artistId IS UNIQUE",
    "CREATE CONSTRAINT venue_id_unique IF NOT EXISTS FOR (n:Venue) REQUIRE n.venueId IS UNIQUE",
    "CREATE CONSTRAINT festival_id_unique IF NOT EXISTS FOR (n:Festival) REQUIRE n.festivalId IS UNIQUE",
    "CREATE CONSTRAINT event_id_unique IF NOT EXISTS FOR (n:Event) REQUIRE n.eventId IS UNIQUE",
    "CREATE CONSTRAINT fan_id_unique IF NOT EXISTS FOR (n:Fan) REQUIRE n.fanId IS UNIQUE",
    "CREATE CONSTRAINT order_id_unique IF NOT EXISTS FOR (n:Order) REQUIRE n.orderId IS UNIQUE",
    "CREATE CONSTRAINT campaign_id_unique IF NOT EXISTS FOR (n:Campaign) REQUIRE n.campaignId IS UNIQUE",
    "CREATE INDEX event_date_idx IF NOT EXISTS FOR (n:Event) ON (n.date)",
    "CREATE INDEX order_date_idx IF NOT EXISTS FOR (n:Order) ON (n.orderDate)",
]

# (csv file, statement) in dependency order: nodes first, then relationships.
LOADS = [
    ("cities.csv", """
        UNWIND $rows AS row
        MERGE (c:City {name: row.name})
        SET c.country = row.country"""),
    ("genres.csv", """
        UNWIND $rows AS row
        MERGE (:Genre {name: row.name})"""),
    ("artists.csv", """
        UNWIND $rows AS row
        MERGE (a:Artist {artistId: row.artistId})
        SET a.name = row.name, a.popularity = toInteger(row.popularity)"""),
    ("venues.csv", """
        UNWIND $rows AS row
        MERGE (v:Venue {venueId: row.venueId})
        SET v.name = row.name, v.capacity = toInteger(row.capacity), v.kind = row.kind
        WITH v, row
        MATCH (c:City {name: row.city})
        MERGE (v)-[:IN_CITY]->(c)"""),
    ("festivals.csv", """
        UNWIND $rows AS row
        MERGE (f:Festival {festivalId: row.festivalId})
        SET f.name = row.name"""),
    ("events.csv", """
        UNWIND $rows AS row
        MERGE (e:Event {eventId: row.eventId})
        SET e.name = row.name, e.type = row.type, e.date = date(row.date),
            e.onSaleDate = date(row.onSaleDate), e.priceEur = toFloat(row.priceEur)
        WITH e, row
        MATCH (v:Venue {venueId: row.venueId})
        MERGE (e)-[:HELD_AT]->(v)"""),
    ("fans.csv", """
        UNWIND $rows AS row
        MERGE (f:Fan {fanId: row.fanId})
        SET f.firstName = row.firstName, f.lastName = row.lastName, f.email = row.email,
            f.ageBand = row.ageBand, f.signupDate = date(row.signupDate),
            f.emailOptIn = toBoolean(row.emailOptIn)
        WITH f, row
        MATCH (c:City {name: row.city})
        MERGE (f)-[:LIVES_IN]->(c)"""),
    ("campaigns.csv", """
        UNWIND $rows AS row
        MERGE (c:Campaign {campaignId: row.campaignId})
        SET c.name = row.name, c.type = row.type, c.subject = row.subject, c.sentAt = datetime(row.sentAt)"""),
    ("orders.csv", """
        UNWIND $rows AS row
        MATCH (f:Fan {fanId: row.fanId})
        MATCH (e:Event {eventId: row.eventId})
        MERGE (o:Order {orderId: row.orderId})
        SET o.orderDate = date(row.orderDate), o.tickets = toInteger(row.tickets),
            o.totalEur = toFloat(row.totalEur), o.channel = row.channel,
            o.attended = toBoolean(row.attended)
        MERGE (f)-[:PLACED]->(o)
        MERGE (o)-[:FOR_EVENT]->(e)"""),
    ("artist_genres.csv", """
        UNWIND $rows AS row
        MATCH (a:Artist {artistId: row.artistId})
        MATCH (g:Genre {name: row.genre})
        MERGE (a)-[:PLAYS_GENRE]->(g)"""),
    ("performances.csv", """
        UNWIND $rows AS row
        MATCH (a:Artist {artistId: row.artistId})
        MATCH (e:Event {eventId: row.eventId})
        MERGE (a)-[r:PERFORMS_AT]->(e)
        SET r.billing = row.billing"""),
    ("festival_editions.csv", """
        UNWIND $rows AS row
        MATCH (e:Event {eventId: row.eventId})
        MATCH (f:Festival {festivalId: row.festivalId})
        MERGE (e)-[r:EDITION_OF]->(f)
        SET r.year = toInteger(row.year)"""),
    ("fan_interests.csv", """
        UNWIND $rows AS row
        MATCH (f:Fan {fanId: row.fanId})
        MATCH (g:Genre {name: row.genre})
        MERGE (f)-[:INTERESTED_IN]->(g)"""),
    ("fan_follows.csv", """
        UNWIND $rows AS row
        MATCH (f:Fan {fanId: row.fanId})
        MATCH (a:Artist {artistId: row.artistId})
        MERGE (f)-[r:FOLLOWS]->(a)
        SET r.since = date(row.since)"""),
    ("campaign_promotes.csv", """
        UNWIND $rows AS row
        MATCH (c:Campaign {campaignId: row.campaignId})
        MATCH (e:Event {eventId: row.eventId})
        MERGE (c)-[:PROMOTES]->(e)"""),
    ("email_received.csv", """
        UNWIND $rows AS row
        MATCH (f:Fan {fanId: row.fanId})
        MATCH (c:Campaign {campaignId: row.campaignId})
        MERGE (f)-[r:RECEIVED]->(c)
        SET r.at = datetime(row.at)"""),
    ("email_opened.csv", """
        UNWIND $rows AS row
        MATCH (f:Fan {fanId: row.fanId})
        MATCH (c:Campaign {campaignId: row.campaignId})
        MERGE (f)-[r:OPENED]->(c)
        SET r.at = datetime(row.at)"""),
    ("email_clicked.csv", """
        UNWIND $rows AS row
        MATCH (f:Fan {fanId: row.fanId})
        MATCH (c:Campaign {campaignId: row.campaignId})
        MERGE (f)-[r:CLICKED]->(c)
        SET r.at = datetime(row.at)"""),
]

COUNT_EXISTING = "MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) RETURN count(n) AS existing"
DELETE_BATCH = """
    MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels)
    WITH n LIMIT 5000
    DETACH DELETE n
    RETURN count(*) AS deleted"""


def read_csv(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class BoltRunner:
    def __init__(self) -> None:
        from dotenv import load_dotenv
        from neo4j import GraphDatabase

        load_dotenv(HERE / ".env")
        uri, password = os.getenv("NEO4J_URI", ""), os.getenv("NEO4J_PASSWORD", "")
        if not uri or "<" in uri or not password or "<" in password:
            sys.exit("Fill in NEO4J_URI and NEO4J_PASSWORD in fan-journey/.env first.")
        self.db = os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USERNAME", "neo4j"), password))
        self.driver.verify_connectivity()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.driver.close()

    async def read(self, query: str, params: dict | None = None) -> list[dict]:
        records, _, _ = self.driver.execute_query(query, params or {}, database_=self.db)
        return [r.data() for r in records]

    async def write(self, query: str, params: dict | None = None) -> None:
        self.driver.execute_query(query, params or {}, database_=self.db)


class McpRunner:
    """Runs Cypher through the Aura MCP server's read-cypher / write-cypher tools."""

    async def __aenter__(self):
        from mcp_client import mcp_session

        self._cm = mcp_session()
        self.session = await self._cm.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self._cm.__aexit__(*exc)

    async def _call(self, tool: str, query: str, params: dict | None) -> str:
        import json

        from mcp_client import tool_text

        args = {"query": query}
        if params:
            args["params"] = params
        text = tool_text(await self.session.call_tool(tool, args))
        return json.loads(text) if text.strip().startswith(("[", "{")) else text

    async def read(self, query: str, params: dict | None = None):
        return await self._call("read-cypher", query, params)

    async def write(self, query: str, params: dict | None = None):
        return await self._call("write-cypher", query, params)


def first_value(result, key: str) -> int:
    """Pull one number out of a tool/driver result regardless of its wrapping."""
    if isinstance(result, dict):
        result = next((v for v in result.values() if isinstance(v, list)), [result])
    if isinstance(result, list) and result and isinstance(result[0], dict) and key in result[0]:
        return int(result[0][key])
    raise RuntimeError(f"Could not read {key!r} from result: {result!r}")


async def main(via: str, reset: bool) -> None:
    if not (DATA / "fans.csv").exists():
        sys.exit("data/ is empty - run `uv run generate.py` first.")

    async with (McpRunner() if via == "mcp" else BoltRunner()) as db:
        existing = first_value(await db.read(COUNT_EXISTING, {"labels": LABELS}), "existing")
        if existing and not reset:
            sys.exit(f"Database already has {existing} nodes with Fan Journey labels. Re-run with --reset to replace them.")
        while reset and existing:
            deleted = first_value(await db.write(DELETE_BATCH, {"labels": LABELS}), "deleted")
            existing -= deleted
            print(f"deleted {deleted} nodes")
            if not deleted:
                break

        for statement in SCHEMA:
            await db.write(statement)
        print(f"schema: {len(SCHEMA)} constraints/indexes ensured")

        for file_name, statement in LOADS:
            rows = read_csv(file_name)
            for i in range(0, len(rows), BATCH):
                await db.write(statement, {"rows": rows[i : i + BATCH]})
            print(f"{file_name:>22}: {len(rows):>6} rows")

        counts = await db.read(
            "MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) "
            "RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC",
            {"labels": LABELS},
        )
        print("\nloaded:", counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--via", choices=["mcp", "bolt"], default="mcp")
    parser.add_argument("--reset", action="store_true", help="delete existing Fan Journey nodes first")
    args = parser.parse_args()
    asyncio.run(main(args.via, args.reset))
