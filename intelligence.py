"""Graph intelligence on top of the Fan Journey data (Aura Graph Analytics / GDS).

    uv run intelligence.py              # segments + scores
    uv run intelligence.py segments     # 1. taste similarity + Louvain fan segments
    uv run intelligence.py score        # 2. next-best-show scores (LIKELY_TO_BUY)

1. segments: starts a 2GB Aura Graph Analytics session, projects a Fan -> Artist/Festival
   "taste" graph (headline-concert orders, festival orders, follows), runs GDS Node Similarity to find each fan's 10 most
   similar fans (written as SIMILAR_TASTE), then Louvain on that similarity graph.
   Communities with enough members become (:Segment) nodes with a profile.
2. score: for every upcoming event, ranks fans who haven't bought yet and writes the
   top matches as (:Fan)-[:LIKELY_TO_BUY {score, reasons}]->(:Event).

Both steps replace their previous output, so they are safe to re-run.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from demo import rows_of
from load import BoltRunner, McpRunner

GRAPH = "fanTaste"
SESSION = "fanTaste"  # Aura Free allows one analytics session at a time
MIN_SEGMENT_SIZE = 40
TOP_PER_EVENT = 150

CLEANUP = [
    "MATCH ()-[r:SIMILAR_TASTE]->() WITH r LIMIT 10000 DELETE r RETURN count(*) AS deleted",
    "MATCH ()-[r:IN_SEGMENT]->() WITH r LIMIT 10000 DELETE r RETURN count(*) AS deleted",
    "MATCH (s:Segment) WITH s LIMIT 10000 DETACH DELETE s RETURN count(*) AS deleted",
    "MATCH (f:Fan) WHERE f.segmentId IS NOT NULL WITH f LIMIT 10000 REMOVE f.segmentId RETURN count(*) AS deleted",
]
CLEANUP_SCORES = "MATCH ()-[r:LIKELY_TO_BUY]->() WITH r LIMIT 10000 DELETE r RETURN count(*) AS deleted"

DROP_GRAPH = f"CALL gds.graph.drop('{GRAPH}', false) YIELD graphName RETURN graphName"
START_SESSION = "CALL gds.session.getOrCreate($name, '2GB', duration({minutes: 30})) YIELD id, status RETURN id, status"
LIST_SESSIONS = "CALL gds.session.list() YIELD id, name, status RETURN id, name, status"
DELETE_SESSION = "CALL gds.session.delete($name)"

# Items a fan "likes": headliners of concerts they bought (2), festivals they bought (2), artists they follow (1).
PROJECT = f"""
CALL () {{
  MATCH (f:Fan)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event {{type: 'concert'}})<-[:PERFORMS_AT {{billing: 'headliner'}}]-(a:Artist)
  RETURN f, a AS item, 2.0 AS w
  UNION ALL
  MATCH (f:Fan)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)-[:EDITION_OF]->(fest:Festival)
  RETURN f, fest AS item, 2.0 AS w
  UNION ALL
  MATCH (f:Fan)-[:FOLLOWS]->(a:Artist)
  RETURN f, a AS item, 1.0 AS w
}}
WITH f, item, sum(w) AS weight
WITH gds.graph.project('{GRAPH}', f, item, {{
  sourceNodeLabels: labels(f), targetNodeLabels: labels(item),
  relationshipType: 'LIKES', relationshipProperties: {{weight: weight}}
}}, {{sessionId: $sessionId}}) AS g
RETURN g.nodeCount AS nodes, g.relationshipCount AS relationships"""

SIMILARITY = f"""
CALL gds.nodeSimilarity.mutate('{GRAPH}', {{
  topK: 10, similarityCutoff: 0.05, relationshipWeightProperty: 'weight',
  mutateRelationshipType: 'SIMILAR_TASTE', mutateProperty: 'score'
}})
YIELD nodesCompared, relationshipsWritten
RETURN nodesCompared, relationshipsWritten"""

LOUVAIN = f"""
CALL gds.louvain.write('{GRAPH}', {{
  nodeLabels: ['Fan'], relationshipTypes: ['SIMILAR_TASTE'], relationshipWeightProperty: 'score',
  writeProperty: 'segmentId', consecutiveIds: true, concurrency: 1
}})
YIELD communityCount, modularity
RETURN communityCount, round(modularity, 3) AS modularity"""

WRITE_SIMILAR = f"""
CALL gds.graph.relationship.write('{GRAPH}', 'SIMILAR_TASTE', 'score')
YIELD relationshipsWritten
RETURN relationshipsWritten"""

SEGMENT_CONSTRAINT = "CREATE CONSTRAINT segment_id_unique IF NOT EXISTS FOR (n:Segment) REQUIRE n.segmentId IS UNIQUE"

CREATE_SEGMENTS = """
MATCH (f:Fan) WHERE f.segmentId IS NOT NULL
WITH f.segmentId AS sid, collect(f) AS fans
WHERE size(fans) >= $minSize
CREATE (s:Segment {segmentId: sid, size: size(fans)})
WITH s, fans
UNWIND fans AS f
CREATE (f)-[:IN_SEGMENT]->(s)
RETURN count(DISTINCT s) AS segments, count(*) AS members"""

PROFILE_SEGMENTS = """
MATCH (s:Segment)
CALL (s) {
  MATCH (s)<-[:IN_SEGMENT]-(:Fan)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event {type: 'concert'})<-[:PERFORMS_AT {billing: 'headliner'}]-(a:Artist)
  WITH a, count(*) AS n ORDER BY n DESC
  RETURN collect(a.name)[..4] AS topArtists
}
CALL (s) {
  MATCH (s)<-[:IN_SEGMENT]-(:Fan)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)<-[:PERFORMS_AT {billing: 'headliner'}]-(:Artist)-[:PLAYS_GENRE]->(g:Genre)
  WITH g, count(*) AS n ORDER BY n DESC
  RETURN collect(g.name)[..3] AS topGenres
}
CALL (s) {
  MATCH (s)<-[:IN_SEGMENT]-(:Fan)-[:LIVES_IN]->(c:City)
  WITH c, count(*) AS n ORDER BY n DESC
  RETURN collect(c.name + ' ' + toString(toInteger(round(100.0 * n / s.size))) + '%')[..3] AS topCities
}
CALL (s) {
  MATCH (s)<-[:IN_SEGMENT]-(:Fan)-[:PLACED]->(o:Order)-[:FOR_EVENT]->(e:Event)
  RETURN round(sum(o.totalEur) / s.size) AS avgSpendEur,
         round(1.0 * count(o) / s.size, 1) AS ordersPerFan,
         toInteger(round(100.0 * count(CASE WHEN e.type = 'festival' THEN 1 END) / count(o))) AS festivalOrderPct
}
CALL (s) {
  MATCH (s)<-[:IN_SEGMENT]-(f:Fan)
  RETURN toInteger(round(100.0 * count(CASE WHEN f.emailOptIn THEN 1 END) / count(f))) AS optInPct,
         toInteger(round(100.0 * sum(COUNT { (f)-[:OPENED]->(:Campaign) }) / count(f))) AS opensPer100Fans
}
SET s += {topArtists: topArtists, topGenres: topGenres, topCities: topCities, avgSpendEur: avgSpendEur,
          ordersPerFan: ordersPerFan, festivalOrderPct: festivalOrderPct, optInPct: optInPct},
    s.name = coalesce(topGenres[0], 'Mixed') + ' fans · ' + coalesce(topArtists[0], 'festivals')
