"""
Phase 1 + Phase 2 — Decision Timing with Panchang-aware Muhurta scoring.

Combines: Bhava Bala / Antardasha strength / gochara (Phase 1) with real
Tithi/Karana/Yoga caution flags from panchang.py (Phase 2). Electional-
lagna calculation for the exact moment of action is still not built —
that requires locating auspicious Lagna-rise windows via iterative
ephemeris search, a further step beyond this.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from astrology import current_transits, compute_antardashas
from panchang import compute_panchang

ACTIVITY_HOUSES = {
    "career_change":        {"primary": [10, 6], "secondary": [2, 11]},
    "start_business":       {"primary": [10, 7], "secondary": [11, 2]},
    "relocation_travel":    {"primary": [3, 9],  "secondary": [12]},
    "marriage":             {"primary": [7],     "secondary": [2, 11]},
    "education":            {"primary": [4, 5, 9], "secondary": []},
    "financial_investment": {"primary": [2, 11], "secondary": [8]},
    "health_decision":      {"primary": [6, 8],  "secondary": [1]},
}

BENEFIC_TRANSITS = {"Jupiter", "Venus"}
MALEFIC_TRANSITS = {"Saturn", "Mars", "Rahu", "Ketu", "Sun"}


def _antardasha_at(dashas: List[Dict], at: datetime) -> Optional[Dict]:
    at_date = at.date().isoformat()
    maha = next((d for d in dashas if d["start"] <= at_date <= d["end"]), None)
    if not maha:
        return None
    for s in compute_antardashas(maha):
        s_start = datetime.strptime(s["start"], "%Y-%m-%d %H:%M:%S")
        s_end = datetime.strptime(s["end"], "%Y-%m-%d %H:%M:%S")
        if s_start <= at.replace(tzinfo=None) <= s_end:
            return s
    return None


def score_window(natal_chart: Dict, dashas: List[Dict], activity: str, at: datetime) -> Dict:
    if activity not in ACTIVITY_HOUSES:
        raise ValueError(f"Unknown activity type: {activity}")

    primary = ACTIVITY_HOUSES[activity]["primary"]
    score = 50.0
    reasons: List[str] = []

    house_lords = {h["house"]: h for h in natal_chart["house_lords"]}
    shadbala = natal_chart.get("shadbala", {})

    bala_values = [house_lords[h]["bhava_bala"]["total_rupas"] for h in primary if h in house_lords]
    if bala_values:
        avg_bala = sum(bala_values) / len(bala_values)
        all_bala = [h["bhava_bala"]["total_rupas"] for h in house_lords.values()]
        chart_avg = sum(all_bala) / len(all_bala) if all_bala else avg_bala
        if avg_bala > chart_avg:
            score += 15
            reasons.append(f"House(s) {primary} are stronger than average in your chart (Bhava Bala).")
        elif avg_bala < chart_avg * 0.7:
            score -= 10
            reasons.append(f"House(s) {primary} are weaker than average in your chart (Bhava Bala) — extra care advised.")

    antar = _antardasha_at(dashas, at)
    if antar:
        lord = antar["lord"]
        lord_strength = shadbala.get(lord, {}).get("total_rupas")
        if lord_strength is not None:
            all_strengths = [v["total_rupas"] for v in shadbala.values()]
            avg_strength = sum(all_strengths) / len(all_strengths) if all_strengths else lord_strength
            if lord_strength > avg_strength:
                score += 10
                reasons.append(f"{lord} (current Antardasha lord) is stronger than your chart's average planet strength.")

        ruling_primary = [h for h, hl in house_lords.items() if hl["lord"] == lord and h in primary]
        if ruling_primary:
            score += 15
            reasons.append(f"{lord} rules house {ruling_primary[0]}, central to this decision.")

        lord_house = next((p["house"] for p in natal_chart["planets"] if p["name"] == lord), None)
        if lord_house in primary:
            score += 10
            reasons.append(f"{lord} sits directly in house {lord_house}.")

    transits = current_transits(natal_chart, at=at)
    sun_row = next(p for p in transits["planets"] if p["name"] == "Sun")
    moon_row = next(p for p in transits["planets"] if p["name"] == "Moon")
    sun_lon = sun_row["sign_idx"] * 30 + sun_row["degree_in_sign"]
    moon_lon = moon_row["sign_idx"] * 30 + moon_row["degree_in_sign"]
    panchang = compute_panchang(sun_lon, moon_lon, at)

    for row in transits["planets"]:
        h = row.get("house_from_lagna")
        if h in primary:
            if row["name"] in BENEFIC_TRANSITS:
                score += 10
                reasons.append(f"Transiting {row['name']} is in house {h} from Lagna — supportive.")
            elif row["name"] in MALEFIC_TRANSITS:
                score -= 8
                reasons.append(f"Transiting {row['name']} is in house {h} from Lagna — proceed with more care.")

    # Panchang cautions — flat penalty per widely-agreed inauspicious factor.
    score -= 15 * len(panchang["cautions"])
    reasons.extend(panchang["cautions"])

    return {
        "date": at.date().isoformat(),
        "score": max(0, min(100, round(score, 1))),
        "reasons": reasons,
        "panchang": {k: v for k, v in panchang.items() if k != "cautions"},
    }


def find_best_windows(
    natal_chart: Dict,
    dashas: List[Dict],
    activity: str,
    days_ahead: int = 180,
    step_days: int = 3,
    threshold: int = 60,
    top_n: int = 3,
) -> List[Dict]:
    start = datetime.now(timezone.utc)
    scored = [
        score_window(natal_chart, dashas, activity, start + timedelta(days=i))
        for i in range(0, days_ahead, step_days)
    ]

    windows, current = [], None
    for r in scored:
        if r["score"] >= threshold:
            if current is None:
                current = {"start": r["date"], "end": r["date"], "scores": [], "reasons": set(), "panchangs": []}
            current["end"] = r["date"]
            current["scores"].append(r["score"])
            current["reasons"].update(r["reasons"])
            current["panchangs"].append(r["panchang"])
        elif current is not None:
            windows.append(current)
            current = None
    if current is not None:
        windows.append(current)

    windows.sort(key=lambda w: sum(w["scores"]) / len(w["scores"]), reverse=True)
    return [
        {
            "start_date": w["start"],
            "end_date": w["end"],
            "avg_score": round(sum(w["scores"]) / len(w["scores"]), 1),
            "reasons": sorted(w["reasons"]),
            "panchang_at_start": w["panchangs"][0],
        }
        for w in windows[:top_n]
    ]
ACTIVITY_KEYWORDS = {
    "career_change": [
        "change job", "changing job", "change jobs", "new job", "switch job", "switching job",
        "career change", "career switch", "quit my job", "quit job", "leave my job", "leaving my job",
        "resign", "resignation", "job change", "shift job", "shift my job", "job offer",
        "job interview", "interview call", "notice period", "job switch", "better opportunity",
        "promotion", "get promoted", "will i get promoted", "career growth", "career move",
        "government job", "govt job", "sarkari naukri", "layoff", "laid off", "fired",
        "job loss", "lose my job", "toxic boss", "toxic workplace", "switch industries",
        "new career", "second career", "remote job", "work from home job", "higher position",
        "job security", "career progress", "career prospects", "job hunt", "job search",
        "when will i get a job", "when will i get a good job",
    ],
    "start_business": [
        "start a business", "start my business", "start my own business", "launch my business",
        "start a company", "own company", "launch my app", "launch my startup", "launch the app",
        "launch my product", "start my own", "become an entrepreneur", "entrepreneurship",
        "open a shop", "open a store", "open my own", "open a restaurant", "open a clinic",
        "open an office", "register my company", "incorporate my company", "side hustle",
        "freelance business", "become self employed", "quit job to start", "raise funding",
        "find an investor", "franchise", "launch website", "go into business",
        "business partnership", "new venture", "startup launch", "product launch",
    ],
    "relocation_travel": [
        "relocate", "relocation", "relocating", "move to", "moving to", "shift to another city",
        "shift base", "shift house", "immigration", "immigrate", "migrate", "migration",
        "green card", "pr application", "permanent residency", "work visa", "study visa",
        "h1b", "visa interview", "settle abroad", "move abroad", "foreign posting",
        "transfer to another city", "job transfer", "posting abroad", "shift overseas",
        "move to another country", "leave the country", "foreign trip", "long trip abroad",
    ],
    "marriage": [
        "marriage", "get married", "getting married", "marry him", "marry her", "wedding date",
        "wedding muhurat", "shubh vivah", "vivah muhurat", "when will i get married",
        "second marriage", "propose", "proposal", "engagement", "engagement ceremony",
        "roka", "sagai", "court marriage", "tie the knot", "love marriage",
        "arranged marriage", "marriage timing", "right partner", "life partner",
        "will i get married", "wedding planning",
    ],
    "education": [
        "study abroad", "admission", "college admission", "university admission",
        "which college", "which university", "higher studies", "masters degree", "mba admission",
        "phd", "entrance exam", "competitive exam", "which stream", "which course",
        "enroll in", "join college", "start a course", "further studies", "grad school",
        "exam result", "will i pass", "clear the exam", "study visa for college",
    ],
    "financial_investment": [
        "invest", "investment", "stock market", "buy stocks", "mutual fund", "sip investment",
        "buy property", "buy land", "buy a house", "real estate investment", "purchase property",
        "cryptocurrency", "crypto investment", "buy gold", "gold investment", "fixed deposit",
        "take a loan", "home loan", "ipo", "trading", "put money in", "financial decision",
        "big purchase", "buy a plot", "invest in shares", "start sip",
    ],
    "health_decision": [
        "surgery", "operation", "medical procedure", "ivf", "fertility treatment",
        "when will i conceive", "childbirth", "delivery date", "c-section", "chemotherapy",
        "dental surgery", "cosmetic surgery", "knee replacement", "hip replacement",
        "health decision", "when will i recover", "start treatment", "elective surgery",
    ],
}
}

def detect_activity_intent(message: str) -> str | None:
    """Lightweight keyword match routing a chat question to a Muhurta
    activity type. Deliberately conservative: fires only on clear phrasing,
    so ordinary questions ('how's my week') pass through untouched. Returns
    None when nothing matches, in which case chat behaves exactly as before."""
    msg = message.lower()
    for activity, keywords in ACTIVITY_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            return activity
    return None
