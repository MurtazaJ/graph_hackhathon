// Fan Journey demo queries.
// Each query starts with a "// Qn:" title line; demo.py runs them in order.
// Parameters: $fanId (Q1) and $eventId (Q2). demo.py picks good defaults;
// in Neo4j Browser/Query set them with e.g.  :param fanId => 'F00042'

// Q1: One fan's journey - signup, emails, clicks, orders, attendance
MATCH (f:Fan {fanId: $fanId})
CALL (f) {
  RETURN datetime({date: f.signupDate}) AS at, 'SIGNED_UP' AS step, '' AS detail
  UNION ALL
  MATCH (f)-[r:RECEIVED|OPENED|CLICKED]->(c:Campaign)
  RETURN r.at AS at, type(r) AS step, c.name AS detail
  UNION ALL
  MATCH (f)-[:PLACED]->(o:Order)-[:FOR_EVENT]->(e:Event)
  RETURN datetime({date: o.orderDate}) AS at, 'ORDERED' AS step,
         e.name + ' (' + toString(o.tickets) + ' tickets, EUR ' + toString(o.totalEur) + ')' AS detail
  UNION ALL
  MATCH (f)-[:PLACED]->(o:Order {attended: true})-[:FOR_EVENT]->(e:Event)
  RETURN datetime({date: e.date}) AS at, 'ATTENDED' AS step, e.name AS detail
}
RETURN toString(date(at)) AS day, step, detail
ORDER BY at;

// Q2: Cross-sell segment for an upcoming show nobody has emailed about yet
MATCH (target:Event {eventId: $eventId})<-[:PERFORMS_AT {billing: 'headliner'}]-(artist:Artist)
MATCH (target)-[:HELD_AT]->(:Venue)-[:IN_CITY]->(showCity:City)
MATCH (artist)-[:PLAYS_GENRE]->(g:Genre)<-[:PLAYS_GENRE]-(similar:Artist)
      -[:PERFORMS_AT]->(:Event)<-[:FOR_EVENT]-(:Order)<-[:PLACED]-(f:Fan {emailOptIn: true})
