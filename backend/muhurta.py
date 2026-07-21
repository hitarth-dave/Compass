"""
Phase 1 — Decision Timing (Muhurta-lite).

Not full classical Muhurta: no Panchang (today's Tithi/Nakshatra/Yoga/
Karana), no electional-lagna calculation for the moment of action itself.
That's Phase 2. This scores candidate DATE windows using data this
codebase already computes and verifies:

  1. Bhava Bala (house strength, from Shadbala) of the houses that
     classically signify the decision (career, marriage, travel, etc.)
  2. The active Antardasha lord's own Shadbala strength, and whether it
     rules/sits in/aspects those same houses (karakatva)
  3. Transiting Jupiter/Saturn/Mars/Rahu/Ketu over those houses (gochara)

Depends only on: current_transits(), compute_antardashas() from
astrology.py — both confirmed present. current_transits() must have the
`at` parameter added (see astrology.py patch) for future-date scanning.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from astrology import current_transits, compute_antardashas

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
    """Find the active Antardasha at an arbitrary future/past datetime.
    Mahadasha list uses date-only strings; Antardasha subs use full
    'YYYY-MM-DD HH:MM:SS' timestamps (per astrology.py's precision fix) —
    handled accordingly."""
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

    # Bhava Bala of the primary houses — real Shadbala-derived house strength.
    bala_values = [house_lords[h]["bhava_bala"]["total_rupas"] for h in primary if h in house_lords]
    if bala_values:
        avg_bala = sum(bala_values) / len(bala_values)
        # Relative scaling: this partial-Shadbala system runs lower than full
        # classical totals (see astrology.py's own scope note), so compare
        # against the chart's own house average rather than a fixed absolute.
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
    for row in transits["planets"]:
        h = row.get("house_from_lagna")
        if h in primary:
            if row["name"] in BENEFIC_TRANSITS:
                score += 10
                reasons.append(f"Transiting {row['name']} is in house {h} from Lagna — supportive.")
            elif row["name"] in MALEFIC_TRANSITS:
                score -= 8
                reasons.append(f"Transiting {row['name']} is in house {h} from Lagna — proceed with more care.")

    return {"date": at.date().isoformat(), "score": max(0, min(100, round(score, 1))), "reasons": reasons}


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
                current = {"start": r["date"], "end": r["date"], "scores": [], "reasons": set()}
            current["end"] = r["date"]
            current["scores"].append(r["score"])
            current["reasons"].update(r["reasons"])
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
        }
        for w in windows[:top_n]
    ]
