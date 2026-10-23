# Project Memory: Fan Journey Graph

Working memory for anyone, human or AI agent, picking this project up. It covers the current state, decisions made and why, gotchas found, and what's next. Update it when any of these change.

*Last updated: 2026-10-23*

## Current state

- **Aura instance `c47ba44c`** contains the full Fan Journey graph and the derived intelligence:
  - Source data: 3,000 `Fan`, 8,371 `Order`, 94 `Event`, 40 `Artist`, 28 `Campaign`, plus reference data.
  - Derived: 18 `Segment` nodes (named by the agent), 28,210 `SIMILAR_TASTE`, 2,795 `IN_SEGMENT` and 5,250 `LIKELY_TO_BUY` (150 per upcoming event).
- **No analytics session is running.** The script deletes it after segmentation.
- **Claude Code** is connected to `neo4j-mcp` and `graphacademy` through `hackathon/.mcp.json`.
- **30 Neo4j skills** are installed in `hackathon/.agents/skills` and linked into `.claude/skills`.
- **Code is on GitHub:** https://github.com/MurtazaJ/graph_hackhathon (branch `main`). `fan-journey/` is its own git repo, nested untracked inside the cloned `workshop-hackathon` repo.

## Where things are

```
hackathon/
├── .mcp.json                  Claude Code MCP config (neo4j-mcp + graphacademy)
├── mcp.json                   original config (mcp-remote style; not read by Claude Code)
├── claude_desktop_config.json GraphAcademy server for Claude Desktop (belongs in %APPDATA%\Claude\)
└── workshop-hackathon/        cloned from neo4j-graphacademy/workshop-hackathon
    └── fan-journey/           ← this project
        ├── generate.py  load.py  intelligence.py  demo.py  visualize.py  mcp_client.py
        ├── queries.cypher     Q1–Q11
        ├── data/              18 CSVs (Aura Import-ready)
        └── README.md  architecture.md  prd.md  memory.md
```

## Run order

```shell
uv run generate.py              # CSVs (dates relative to today)
uv run load.py [--reset]        # into Aura via MCP
uv run intelligence.py          # segments (~3 min) + scores
uv run demo.py [n ...]          # demo queries
uv run visualize.py [--fan ID]  # graph.html
```

Re-running `intelligence.py segments` **resets the segment names and descriptions** to auto-generated ones. Afterwards, ask the agent to profile and rename them again.

## Decisions (and why)

| Decision | Why |
|---|---|
| Synthetic, fictional data (artists, venues, fans; `example.com` emails) | No real customer data at the hackathon; avoids PII and confusion with real acts |
| Dates relative to the run date | Keeps "upcoming", "lapsed" and "last 90 days" meaningful whenever the data is regenerated |
| `Order` as a node | It has its own properties and is used for attribution windows |
| Load through MCP by default, with Bolt as a fallback | The user wanted to use the MCP server, and there's no password in `.env` |
| One set of CSVs for both `load.py` and Aura Import | A single source of truth; the user asked for "data sources" |
| Taste graph uses only headliners for concerts, and the `Festival` node for festivals | Linking a festival-goer to all 12 acts on the lineup would drown out the taste signal |
| Louvain on the `SIMILAR_TASTE` graph, not on the raw bipartite graph | Cleaner fan-only clusters; artists describe segments rather than belong to them |
| Louvain `concurrency: 1` | Repeatable community IDs |
| Hand-weighted `LIKELY_TO_BUY` score with reasons | Explainability for marketers; there are no labels to train on |
| Only fans with `emailOptIn` in the targeting query (Q10) | Consent |
| Built a plain vis-network HTML page, not a UI app | Fastest way to show the graph |

## Gotchas found (also product feedback for the organisers)

1. **Claude Code reads `.mcp.json` (leading dot) in the project root, not `mcp.json`.** The workshop's `mcp.json` was ignored until it was copied over.
2. **The MCP server returns temporal values as `{}`.** Wrap dates in `toString()` in any query whose output a person or agent reads.
3. **Aura MCP requests time out after about 40 seconds** (`upstream request timeout`). Starting an AGA session takes about 2 minutes, so start it with `gds.session.getOrCreate`, then poll `gds.session.list()`.
4. **On Aura Free, `gds.graph.project` needs `{memory: '2GB'}` or `{sessionId}`** in its fifth argument. Otherwise it fails with "Either `sessionId` or `memory` parameter must be specified".
5. **An implicit AGA session is deleted when its last graph is dropped.** Drop old graphs *before* starting the session, or the `sessionId` disappears.
6. **Aura Free allows one analytics session at a time.**
7. **Newer `mcp` Python SDK versions renamed `inputSchema` to `input_schema`** (and `isError` to `is_error`). `mcp_client.py` handles both.
8. **Windows console printing** mangles "–" and umlauts unless stdout is UTF-8. `demo.py` reconfigures it.
9. **The workshop repo's root `.env` is tracked by git.** Don't put real credentials there. Use `fan-journey/.env`, which is git-ignored.
10. **The `www-authenticate` metadata points to Auth0** (`aura-mcp.eu.auth0.com`). The first `mcp-remote` run opens a browser; after that, tokens are cached in `~/.mcp-auth`.

## Open items / next steps

- [ ] Agent Memory Service integration (PRD story 11)
- [ ] Copilot system prompt and playbook for the demo
- [ ] Backtest `LIKELY_TO_BUY`, then learn the weights
- [ ] Store segment names keyed to a stable signature so they survive re-runs
- [ ] Write the feedback section in the workshop `README.md` (use the Gotchas above)