WHERE similar <> artist
  AND NOT EXISTS { (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(target) }
WITH target, artist, showCity, f, collect(DISTINCT similar.name) AS boughtSimilar
WITH target, f, boughtSimilar,
     EXISTS { (f)-[:FOLLOWS]->(artist) } AS followsArtist,
     EXISTS { (f)-[:LIVES_IN]->(showCity) } AS local
WITH target, f, boughtSimilar, followsArtist, local,
     size(boughtSimilar) + CASE WHEN followsArtist THEN 3 ELSE 0 END + CASE WHEN local THEN 2 ELSE 0 END AS score
RETURN target.name AS show, f.fanId AS fanId, f.firstName + ' ' + f.lastName AS fan,
       local, followsArtist, boughtSimilar[..3] AS boughtSimilarArtists, score
ORDER BY score DESC, fanId
LIMIT 15;

// Q3: Campaign performance with last-click attribution (order within 7 days of a click)
MATCH (c:Campaign)
WITH c,
     COUNT { (:Fan)-[:RECEIVED]->(c) } AS sent,
     COUNT { (:Fan)-[:OPENED]->(c) } AS opened,
     COUNT { (:Fan)-[:CLICKED]->(c) } AS clicked
OPTIONAL MATCH (f:Fan)-[click:CLICKED]->(c)-[:PROMOTES]->(:Event)<-[:FOR_EVENT]-(o:Order)<-[:PLACED]-(f)
  WHERE date(click.at) <= o.orderDate <= date(click.at) + duration({days: 7})
WITH c, sent, opened, clicked, count(o) AS orders, coalesce(sum(o.totalEur), 0) AS revenue
RETURN c.name AS campaign, c.type AS type, sent,
       round(100.0 * opened / sent, 1) AS openPct,
       round(100.0 * clicked / sent, 1) AS clickPct,
       orders, round(revenue) AS revenueEur
ORDER BY revenueEur DESC
LIMIT 10;

// Q4: Audience overlap - "fans of A over-index on B" (booking and co-marketing signal)
// lift = share of A's fans who bought B / share of all concert buyers who bought B
CALL () {
  MATCH (f:Fan) WHERE EXISTS { (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event {type: 'concert'}) }
  RETURN count(f) AS buyers
}
MATCH (a:Artist)-[:PERFORMS_AT {billing: 'headliner'}]->(:Event {type: 'concert'})<-[:FOR_EVENT]-(:Order)<-[:PLACED]-(f:Fan)
WITH buyers, a, collect(DISTINCT f) AS fans
WHERE size(fans) >= 40
WITH buyers, collect({artist: a, fans: fans}) AS audiences
UNWIND audiences AS aud
UNWIND aud.fans AS f
MATCH (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event {type: 'concert'})<-[:PERFORMS_AT {billing: 'headliner'}]-(b:Artist)
WHERE b <> aud.artist
WITH buyers, audiences, aud, b, count(DISTINCT f) AS shared
WHERE shared >= 15
WITH buyers, aud, b, shared, [x IN audiences WHERE x.artist = b | size(x.fans)][0] AS bAudience
WHERE bAudience IS NOT NULL
RETURN aud.artist.name AS fansOf, b.name AS alsoBuy, shared, size(aud.fans) AS audience,
       round(100.0 * shared / size(aud.fans), 1) AS pctOfAudience,
       round((1.0 * shared / size(aud.fans)) / (1.0 * bAudience / buyers), 2) AS lift
ORDER BY lift DESC
LIMIT 10;

// Q5: Win-back list - lapsed buyers (no order in 12 months) who still open our emails
MATCH (f:Fan)-[:PLACED]->(o:Order)
WITH f, max(o.orderDate) AS lastOrder, count(o) AS orders, sum(o.totalEur) AS lifetimeValue
WHERE lastOrder < date() - duration({months: 12})
MATCH (f)-[op:OPENED]->(:Campaign)
WHERE op.at >= datetime() - duration({days: 90})
WITH f, lastOrder, orders, lifetimeValue, count(*) AS recentOpens
RETURN f.fanId AS fanId, f.firstName + ' ' + f.lastName AS fan, toString(lastOrder) AS lastOrder, orders,
       round(lifetimeValue) AS lifetimeValueEur, recentOpens
ORDER BY lifetimeValue DESC
LIMIT 15;

// Q6: Email fatigue - fans to suppress (6+ emails in 180 days, zero opens)
MATCH (f:Fan)-[r:RECEIVED]->(:Campaign)
WHERE r.at >= datetime() - duration({days: 180})
WITH f, count(*) AS received
WHERE received >= 6
  AND NOT EXISTS { (f)-[o:OPENED]->(:Campaign) WHERE o.at >= datetime() - duration({days: 180}) }
RETURN count(f) AS fansToSuppress, round(avg(received), 1) AS avgEmailsReceived,
       collect(f.fanId)[..8] AS sample;

// Q7: Festival loyalty - attended every past edition, not yet bought the next one
MATCH (fest:Festival)<-[:EDITION_OF]-(e:Event)
WITH fest, collect(e) AS editions
WITH fest, [e IN editions WHERE e.date < date()] AS past, [e IN editions WHERE e.date >= date()] AS upcoming
WHERE size(past) >= 2
UNWIND upcoming AS next
MATCH (f:Fan)-[:PLACED]->(:Order {attended: true})-[:FOR_EVENT]->(pe:Event)
WHERE pe IN past
WITH fest, next, past, f, count(DISTINCT pe) AS attendedEditions
WHERE attendedEditions = size(past)
  AND NOT EXISTS { (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(next) }
RETURN fest.name AS festival, next.name AS nextEdition, size(past) AS pastEditions,
       count(f) AS loyalFansNotYetBought, collect(f.fanId)[..5] AS sample
ORDER BY loyalFansNotYetBought DESC;

// Q8: Profile enrichment - genre interest inferred from purchases for fans who never told us
MATCH (f:Fan)
WHERE NOT EXISTS { (f)-[:INTERESTED_IN]->(:Genre) }
MATCH (f)-[:PLACED]->(:Order)-[:FOR_EVENT]->(:Event)<-[:PERFORMS_AT {billing: 'headliner'}]-(:Artist)-[:PLAYS_GENRE]->(g:Genre)
WITH f, g, count(*) AS purchases
WHERE purchases >= 2
RETURN g.name AS inferredGenre, count(f) AS fansToEnrich
ORDER BY fansToEnrich DESC;

// Q9: Fan segments discovered by GDS (Node Similarity + Louvain) - run intelligence.py first
MATCH (s:Segment)
RETURN s.name AS segment, s.size AS fans, s.topArtists AS topArtists, s.topGenres AS topGenres,
       s.topCities AS topCities, s.avgSpendEur AS avgSpendEur, s.festivalOrderPct AS festivalOrderPct,
       s.description AS description
ORDER BY fans DESC;

// Q10: Who to target for a show - predicted buyers with reasons (LIKELY_TO_BUY)
MATCH (f:Fan)-[p:LIKELY_TO_BUY]->(e:Event {eventId: $eventId})
WHERE f.emailOptIn
OPTIONAL MATCH (f)-[:IN_SEGMENT]->(s:Segment)
RETURN e.name AS show, f.fanId AS fanId, f.firstName + ' ' + f.lastName AS fan,
       p.score AS score, s.name AS segment, p.reasons AS reasons
ORDER BY score DESC
LIMIT 15;

// Q11: Next best shows for one fan
MATCH (f:Fan {fanId: $fanId})-[p:LIKELY_TO_BUY]->(e:Event)
RETURN e.name AS show, toString(e.date) AS date, p.score AS score, p.reasons AS reasons
ORDER BY score DESC
LIMIT 5;
