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
