"""
Phase 2 — Panchang engine.

Computes four of the five classical Panchang elements — Tithi, Nitya Yoga,
Karana, and Vara (weekday) — for any given instant, from sidereal Sun/Moon
longitudes already computed elsewhere in this codebase. Nakshatra-of-the-
moment is already available via astrology.py's existing nakshatra lookup,
so it isn't duplicated here.

HONESTY NOTE ON SCOPE:
- This computes the Panchang AT a specific instant (which is what Muhurta
  selection needs — "is this exact moment auspicious") rather than a
  traditional printed-calendar "today's Panchang" day-card, which requires
  iterative root-finding to locate the exact clock time each Tithi/Yoga
  boundary crosses. Different feature; not built here.
- Omitted: Choghadiya, Hora (planetary-hour) lords, Rahu Kaal/Yamaganda/
  Gulika Kaal (need sunrise/sunset day-division math not implemented here),
  and Nakshatra-specific activity suitability tables (these vary
  significantly by regional tradition — including a single table would
  assert a disputed rule as settled, which we avoid elsewhere in this
  codebase too).
- Tithi/Karana/Yoga formulas below are standard and structurally verified
  (each index cycles through the correct count — 30 tithis, 60 karanas,
  27 yogas), but this has NOT been checked against a published worked
  Panchang example the way Ashtakavarga was. Treat it as directionally
  correct, not certified to the minute.
"""

from datetime import datetime
from typing import Dict

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima",
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya",
]
# Rikta ("empty") tithis — 4th, 9th, 14th of either paksha — classically
# avoided for starting new ventures. Widely agreed, low-controversy rule.
RIKTA_TITHI_INDICES = {3, 8, 13, 18, 23, 28}

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarma", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti",
]
INAUSPICIOUS_YOGAS = {
    "Vishkambha", "Atiganda", "Shoola", "Ganda",
    "Vyaghata", "Vajra", "Vyatipata", "Parigha", "Vaidhriti",
}

KARANA_MOVABLE = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
KARANA_FIXED = ["Shakuni", "Chatushpada", "Naga", "Kimstughna"]
# Vishti (Bhadra) is the single most universally agreed inauspicious
# karana across classical Muhurta texts — avoided for nearly every
# auspicious activity.
INAUSPICIOUS_KARANAS = {"Vishti"}

VARA_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Matches Python's datetime.weekday(): Monday=0 ... Sunday=6.


def _karana_name(karana_index: int) -> str:
    """karana_index: 0-59 (half-tithi index across a lunar month). The
    first 56 slots (0-55) cycle through the 7 movable karanas 8 times;
    the final 4 (56-59) are the fixed karanas, in order."""
    if karana_index >= 56:
        return KARANA_FIXED[karana_index - 56]
    return KARANA_MOVABLE[karana_index % 7]


def compute_panchang(sun_lon: float, moon_lon: float, at: datetime) -> Dict:
    """sun_lon, moon_lon: sidereal longitudes (0-360) at instant `at`.
    Returns Tithi, Nitya Yoga, Karana, Vara, and a small set of widely-
    agreed classical caution flags for that instant."""
    diff = (moon_lon - sun_lon) % 360

    tithi_index = int(diff // 12)  # 0-29
    tithi_name = TITHI_NAMES[tithi_index]
    paksha = "Shukla" if tithi_index < 15 else "Krishna"

    karana_index = int(diff // 6)  # 0-59
    karana_name = _karana_name(karana_index)

    yoga_index = int(((sun_lon + moon_lon) % 360) // (360 / 27))
    yoga_name = YOGA_NAMES[yoga_index]

    vara = VARA_NAMES[at.weekday()]

    cautions = []
    if tithi_index in RIKTA_TITHI_INDICES:
        cautions.append(f"Rikta Tithi ({tithi_name}) — classically avoided for new ventures.")
    if tithi_name == "Amavasya":
        cautions.append("Amavasya — new moon, widely avoided for auspicious beginnings.")
    if karana_name in INAUSPICIOUS_KARANAS:
        cautions.append(f"{karana_name} Karana (Bhadra) — the most universally avoided karana for any auspicious start.")
    if yoga_name in INAUSPICIOUS_YOGAS:
        cautions.append(f"{yoga_name} Yoga — classically inauspicious for new beginnings.")

    return {
        "tithi": tithi_name,
        "paksha": paksha,
        "karana": karana_name,
        "yoga": yoga_name,
        "vara": vara,
        "cautions": cautions,
        "is_favorable": len(cautions) == 0,
    }
