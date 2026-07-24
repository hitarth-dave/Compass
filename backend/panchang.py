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


# --- Daily time-slot Muhurta: Rahu Kaal, Yamaganda Kaal, Gulika Kaal,
# Abhijit Muhurta, and Choghadiya. This is the "what does Drik Panchang
# show for today" layer — distinct from compute_panchang above, which
# answers "is THIS instant auspicious" for the 6-month decision scanner.
#
# CONFIDENCE NOTE: Rahu Kaal / Yamaganda / Gulika Kaal use the equal-eighth
# day-division method, which is the most common one across Vedic astrology
# software — the weekday->octant tables below are standard and I'm
# confident in them. The Choghadiya weekday-start tables are also standard,
# but (same honesty policy as the rest of this module) haven't been checked
# against a published worked example — spot-check a known date/city against
# Drik Panchang before fully trusting it.

from datetime import timedelta

# Which of the 8 equal day-segments (1-indexed, sunrise=segment 1) each
# inauspicious period falls in, by weekday (Monday=0 .. Sunday=6, matching
# Python's date.weekday() and this module's existing VARA_NAMES order).
RAHU_KAAL_OCTANT =      [2, 7, 5, 6, 4, 3, 8]  # Mon..Sun
YAMAGANDA_OCTANT =      [4, 3, 2, 1, 7, 6, 5]  # Mon..Sun
GULIKA_KAAL_OCTANT =    [6, 5, 4, 3, 2, 1, 7]  # Mon..Sun

CHOGHADIYA_CYCLE = ["Udveg", "Chal", "Labh", "Amrit", "Kaal", "Shubh", "Rog"]
CHOGHADIYA_QUALITY = {
    "Amrit": "good", "Shubh": "good", "Labh": "good",
    "Chal": "neutral",
    "Udveg": "bad", "Rog": "bad", "Kaal": "bad",
}
# Starting Choghadiya name for the 8 day-segments and 8 night-segments, by
# weekday (Monday=0 .. Sunday=6). Each subsequent segment advances through
# CHOGHADIYA_CYCLE in order.
CHOGHADIYA_DAY_START =   ["Amrit", "Rog", "Labh", "Shubh", "Chal", "Kaal", "Udveg"]    # Mon..Sun
CHOGHADIYA_NIGHT_START = ["Chal", "Kaal", "Udveg", "Amrit", "Rog", "Labh", "Shubh"]     # Mon..Sun


def _octant_window(sunrise: datetime, segment_len: timedelta, octant_1indexed: int) -> Dict:
    start = sunrise + segment_len * (octant_1indexed - 1)
    end = start + segment_len
    return {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}


def _choghadiya_segments(period_start: datetime, segment_len: timedelta, start_name: str) -> list:
    idx = CHOGHADIYA_CYCLE.index(start_name)
    out = []
    for i in range(8):
        name = CHOGHADIYA_CYCLE[(idx + i) % len(CHOGHADIYA_CYCLE)]
        seg_start = period_start + segment_len * i
        seg_end = seg_start + segment_len
        out.append({
            "name": name,
            "quality": CHOGHADIYA_QUALITY[name],
            "start": seg_start.strftime("%H:%M"),
            "end": seg_end.strftime("%H:%M"),
        })
    return out


def compute_daily_muhurta(sunrise: datetime, sunset: datetime, next_sunrise: datetime, weekday_idx: int) -> Dict:
    """weekday_idx: Monday=0 .. Sunday=6 (Python's date.weekday()), for the
    calendar day `sunrise` falls on. sunrise/sunset/next_sunrise: local
    datetimes from astrology.sun_rise_set()."""
    day_len = sunset - sunrise
    night_len = next_sunrise - sunset
    day_octant = day_len / 8
    night_octant = night_len / 8

    # Abhijit Muhurta: the 8th of 15 equal divisions of the day — roughly
    # straddles local solar noon, but sized proportionally to day length
    # (the classically correct behavior) rather than a fixed 48 minutes.
    day_muhurta = day_len / 15
    abhijit_start = sunrise + day_muhurta * 7
    abhijit_end = sunrise + day_muhurta * 8

    return {
        "sunrise": sunrise.strftime("%H:%M"),
        "sunset": sunset.strftime("%H:%M"),
        "rahu_kaal": _octant_window(sunrise, day_octant, RAHU_KAAL_OCTANT[weekday_idx]),
        "yamaganda_kaal": _octant_window(sunrise, day_octant, YAMAGANDA_OCTANT[weekday_idx]),
        "gulika_kaal": _octant_window(sunrise, day_octant, GULIKA_KAAL_OCTANT[weekday_idx]),
        "abhijit_muhurta": {"start": abhijit_start.strftime("%H:%M"), "end": abhijit_end.strftime("%H:%M")},
        "choghadiya_day": _choghadiya_segments(sunrise, day_octant, CHOGHADIYA_DAY_START[weekday_idx]),
        "choghadiya_night": _choghadiya_segments(sunset, night_octant, CHOGHADIYA_NIGHT_START[weekday_idx]),
    }
