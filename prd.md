# PRD: Fan Journey Copilot

| | |
|---|---|
| **Status** | Hackathon prototype (Neo4j Mini Agentic Hack) |
| **Owner** | Murtaza Jabalpurwala |
| **Last updated** | 2026-10-23 |

## 1. Problem

A promoter's knowledge about a fan is spread across separate systems:
- **Ticketing** holds orders.
- **Email** holds sends, opens and clicks.
- **The catalogue** holds artists, events, venues and festivals.
- **The preference centre** holds declared interests, but most fans never fill it in.

Everyday CRM questions need all of these at once:
- "Who should we email about this new show?"
- "Did that campaign actually sell tickets?"
- "Which loyal festival-goers haven't bought next year yet?"
- "Who is about to lapse?"

Today, answering them means exports, spreadsheet joins and rule-based segments that someone builds by hand. That work is slow and coarse, so targeting stays broad. Broad targeting tires out the audience, and good prospects get missed.

## 2. Solution

A **knowledge graph** connects fans, orders, events, artists, campaigns and engagement.

**Graph analytics** then adds two capabilities:
- **Automatic fan segments:** clusters of fans who buy similar things.
- **Explainable predictions:** which fan is likely to buy which upcoming show, and why.

**An AI copilot** connects to the graph through MCP. Marketers ask questions in plain English and get answers, segments and reasons back, without writing SQL or Cypher.

## 3. Users

| Persona | Need |
|---|---|
| CRM / campaign manager | Build target lists for on-sales, measure campaign impact, avoid over-mailing |
| Marketing lead | Understand the audience (segments, value, churn) and plan campaigns |
| Booking / programming | Audience overlap between artists for co-headline and lineup decisions |
| Data / BI team | One model to answer cross-system questions without bespoke pipelines |

## 4. Goals and non-goals

**Goals (hackathon)**
- Show that a graph answers cross-system CRM questions in one query.
- Show that GDS finds meaningful segments without hand-written rules.
- Produce predictions with readable reasons a marketer can trust and act on.
- Show an agent answering through Aura MCP.
- Collect feedback on the Neo4j products we used.

**Non-goals**
- Production data integration (live ticketing or SFMC feeds).
- A trained or validated propensity model.
- A dedicated UI. The agent chat and `graph.html` are enough for the demo.
- Sending campaigns, consent management, and PII handling. The data is synthetic.

## 5. User stories and scope

| # | As a… | I want to… | Status |
|---|---|---|---|
| 1 | CRM manager | see one fan's whole journey (signup, emails, orders, attendance) | **Done**: Q1, `visualize.py` |
| 2 | CRM manager | get a ranked target list for an upcoming show, with reasons | **Done**: `LIKELY_TO_BUY`, Q10 |
| 3 | CRM manager | know which campaigns drove ticket revenue | **Done**: Q3, 7-day last-click attribution |
| 4 | CRM manager | suppress fans who never open | **Done**: Q6 |
| 5 | Marketing lead | see data-driven fan segments with descriptions and actions | **Done**: 18 `Segment`s, Q9 |
| 6 | Marketing lead | find lapsed high-value fans who are still engaged | **Done**: Q5 |
| 7 | Festival team | find loyal past attendees who haven't bought the next edition | **Done**: Q7 |
| 8 | Booking team | see which artists' audiences over-index on each other | **Done**: Q4 (lift) |
| 9 | Data team | fill in missing preferences from behaviour | **Done**: Q8 |
| 10 | Any user | ask all of the above in plain English | **Done (demo)**: Claude Code + `neo4j-mcp` |
| 11 | CRM manager | have the copilot remember past decisions ("already targeted last week") | **Planned**: Agent Memory Service |
| 12 | Any user | see "next best shows" for a fan | **Done**: Q11 |

## 6. Functional requirements

1. **Data model.** Fans, orders, events, festivals (with editions), artists, genres, venues, cities and campaigns, with email engagement and follows. Every node key has a uniqueness constraint.
2. **Loading.** The same CSVs load through MCP or Bolt, and can also be uploaded to Aura Import. Loading must refuse to overwrite existing data unless explicitly told to.
3. **Segmentation.** Fans are clustered by taste using Node Similarity on purchases and follows, then Louvain. Only segments of at least 40 fans are kept. Each segment is profiled with top artists, genres and cities, spend per fan, festival share and opt-in rate. Each also has a human-readable name, description and suggested action.
4. **Predictions.** For every upcoming event, the top 150 non-buyers get a score from 0 to 100 and a list of reasons. Reasons must be readable without a data background.
5. **Agent access.** All entities, segments and predictions can be queried through the Aura MCP tools (`get-schema`, `read-cypher`). Writes go through `write-cypher`.
6. **Re-runnable.** Every pipeline step can be run again safely and replaces its previous output.

## 7. Success metrics

**Hackathon demo**
- Each of the 11 demo questions is answered correctly by the agent in one turn.
- Segment modularity is above 0.5. Achieved: 0.73.
- Every prediction carries at least one reason. Achieved: 100% of the 5,250 predictions.

**Production (if pursued)**
- Click-to-purchase conversion of graph-targeted sends versus today's rule-based segments, measured as uplift in an A/B test.
- Fewer emails per ticket sold, a proxy for fatigue.
- Time to build a campaign target list.
- Precision and recall of `LIKELY_TO_BUY` against actual purchases, from a backtest on historical on-sales.

## 8. Demo script (about 5 minutes)

1. **Problem (30 s).** Three systems, and nobody can answer "who do we target?" quickly.
2. **Graph (45 s).** Open `graph.html`: the Schema view, then one fan's journey.
3. **Ask the copilot (2 min)**, each answered live through MCP:
   - "Who should we target for Nova Kaiser Berlin 2027, and why?"
   - "Describe our fan segments. Which one is most at risk?"
   - "Which campaign drove the most revenue?"
4. **How it's intelligent (1 min).** Node Similarity, then Louvain, then segments; explainable scores.
5. **What's next and feedback (45 s).**

## 9. Risks and open questions

| Risk / question | Mitigation / note |
|---|---|
| Scores are hand-weighted, and synthetic data rediscovers the rules that generated it | Present them as explainable heuristics. Before production, backtest and learn the weights (for example GDS link prediction or a simple classifier). |
| GDPR: profiling, email consent, retention | Use only opted-in fans for targeting (Q10 filters on `emailOptIn`). A legal review is needed before using real data. |
| Real data volumes (millions of fans and emails) | Bucket email events by time and run analytics in a larger session. The model itself scales. |
| Segment instability between runs | Louvain runs with concurrency 1. Segment names should be keyed to a stable signature, not `segmentId`. |
| MCP timeout of about 40 s | Long jobs are started and then polled. Keep single statements small. |
| Where does this live long-term? | Open question: alongside SFMC, as a feature store, or as an agent tool? |

## 10. Next steps

1. Add the **Agent Memory Service** so the copilot remembers prior targeting decisions and preferences.
2. Package the copilot: a system prompt and a playbook of graph questions.
3. Backtest `LIKELY_TO_BUY` on historical events, then replace the hand-set weights with learned ones.
4. Prototype ingestion from real ticketing and email exports.
5. Write up product feedback for the organisers (see `memory.md` → Gotchas).
