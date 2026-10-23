# Fan Journey Graph

A CRM graph for a live-events promoter. It connects fans, ticket orders, concerts, festivals, artists and email campaigns, so you can ask questions that cut across all of them. Examples: *"which fans should we email about this show"*, *"which campaign actually sold tickets"* and *"which loyal festival-goers haven't bought next year yet"*.

All data is **synthetic and fictional**: 3,000 fans, 40 artists, 94 events, 28 campaigns and about 8,400 orders. Dates are relative to the day you generate the data.

## Model

```
(:Fan)-[:LIVES_IN]->(:City)<-[:IN_CITY]-(:Venue)<-[:HELD_AT]-(:Event)-[:EDITION_OF {year}]->(:Festival)
(:Fan)-[:PLACED]->(:Order {orderDate, tickets, totalEur, channel, attended})-[:FOR_EVENT]->(:Event)
(:Artist)-[:PERFORMS_AT {billing}]->(:Event)
(:Artist)-[:PLAYS_GENRE]->(:Genre)<-[:INTERESTED_IN]-(:Fan)
(:Fan)-[:FOLLOWS {since}]->(:Artist)
(:Campaign)-[:PROMOTES]->(:Event)
(:Fan)-[:RECEIVED|OPENED|CLICKED {at}]->(:Campaign)
```

Every node label has a uniqueness constraint on its ID (`fanId`, `eventId`, ...). `Order` is a node, not a relationship, because it has its own properties and is queried on its own.

## Run it

You need [uv](https://docs.astral.sh/uv/). It installs the Python dependencies automatically.

```shell
uv run generate.py        # writes the 18 CSV files to data/
uv run load.py            # loads them via the Aura MCP server (browser sign-in on first use)
uv run demo.py            # runs the 8 demo queries in queries.cypher
uv run demo.py 2 7        # run only Q2 and Q7
```

`load.py` refuses to run if the database already contains Fan Journey nodes. Use `--reset` to replace them.

To use the Python driver instead of MCP, copy `.env.example` to `.env`, fill in the password, and add `--via bolt`.

The MCP server URL is set in `mcp_client.py` and matches `../../mcp.json`.

## Demo queries (`queries.cypher`)

| # | Question | Why a graph helps |
|---|---|---|
| Q1 | One fan's full journey: signup, emails, clicks, orders, attendance | One traversal across CRM, ticketing and email data |
| Q2 | Cross-sell segment for an upcoming show that hasn't been marketed yet | Fan → orders → similar artists by genre → target show, ranked by follows and home city |
| Q3 | Campaign performance with 7-day last-click attribution | Joins email clicks to orders through the promoted event |
| Q4 | Audience overlap ("fans of A over-index on B", by lift) | Co-purchase patterns for booking and co-marketing |
| Q5 | Win-back list: lapsed buyers who still open emails | Buying behaviour combined with email engagement |
| Q6 | Email fatigue: fans to suppress | Many sends, no opens |
| Q7 | Festival loyalty: attended every past edition, not yet bought the next | Edition chain via `EDITION_OF` |
| Q8 | Profile enrichment: genre inferred from purchases | Fills gaps in the preference centre |
| Q9 | Fan segments discovered by GDS | Node Similarity + Louvain over taste (see below) |
| Q10 | Who to target for a show, with reasons | `LIKELY_TO_BUY` predictions |
| Q11 | Next best shows for one fan | `LIKELY_TO_BUY` predictions |

The queries also work in Neo4j Query/Browser. Set the parameters first, for example `:param fanId => 'F00114'` and `:param eventId => 'E0085'`. A coding agent connected to the Aura MCP server can run them with `read-cypher` too.

## Graph intelligence (`intelligence.py`)

```shell
uv run intelligence.py            # both steps (takes ~3 min; most of it is starting the analytics session)
uv run intelligence.py score      # only re-score (e.g. after new orders)
```

**1. Fan segments (Aura Graph Analytics).** The script starts a 2 GB analytics session (unbilled on Aura Free) and projects a taste graph. In it, each fan links to the concert headliners and festivals they bought and the artists they follow. **Node Similarity** finds each fan's 10 most similar fans, written as `(:Fan)-[:SIMILAR_TASTE {score}]->(:Fan)`. **Louvain** then clusters that similarity graph into communities. Each community with at least 40 members becomes a `(:Segment)` with a profile: top artists, genres, cities, spend per fan, share of festival orders and opt-in rate. Fans connect to it via `IN_SEGMENT`.

The current run found 18 segments with modularity 0.73, meaning strongly separated clusters. The agent then named each one and added a description and suggested action, for example *Pop Superfans*, *Lapsing R&B / Hip-Hop (Berlin)* and *Deutschrap Followers (rarely buy)*. Re-running the `segments` step resets the names to auto-generated ones.

**2. Next-best-show scores.** For every upcoming event, the script ranks fans who haven't bought a ticket yet and writes the top 150 as `(:Fan)-[:LIKELY_TO_BUY {score, reasons}]->(:Event)`. The score (0–100) combines:

| Signal | Weight |
|---|---|
| Fans with similar taste (`SIMILAR_TASTE`) already bought | 0.30 |
| Follows a performer | 0.20 |
| Share of past purchases in the event's genres | 0.15 |
| Attended a previous festival edition | 0.15 |
| Lives in the event city (same country counts less) | up to 0.15 |
| Event over-indexes in the fan's segment (lift) | 0.10 |
| Declared interest in the genre | 0.05 |

Each score comes with readable reasons, for example: *"2 fans with similar taste already bought tickets · Follows Nova Kaiser · Lives in Berlin · Popular in segment 'Pop Superfans' (4.3x average)"*. The weights are set by hand, not trained, and on synthetic data the scores mostly rediscover the rules that generated the data. Validate them against real purchase data before relying on them.

## Aura Import (alternative to load.py)

The `data/` CSVs can also be uploaded as **Data sources** in Aura's Import tool. Node files include the foreign keys their relationships need (for example `events.csv` has `venueId` for `HELD_AT`, and `orders.csv` has `fanId` and `eventId`), so you can map each relationship from a single file.

Only use one loading method per database, or you'll get duplicate nodes.