RETURN s.segmentId AS segmentId, s.size AS size, s.name AS name, topArtists, topGenres, topCities,
       avgSpendEur, ordersPerFan, festivalOrderPct, optInPct
ORDER BY size DESC"""

UPCOMING = "MATCH (e:Event) WHERE e.date > date() RETURN e.eventId AS eventId, e.name AS name ORDER BY e.date"

# Scores one event. Weights are hand-set (no training data); reasons explain each score.
SCORE_EVENT = """
MATCH (e:Event {eventId: $eventId})-[:HELD_AT]->(:Venue)-[:IN_CITY]->(ec:City)
WITH e, ec,
     [(a:Artist)-[:PERFORMS_AT]->(e) | a] AS performers,
     [(a:Artist)-[:PERFORMS_AT {billing: 'headliner'}]->(e) | a] AS headliners
WITH e, ec, performers, headliners,
     reduce(acc = [], h IN headliners | acc + [(h)-[:PLAYS_GENRE]->(g:Genre) WHERE NOT g IN acc | g]) AS genres
CALL () { MATCH (f:Fan) RETURN count(f) AS totalFans }
CALL (e) { MATCH (e)<-[:FOR_EVENT]-(:Order)<-[:PLACED]-(b:Fan) RETURN count(DISTINCT b) AS buyers }
CALL (e) {
  OPTIONAL MATCH (e)<-[:FOR_EVENT]-(:Order)<-[:PLACED]-(:Fan)-[:IN_SEGMENT]->(s:Segment)
  WITH s, count(s) AS n
  RETURN collect(CASE WHEN s IS NOT NULL THEN {sid: s.segmentId, rate: 1.0 * n / s.size} END) AS segRates
}
CALL (e, performers, headliners, genres) {
  MATCH (e)<-[:FOR_EVENT]-(:Order)<-[:PLACED]-(:Fan)<-[:SIMILAR_TASTE]-(f:Fan) RETURN f
  UNION
  UNWIND performers AS a MATCH (f:Fan)-[:FOLLOWS]->(a) RETURN f
  UNION
  UNWIND genres AS g MATCH (f:Fan)-[:INTERESTED_IN]->(g) RETURN f
  UNION
  UNWIND headliners AS h MATCH (f:Fan)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)<-[:PERFORMS_AT {billing: 'headliner'}]-(:Artist)-[:PLAYS_GENRE]->(g:Genre)<-[:PLAYS_GENRE]-(h) RETURN f
}
WITH DISTINCT e, ec, performers, genres, totalFans, buyers, segRates, f
WHERE NOT EXISTS { (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(e) }
CALL (f, e) {
  OPTIONAL MATCH (f)-[s:SIMILAR_TASTE]->(peer:Fan)-[:PLACED]->(:Order)-[:FOR_EVENT]->(e)
  RETURN coalesce(sum(s.score), 0.0) AS cf, count(DISTINCT peer) AS peers
}
CALL (f, genres) {
  OPTIONAL MATCH (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)<-[:PERFORMS_AT {billing: 'headliner'}]-(:Artist)-[:PLAYS_GENRE]->(g:Genre)
  RETURN CASE WHEN count(g) = 0 THEN 0.0 ELSE 1.0 * count(CASE WHEN g IN genres THEN 1 END) / count(g) END AS genreAff
}
OPTIONAL MATCH (f)-[:IN_SEGMENT]->(seg:Segment)
WITH e, ec, genres, f, cf, peers, genreAff, seg,
     [a IN performers WHERE EXISTS { (f)-[:FOLLOWS]->(a) } | a.name] AS followed,
     [g IN genres WHERE EXISTS { (f)-[:INTERESTED_IN]->(g) } | g.name] AS declared,
     EXISTS { (f)-[:LIVES_IN]->(ec) } AS local,
     EXISTS { (f)-[:LIVES_IN]->(:City {country: ec.country}) } AS sameCountry,
     EXISTS { (f)-[:PLACED]->(:Order {attended: true})-[:FOR_EVENT]->(:Event)-[:EDITION_OF]->(:Festival)<-[:EDITION_OF]-(e) } AS loyal,
     CASE WHEN buyers = 0 THEN 0.0
          ELSE coalesce([x IN segRates WHERE x.sid = seg.segmentId | x.rate][0], 0.0) / (1.0 * buyers / totalFans) END AS segLift
WITH e, ec, genres, f, peers, genreAff, seg, followed, declared, local, loyal, segLift,
     0.30 * CASE WHEN cf > 1.0 THEN 1.0 ELSE cf END
   + 0.20 * CASE WHEN size(followed) > 0 THEN 1 ELSE 0 END
   + 0.15 * genreAff
   + 0.05 * CASE WHEN size(declared) > 0 THEN 1 ELSE 0 END
   + CASE WHEN local THEN (CASE e.type WHEN 'festival' THEN 0.08 ELSE 0.15 END)
          WHEN sameCountry THEN 0.05 ELSE 0.0 END
   + 0.15 * CASE WHEN loyal THEN 1 ELSE 0 END
   + 0.10 * CASE WHEN segLift <= 1.0 THEN 0.0 WHEN segLift >= 4.0 THEN 1.0 ELSE (segLift - 1.0) / 3.0 END AS score
ORDER BY score DESC
LIMIT $topN
WITH e, f, score, [r IN [
       CASE WHEN peers > 0 THEN toString(peers) + CASE WHEN peers = 1 THEN ' fan' ELSE ' fans' END + ' with similar taste already bought tickets' END,
       CASE WHEN size(followed) > 0 THEN 'Follows ' + apoc.text.join(followed, ', ') END,
       CASE WHEN genreAff >= 0.3 THEN toString(toInteger(round(100 * genreAff))) + '% of past purchases are ' + apoc.text.join([g IN genres | g.name], '/') END,
       CASE WHEN size(declared) > 0 THEN 'Told us they like ' + apoc.text.join(declared, ', ') END,
       CASE WHEN local THEN 'Lives in ' + ec.name END,
       CASE WHEN loyal THEN 'Attended a previous edition' END,
       CASE WHEN segLift >= 1.5 THEN 'Popular in segment "' + seg.name + '" (' + toString(round(segLift, 1)) + 'x average)' END
     ] WHERE r IS NOT NULL] AS reasons
MERGE (f)-[r:LIKELY_TO_BUY]->(e)
SET r.score = toInteger(round(100 * score)), r.reasons = reasons, r.computedAt = datetime()
RETURN count(r) AS scored, max(r.score) AS best, min(r.score) AS cutoff"""


async def drain(db, statement: str) -> int:
    total = 0
    while True:
        n = rows_of(await db.write(statement))[0]["deleted"]
        total += n
        if not n:
            return total


async def start_session(db, timeout_s: int = 900) -> str:
    """Starting a session can outlast the MCP request timeout, so start it and then poll."""
    await start_session_once(db)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        session = next((s for s in rows_of(await db.read(LIST_SESSIONS)) if s["name"] == SESSION), None)
        status = session["status"] if session else "missing"
        print(f"session {SESSION}: {status}")
        if session and status.lower() == "ready":
            return session["id"]
        if not session:
            await start_session_once(db)
        await asyncio.sleep(15)
    raise SystemExit(f"Analytics session {SESSION!r} did not become ready in {timeout_s}s")


async def start_session_once(db) -> None:
    try:
        await db.write(START_SESSION, {"name": SESSION})
    except Exception as exc:  # noqa: BLE001 - an upstream timeout here is expected
        if "timeout" not in str(exc).lower():
            raise


async def segments(db) -> None:
    for statement in CLEANUP:
        await drain(db, statement)
    await db.write(DROP_GRAPH)  # before starting: dropping a session's last graph ends an implicit session
    session_id = await start_session(db)
    print("projection:", rows_of(await db.write(PROJECT, {"sessionId": session_id}))[0])
    print("similarity:", rows_of(await db.write(SIMILARITY))[0])
    print("louvain:   ", rows_of(await db.write(LOUVAIN))[0])
    print("written:   ", rows_of(await db.write(WRITE_SIMILAR))[0])
    await db.write(DROP_GRAPH)
    await db.write(DELETE_SESSION, {"name": SESSION})
    await db.write(SEGMENT_CONSTRAINT)
    print("segments:  ", rows_of(await db.write(CREATE_SEGMENTS, {"minSize": MIN_SEGMENT_SIZE}))[0])
    for row in rows_of(await db.write(PROFILE_SEGMENTS)):
        print(f"  [{row['segmentId']}] {row['size']:>4} fans  {row['name']}")
        print(f"        artists {row['topArtists']}  genres {row['topGenres']}  cities {row['topCities']}")
        print(f"        EUR {row['avgSpendEur']}/fan, {row['ordersPerFan']} orders/fan, "
              f"{row['festivalOrderPct']}% festival orders, {row['optInPct']}% opted in")


async def score(db) -> None:
    await drain(db, CLEANUP_SCORES)
    for event in rows_of(await db.read(UPCOMING)):
        result = rows_of(await db.write(SCORE_EVENT, {"eventId": event["eventId"], "topN": TOP_PER_EVENT}))
        r = result[0] if result else {"scored": 0, "best": None, "cutoff": None}
        print(f"  {event['name']:<45} scored {r['scored']:>3}  best {r['best']}  cutoff {r['cutoff']}")


async def main(step: str, via: str) -> None:
    async with (McpRunner() if via == "mcp" else BoltRunner()) as db:
        if step in ("all", "segments"):
            await segments(db)
        if step in ("all", "score"):
            await score(db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", nargs="?", choices=["all", "segments", "score"], default="all")
    parser.add_argument("--via", choices=["mcp", "bolt"], default="mcp")
    args = parser.parse_args()
    asyncio.run(main(args.step, args.via))
