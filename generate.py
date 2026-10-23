"""Deterministic synthetic data for the Fan Journey graph.

All artists, venues, festivals and fans are fictional. Dates are anchored to the
day the script runs, so "upcoming", "lapsed" and "last 90 days" stay meaningful.

Run directly to write the CSV files to data/ (no database needed):
    uv run generate.py
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

SEED = 42
N_FANS = 3000

# (name, country, share of fan base)
CITIES = [
    ("Berlin", "DE", 0.22),
    ("Hamburg", "DE", 0.14),
    ("Munich", "DE", 0.13),
    ("Cologne", "DE", 0.11),
    ("Frankfurt", "DE", 0.09),
    ("Leipzig", "DE", 0.08),
    ("Stuttgart", "DE", 0.08),
    ("Vienna", "AT", 0.08),
    ("Zurich", "CH", 0.07),
]

# (genre, how common it is as a fan preference)
GENRES = [
    ("Pop", 1.0),
    ("Indie Rock", 0.9),
    ("Hip-Hop", 0.85),
    ("Deutschrap", 0.7),
    ("Techno", 0.65),
    ("House", 0.5),
    ("R&B", 0.5),
    ("Metal", 0.45),
    ("Punk", 0.4),
    ("Singer-Songwriter", 0.45),
]

# (name, genres, popularity 1-100)
ARTISTS = [
    ("Nova Kaiser", ["Pop"], 95),
    ("Kiez Kollektiv", ["Deutschrap", "Hip-Hop"], 90),
    ("The Velvet Static", ["Indie Rock"], 88),
    ("Mira Solé", ["R&B", "Pop"], 84),
    ("Saint Marlowe", ["Hip-Hop", "R&B"], 82),
    ("Iron Lantern", ["Metal"], 80),
    ("Tiefdruck", ["Techno"], 78),
    ("Ostwind", ["Deutschrap"], 75),
    ("Paper Harbours", ["Indie Rock", "Singer-Songwriter"], 72),
    ("Lena Wilder", ["Pop"], 71),
    ("Neon Bassline", ["House"], 70),
    ("Lia & The Lowlights", ["Pop", "Indie Rock"], 68),
    ("Dark Matter Society", ["Techno", "House"], 66),
    ("Lukas Brandt", ["Singer-Songwriter"], 65),
    ("Block 17", ["Deutschrap", "Hip-Hop"], 64),
    ("Satellite Hearts", ["Indie Rock", "Pop"], 63),
    ("Juno Arcade", ["Pop"], 62),
    ("Pulse Cathedral", ["Techno"], 61),
    ("Glasshouse Riot", ["Punk"], 60),
    ("Yara Blue", ["R&B", "Hip-Hop"], 59),
    ("Black Fjord", ["Metal"], 58),
    ("MC Kurzschluss", ["Deutschrap"], 57),
    ("The Hollow Pines", ["Indie Rock"], 55),
    ("Amber Coast", ["Singer-Songwriter", "Pop"], 54),
    ("Rosa Vandal", ["Punk", "Indie Rock"], 52),
    ("Elbtunnel", ["Techno"], 50),
    ("Velour", ["R&B"], 48),
    ("Concrete Choir", ["Hip-Hop"], 47),
    ("Morning Atlas", ["Singer-Songwriter", "Indie Rock"], 46),
    ("Kollaps Kids", ["Punk"], 45),
    ("Hammerhai", ["Metal", "Punk"], 44),
    ("Sunday Arsonists", ["Indie Rock", "Punk"], 43),
    ("Grave Cartel", ["Metal"], 42),
    ("Silk Verdict", ["R&B"], 41),
    ("Dub Kolonie", ["House", "Techno"], 40),
    ("The Kerosene Saints", ["Punk"], 39),
    ("Fernweh", ["Singer-Songwriter"], 38),
    ("Club Mondschein", ["House"], 36),
    ("Static Bloom", ["Indie Rock"], 35),
    ("Nachtfalter", ["Techno"], 33),
]

# (venueId, name, city, capacity, kind)
VENUES = [
    ("V01", "Spreeufer Arena", "Berlin", 14000, "arena"),
    ("V02", "Kranhalle", "Berlin", 2500, "hall"),
    ("V03", "Club Lichtblick", "Berlin", 700, "club"),
    ("V04", "Hafenhalle", "Hamburg", 3500, "hall"),
    ("V05", "Kiezkeller", "Hamburg", 600, "club"),
    ("V06", "Isar Dome", "Munich", 12000, "arena"),
    ("V07", "Backstube", "Munich", 900, "club"),
    ("V08", "Rheinwerk", "Cologne", 4000, "hall"),
    ("V09", "Domkeller", "Cologne", 550, "club"),
    ("V10", "Mainhalle", "Frankfurt", 3000, "hall"),
    ("V11", "Lindenwerk", "Leipzig", 1800, "hall"),
    ("V12", "Neckar Arena", "Stuttgart", 9000, "arena"),
    ("V13", "Donaukanal Halle", "Vienna", 3200, "hall"),
    ("V14", "Limmatwerk", "Zurich", 1200, "club"),
    ("V15", "Elbwiesen Festivalgelände", "Hamburg", 45000, "open_air"),
    ("V16", "Isarauen Gelände", "Munich", 40000, "open_air"),
    ("V17", "Pleißewiesen", "Leipzig", 30000, "open_air"),
]

# (festivalId, name, venueId, month, day, genre focus)
FESTIVALS = [
    ("FEST1", "Nordlicht Festival", "V15", 6, 20, ["Indie Rock", "Punk", "Pop", "Singer-Songwriter"]),
    ("FEST2", "Isarwelle Open Air", "V16", 7, 18, ["Hip-Hop", "Deutschrap", "R&B", "Pop"]),
    ("FEST3", "Tiefgrün Festival", "V17", 8, 8, ["Techno", "House"]),
]

FIRST_NAMES = [
    "Anna", "Ben", "Clara", "David", "Elif", "Felix", "Greta", "Hannah", "Ilias", "Jana",
    "Jonas", "Lea", "Leon", "Lina", "Luca", "Maja", "Max", "Mia", "Noah", "Paul",
    "Sara", "Tim", "Yusuf", "Zoe", "Emil", "Ida", "Moritz", "Nina", "Ole", "Pia",
    "Rafael", "Sophie", "Tom", "Vera", "Aylin", "Finn", "Lara", "Milan", "Nora", "Theo",
]
LAST_NAMES = [
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz", "Hoffmann",
    "Koch", "Richter", "Klein", "Wolf", "Neumann", "Schwarz", "Braun", "Zimmermann", "Krüger", "Hartmann",
    "Lange", "Werner", "Krause", "Lehmann", "Köhler", "Yilmaz", "Kaya", "Novak", "Huber", "Gruber",
    "Bauer", "Steiner", "Frei", "Keller", "Brunner", "Lorenz", "Vogel", "Jung", "Roth", "Engel",
]
AGE_BANDS = [("18-24", 0.24), ("25-34", 0.34), ("35-44", 0.21), ("45-54", 0.13), ("55+", 0.08)]

CONCERT_BUYERS = {"club": (15, 40), "hall": (35, 90), "arena": (90, 200)}
PRICE_RANGE = {"club": (25, 45), "hall": (45, 75), "arena": (70, 130), "open_air": (190, 260)}


def _ascii(s: str) -> str:
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e")):
        s = s.replace(a, b)
    return s


def _at(rng: random.Random, d: date) -> datetime:
    """A daytime UTC timestamp on day d."""
    return datetime.combine(d, time(rng.randint(8, 19), rng.randint(0, 59)), tzinfo=timezone.utc)


def _weighted_sample(rng: random.Random, weights: dict[str, float], k: int) -> list[str]:
    """k keys without replacement, proportional to weight (Efraimidis-Spirakis)."""
    keyed = [(rng.random() ** (1.0 / w), key) for key, w in weights.items() if w > 0]
    keyed.sort(reverse=True)
    return [key for _, key in keyed[:k]]


def generate(seed: int = SEED, today: date | None = None) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    today = today or date.today()
    now = datetime.now(timezone.utc)

    artists = [
        {"artistId": f"A{i + 1:03d}", "name": name, "genres": genres, "popularity": pop}
        for i, (name, genres, pop) in enumerate(ARTISTS)
    ]
    artist_by_id = {a["artistId"]: a for a in artists}
    venue_by_id = {v[0]: v for v in VENUES}
    city_country = {c: country for c, country, _ in CITIES}

    # --- Events: headline concerts, with optional support acts -------------------
    events: list[dict] = []
    performances: list[dict] = []
    editions: list[dict] = []

    def add_concert(artist: dict, venue: tuple, day: date, on_sale: date) -> dict:
        lo, hi = PRICE_RANGE[venue[4]]
        event = {
            "eventId": f"E{len(events) + 1:04d}",
            "name": f"{artist['name']} – {venue[2]} {day.year}",
            "type": "concert",
            "date": day,
            "onSaleDate": on_sale,
            "priceEur": float(rng.randint(lo, hi)),
            "venueId": venue[0],
        }
        events.append(event)
        performances.append({"artistId": artist["artistId"], "eventId": event["eventId"], "billing": "headliner"})
        if rng.random() < 0.45:
            support = [
                a for a in artists
                if a["popularity"] < artist["popularity"] and set(a["genres"]) & set(artist["genres"])
            ]
            if support:
                pick = rng.choice(support)
                performances.append({"artistId": pick["artistId"], "eventId": event["eventId"], "billing": "support"})
        return event

    indoor = [v for v in VENUES if v[4] != "open_air"]
    for artist in artists:
        pop = artist["popularity"]
        if pop >= 80:
            kinds, kind_w = ["arena", "hall"], [0.6, 0.4]
        elif pop >= 55:
            kinds, kind_w = ["hall", "club"], [0.7, 0.3]
        else:
            kinds, kind_w = ["club", "hall"], [0.8, 0.2]
        used_cities: set[str] = set()
        for _ in range(rng.randint(1, 3) + (1 if pop >= 70 else 0)):
            kind = rng.choices(kinds, kind_w)[0]
            options = [v for v in indoor if v[4] == kind and v[2] not in used_cities]
            if not options:
                continue
            venue = rng.choice(options)
            used_cities.add(venue[2])
            day = today + timedelta(days=rng.randint(-640, 270))
            add_concert(artist, venue, day, day - timedelta(days=rng.randint(100, 220)))

    # The demo's "nobody has marketed this yet" show: the biggest artist's next arena date.
    focus_event = add_concert(
        artists[0], venue_by_id["V01"], today + timedelta(days=120), today - timedelta(days=30)
    )
    performances = [p for p in performances if not (p["eventId"] == focus_event["eventId"] and p["billing"] == "support")]

    # --- Festivals: three editions each (last year, this year, next year) --------
    festivals = [{"festivalId": f[0], "name": f[1]} for f in FESTIVALS]
    festival_editions: dict[str, list[dict]] = {}
    for fest_id, fest_name, venue_id, month, day_of_month, focus in FESTIVALS:
        festival_editions[fest_id] = []
        for year in (today.year - 1, today.year, today.year + 1):
            day = date(year, month, day_of_month)
            lo, hi = PRICE_RANGE["open_air"]
            event = {
                "eventId": f"E-{fest_id}-{year}",
                "name": f"{fest_name} {year}",
                "type": "festival",
                "date": day,
                "onSaleDate": date(year - 1, 10, 1),
                "priceEur": float(rng.randint(lo, hi)),
                "venueId": venue_id,
            }
            events.append(event)
            editions.append({"eventId": event["eventId"], "festivalId": fest_id, "year": year})
            festival_editions[fest_id].append(event)
            weights = {
                a["artistId"]: a["popularity"] * (1.0 if set(a["genres"]) & set(focus) else 0.08)
                for a in artists
            }
            lineup = _weighted_sample(rng, weights, 12 if day < today else 8)  # next year: partly announced
            lineup.sort(key=lambda aid: -artist_by_id[aid]["popularity"])
            for rank, aid in enumerate(lineup):
                performances.append(
                    {"artistId": aid, "eventId": event["eventId"], "billing": "headliner" if rank < 3 else "support"}
                )

    performers: dict[str, list[str]] = {}
    for p in performances:
        performers.setdefault(p["eventId"], []).append(p["artistId"])

    def event_genres(event: dict) -> set[str]:
        return {g for aid in performers[event["eventId"]] for g in artist_by_id[aid]["genres"]}

    # --- Fans ------------------------------------------------------------------------
    fans: list[dict] = []
    profile: dict[str, dict] = {}  # hidden behavioural traits that drive the simulation
    interests: list[dict] = []
    follows: list[dict] = []
    city_names, city_w = [c[0] for c in CITIES], [c[2] for c in CITIES]
    genre_names, genre_w = [g[0] for g in GENRES], [g[1] for g in GENRES]

    for i in range(N_FANS):
        fan_id = f"F{i + 1:05d}"
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        signup = today - timedelta(days=rng.randint(30, 1280))
        prefs: dict[str, float] = {}
        for weight in (1.0, 0.6, 0.35)[: rng.choices([1, 2, 3], [0.35, 0.45, 0.2])[0]]:
            remaining = [g for g in genre_names if g not in prefs]
            prefs[rng.choices(remaining, [genre_w[genre_names.index(g)] for g in remaining])[0]] = weight
        lapsed = rng.random() < 0.2
        fan = {
            "fanId": fan_id,
            "firstName": first,
            "lastName": last,
            "email": f"{_ascii(first).lower()}.{_ascii(last).lower()}{i + 1}@example.com",
            "city": rng.choices(city_names, city_w)[0],
            "ageBand": rng.choices([a for a, _ in AGE_BANDS], [w for _, w in AGE_BANDS])[0],
            "signupDate": signup,
            "emailOptIn": rng.random() < 0.82,
        }
        fans.append(fan)
        profile[fan_id] = {
            "prefs": prefs,
            "activity": rng.betavariate(1.5, 4.0),
            "engagement": rng.betavariate(1.6, 3.0) * (0.7 if lapsed else 1.0),
            "activeUntil": today - timedelta(days=rng.randint(380, 640)) if lapsed else None,
            "follows": set(),
        }
        if rng.random() < 0.6:  # only some fans fill in the preference centre
            interests.extend({"fanId": fan_id, "genre": g} for g in prefs)

        n_follows = rng.choices([0, 1, 2, 3, 5], [0.3, 0.3, 0.2, 0.12, 0.08])[0]
        if n_follows:
            weights = {
                a["artistId"]: a["popularity"] * (0.05 + max(prefs.get(g, 0) for g in a["genres"]))
                for a in artists
            }
            for aid in _weighted_sample(rng, weights, n_follows):
                profile[fan_id]["follows"].add(aid)
                since = signup + timedelta(days=rng.randint(0, max(0, (today - signup).days)))
                follows.append({"fanId": fan_id, "artistId": aid, "since": since})

    fan_by_id = {f["fanId"]: f for f in fans}

    # --- Organic ticket orders ------------------------------------------------------
    raw_orders: list[dict] = []
    bought: set[tuple[str, str]] = set()
    attended_edition: dict[str, set[str]] = {}  # eventId -> fans who attended

    def order_window(fan_id: str, event: dict, earliest: date) -> tuple[date, date] | None:
        p = profile[fan_id]
        start = max(earliest, fan_by_id[fan_id]["signupDate"])
        end = min(event["date"] - timedelta(days=1), today)
        if p["activeUntil"]:
            end = min(end, p["activeUntil"])
        return (start, end) if start <= end else None

    def add_order(fan_id: str, event: dict, day: date) -> None:
        tickets = rng.choices([1, 2, 3, 4], [0.35, 0.45, 0.12, 0.08])[0]
        order = {
            "fanId": fan_id,
            "eventId": event["eventId"],
            "orderDate": day,
            "tickets": tickets,
            "totalEur": round(tickets * event["priceEur"], 2),
            "channel": rng.choices(["web", "app", "box_office"], [0.55, 0.38, 0.07])[0],
            "attended": (rng.random() < 0.93) if event["date"] < today else None,
        }
        raw_orders.append(order)
        bought.add((fan_id, event["eventId"]))
        if order["attended"]:
            attended_edition.setdefault(event["eventId"], set()).add(fan_id)

    previous_edition = {
        e["eventId"]: eds[i - 1]["eventId"]
        for eds in festival_editions.values()
        for i, e in enumerate(eds)
        if i > 0
    }

    for event in sorted(events, key=lambda e: e["date"]):  # chronological, so festival loyalty can build up
        venue = venue_by_id[event["venueId"]]
        is_festival = event["type"] == "festival"
        if event["onSaleDate"] > today:
            continue
        headliner = artist_by_id[performers[event["eventId"]][0]]
        genres = event_genres(event)
        loyal = attended_edition.get(previous_edition.get(event["eventId"], ""), set())

        weights: dict[str, float] = {}
        for fan in fans:
            fid = fan["fanId"]
            if not order_window(fid, event, event["onSaleDate"]):
                continue
            p = profile[fid]
            score = 0.02 + max((p["prefs"].get(g, 0) for g in genres), default=0)
            if p["follows"] & set(performers[event["eventId"]]):
                score += 0.8
            if fan["city"] == venue[2]:
                city_factor = 1.0
            elif city_country[fan["city"]] == city_country[venue[2]]:
                city_factor = 0.6 if is_festival else 0.25
            else:
                city_factor = 0.3 if is_festival else 0.08
            score *= city_factor * (0.3 + p["activity"])
            score *= 4.0 if fid in loyal else 1.0
            score *= 1.0 if is_festival else headliner["popularity"] / 100
            weights[fid] = score

        if is_festival:
            k = rng.randint(280, 420)
        else:
            lo, hi = CONCERT_BUYERS[venue[4]]
            k = int(rng.randint(lo, hi) * (0.5 + headliner["popularity"] / 100))
        if event["date"] > today:  # still on sale: only part of the demand has arrived
            elapsed = (today - event["onSaleDate"]).days / max(1, (event["date"] - event["onSaleDate"]).days)
            k = int(k * min(1.0, 0.2 + elapsed))

        for fid in _weighted_sample(rng, weights, k):
            start, end = order_window(fid, event, event["onSaleDate"])
            add_order(fid, event, start + timedelta(days=int((end - start).days * rng.random() ** 2)))

    # --- Email campaigns ----------------------------------------------------------
    campaigns: list[dict] = []
    received: list[dict] = []
    opened: list[dict] = []
    clicked: list[dict] = []

    def targeted_window(event: dict) -> tuple[date, date] | None:
        start = max(event["onSaleDate"], today - timedelta(days=540))
        end = min(event["date"] - timedelta(days=7), today - timedelta(days=1))
        return (start, end) if start <= end else None

    candidates = [
        e for e in events
        if e["eventId"] != focus_event["eventId"]
        and targeted_window(e)
        and (e["type"] == "festival" or artist_by_id[performers[e["eventId"]][0]]["popularity"] >= 50)
    ]
    plans = []
    for event in rng.sample(candidates, min(20, len(candidates))):
        start, end = targeted_window(event)
        sent = _at(rng, start + timedelta(days=rng.randint(0, (end - start).days)))
        if event["type"] == "festival":
            name, subject = f"Lineup drop: {event['name']}", f"The first names for {event['name']} are here"
        else:
            name, subject = f"On sale: {event['name']}", f"Tickets for {event['name']} are on sale now"
        plans.append(("targeted", name, subject, sent, [event]))

    for months_back in range(8):  # monthly newsletter
        month_start = date(today.year, today.month, 1)
        for _ in range(months_back):
            month_start = (month_start - timedelta(days=1)).replace(day=1)
        sent_day = month_start.replace(day=5)
        if sent_day >= today:
            continue
        sent = _at(rng, sent_day)
        upcoming = [
            e for e in events
            if e["onSaleDate"] <= sent_day < e["date"] and e["eventId"] != focus_event["eventId"]
        ]
        upcoming.sort(key=lambda e: -artist_by_id[performers[e["eventId"]][0]]["popularity"])
        plans.append(
            ("newsletter", f"Newsletter {sent_day:%B %Y}", f"Your {sent_day:%B} live music picks", sent, upcoming[:3])
        )

    plans.sort(key=lambda plan: plan[3])
    for n, (kind, name, subject, sent, promoted) in enumerate(plans, start=1):
        if not promoted:
            continue
        campaign_id = f"C{n:03d}"
        campaigns.append(
            {
                "campaignId": campaign_id,
                "name": name,
                "type": kind,
                "subject": subject,
                "sentAt": sent,
                "eventIds": [e["eventId"] for e in promoted],
            }
        )
        promoted_artists = {aid for e in promoted for aid in performers[e["eventId"]]}
        promoted_genres = {g for e in promoted for g in event_genres(e)}
        past_buyers_of_artists = {
            o["fanId"] for o in raw_orders
            if o["orderDate"] < sent.date() and set(performers[o["eventId"]]) & promoted_artists
        }

        for fan in fans:
            fid, p = fan["fanId"], profile[fan["fanId"]]
            if not fan["emailOptIn"] or fan["signupDate"] > sent.date():
                continue
            if kind == "targeted":
                relevant = (
                    set(p["prefs"]) & promoted_genres
                    or p["follows"] & promoted_artists
                    or fid in past_buyers_of_artists
                )
                if not relevant or all((fid, e["eventId"]) in bought for e in promoted):
                    continue
            received.append({"fanId": fid, "campaignId": campaign_id, "at": sent})

            if rng.random() >= 0.04 + 0.55 * p["engagement"]:
                continue
            open_at = sent + timedelta(hours=min(96.0, rng.expovariate(1 / 8)))
            if open_at > now:
                continue
            opened.append({"fanId": fid, "campaignId": campaign_id, "at": open_at})

            if rng.random() >= 0.12 + 0.4 * p["engagement"]:
                continue
            click_at = open_at + timedelta(minutes=rng.randint(0, 30))
            clicked.append({"fanId": fid, "campaignId": campaign_id, "at": click_at})

            # Some clicks turn into an order within a few days.
            for event in promoted:
                if (fid, event["eventId"]) in bought or event["onSaleDate"] > click_at.date():
                    continue
                chance = 0.18 + 0.2 * max((p["prefs"].get(g, 0) for g in event_genres(event)), default=0)
                if p["follows"] & set(performers[event["eventId"]]):
                    chance += 0.25
                if rng.random() >= chance:
                    continue
                window = order_window(fid, event, click_at.date())
                if window:
                    start, end = window
                    add_order(fid, event, min(end, start + timedelta(days=rng.choice([0, 0, 0, 1, 2, 3, 5]))))
                break

    raw_orders.sort(key=lambda o: (o["orderDate"], o["fanId"]))
    orders = [{"orderId": f"O{i + 1:06d}", **o} for i, o in enumerate(raw_orders)]

    return {
        "cities": [{"name": c, "country": country} for c, country, _ in CITIES],
        "genres": [{"name": g} for g, _ in GENRES],
        "artists": artists,
        "venues": [
            {"venueId": v[0], "name": v[1], "city": v[2], "capacity": v[3], "kind": v[4]} for v in VENUES
        ],
        "festivals": festivals,
        "events": events,
        "editions": editions,
        "performances": performances,
        "fans": fans,
        "interests": interests,
        "follows": follows,
        "orders": orders,
        "campaigns": campaigns,
        "received": received,
        "opened": opened,
        "clicked": clicked,
    }


# CSV files for Aura Import "Data sources" (and for load.py).
# file name -> (dataset key, columns). Node files also carry the foreign keys
# needed to map their relationships (e.g. events.csv has venueId for HELD_AT).
CSV_FILES = {
    "cities.csv": ("cities", ["name", "country"]),
    "genres.csv": ("genres", ["name"]),
    "artists.csv": ("artists", ["artistId", "name", "popularity"]),
    "venues.csv": ("venues", ["venueId", "name", "city", "capacity", "kind"]),
    "festivals.csv": ("festivals", ["festivalId", "name"]),
    "events.csv": ("events", ["eventId", "name", "type", "date", "onSaleDate", "priceEur", "venueId"]),
    "fans.csv": ("fans", ["fanId", "firstName", "lastName", "email", "city", "ageBand", "signupDate", "emailOptIn"]),
    "orders.csv": (
        "orders",
        ["orderId", "fanId", "eventId", "orderDate", "tickets", "totalEur", "channel", "attended"],
    ),
    "campaigns.csv": ("campaigns", ["campaignId", "name", "type", "subject", "sentAt"]),
    "artist_genres.csv": ("artist_genres", ["artistId", "genre"]),
    "performances.csv": ("performances", ["artistId", "eventId", "billing"]),
    "festival_editions.csv": ("editions", ["eventId", "festivalId", "year"]),
    "fan_interests.csv": ("interests", ["fanId", "genre"]),
    "fan_follows.csv": ("follows", ["fanId", "artistId", "since"]),
    "campaign_promotes.csv": ("campaign_promotes", ["campaignId", "eventId"]),
    "email_received.csv": ("received", ["fanId", "campaignId", "at"]),
    "email_opened.csv": ("opened", ["fanId", "campaignId", "at"]),
    "email_clicked.csv": ("clicked", ["fanId", "campaignId", "at"]),
}


def _csv_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def write_csv(data: dict[str, list[dict]], out_dir) -> None:
    import csv
    from pathlib import Path

    tables = dict(data)
    tables["artist_genres"] = [{"artistId": a["artistId"], "genre": g} for a in data["artists"] for g in a["genres"]]
    tables["campaign_promotes"] = [
        {"campaignId": c["campaignId"], "eventId": eid} for c in data["campaigns"] for eid in c["eventIds"]
    ]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for file_name, (key, columns) in CSV_FILES.items():
        with open(out / file_name, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            writer.writerows([_csv_value(row[c]) for c in columns] for row in tables[key])


if __name__ == "__main__":
    from pathlib import Path

    data = generate()
    out_dir = Path(__file__).parent / "data"
    write_csv(data, out_dir)
    for key, rows in data.items():
        print(f"{key:>13}: {len(rows):>6}")
    today = date.today()
    print()
    print("upcoming events:", sum(e["date"] >= today for e in data["events"]))
    print("orders by channel:", dict(Counter(o["channel"] for o in data["orders"])))
    print("campaign types:", dict(Counter(c["type"] for c in data["campaigns"])))
    print(f"\nwrote {len(CSV_FILES)} CSV files to {out_dir}")
