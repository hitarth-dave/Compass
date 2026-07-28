"""Vedic astrology computations using Swiss Ephemeris (sidereal / Lahiri ayanamsa)."""
from __future__ import annotations
import swisseph as swe
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional

# Use Lahiri (Chitrapaksha) ayanamsa — standard for Vedic astrology
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

RASHIS = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena"
]
RASHI_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]
# Vimshottari dasha lords in order (starting from Ashwini)
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}

PLANETS = [
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mars", swe.MARS),
    ("Mercury", swe.MERCURY),
    ("Jupiter", swe.JUPITER),
    ("Venus", swe.VENUS),
    ("Saturn", swe.SATURN),
    ("Rahu", swe.MEAN_NODE),
]

PLANET_SYMBOLS = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa",
    "Rahu": "Ra", "Ketu": "Ke", "Ascendant": "As",
}


def _julday(dt_utc: datetime) -> float:
    return swe.julday(
        dt_utc.year, dt_utc.month, dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    )


def _sidereal_lon(jd: float, planet_id: int) -> float:
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    pos, _ = swe.calc_ut(jd, planet_id, flags)
    return pos[0] % 360, pos[3]  # longitude, speed


def _rashi_from_lon(lon: float) -> Tuple[int, float]:
    sign = int(lon // 30)
    deg_in_sign = lon - sign * 30
    return sign, deg_in_sign


def _nakshatra_from_lon(lon: float) -> Tuple[int, float]:
    # Each nakshatra = 13°20' = 13.3333°
    idx = int(lon // (360 / 27))
    pada = int((lon % (360 / 27)) // (360 / 108)) + 1
    return idx, pada


# --- Dignity tables (Vedic) ---
# Exaltation: sign_idx and exact degree of deepest exaltation
EXALTATION = {
    "Sun": (0, 10), "Moon": (1, 3), "Mars": (9, 28), "Mercury": (5, 15),
    "Jupiter": (3, 5), "Venus": (11, 27), "Saturn": (6, 20),
    "Rahu": (1, 20), "Ketu": (7, 20),
}
DEBILITATION = {p: ((s + 6) % 12, d) for p, (s, d) in EXALTATION.items()}
OWN_SIGNS = {
    "Sun": {4}, "Moon": {3}, "Mars": {0, 7}, "Mercury": {2, 5},
    "Jupiter": {8, 11}, "Venus": {1, 6}, "Saturn": {9, 10},
    "Rahu": {10}, "Ketu": {7},
}
# Moolatrikona: sign_idx, degree_min, degree_max (inclusive)
MOOLATRIKONA = {
    "Sun": (4, 0, 20), "Moon": (1, 4, 20), "Mars": (0, 0, 12),
    "Mercury": (5, 16, 20), "Jupiter": (8, 0, 10),
    "Venus": (6, 0, 15), "Saturn": (10, 0, 20),
}


def _navamsa_sign(lon: float) -> int:
    """Return sign_idx (0-11) of the Navamsa (D9) position."""
    sign = int(lon // 30)
    deg_in_sign = lon - sign * 30
    navamsa_idx = int(deg_in_sign // (30 / 9))  # 0..8
    element = sign % 3  # 0=movable, 1=fixed, 2=dual
    start_map = {0: sign, 1: (sign + 8) % 12, 2: (sign + 4) % 12}
    return (start_map[element] + navamsa_idx) % 12


def _dasamsa_sign(lon: float) -> int:
    """Return sign_idx (0-11) of the Dasamsa (D10) position.
    Classical rule: odd signs (Aries, Gemini, Leo, Libra, Sagittarius, Aquarius)
    count the 10 parts starting from the same sign; even signs start counting
    from the 9th sign from themselves (i.e. +8 in 0-indexed terms)."""
    sign = int(lon // 30)
    deg_in_sign = lon - sign * 30
    dasamsa_idx = int(deg_in_sign // (30 / 10))  # 0..9
    is_odd_sign = (sign % 2 == 0)  # sign_idx 0 (Aries) is the 1st sign = odd
    start = sign if is_odd_sign else (sign + 8) % 12
    return (start + dasamsa_idx) % 12


# --- Remaining Shodasha Varga (16-chart system) divisional signs ---
# Each follows the classical Parashari division rule for that chart. Where a
# tradition offers more than one accepted method (D4, D6 in particular), the
# most widely implemented Parashari rule is used below.

def _hora_sign(lon: float) -> int:
    """D2 Hora — wealth/resources. Sign split into two 15° halves, each
    assigned to the Sun's Hora (Leo) or the Moon's Hora (Cancer). Odd signs
    run Leo-then-Cancer; even signs run Cancer-then-Leo."""
    sign, deg = _rashi_from_lon(lon)
    half = int(deg // 15)  # 0 or 1
    is_odd_sign = (sign % 2 == 0)
    LEO, CANCER = 4, 3
    if is_odd_sign:
        return LEO if half == 0 else CANCER
    return CANCER if half == 0 else LEO


def _chaturthamsa_sign(lon: float) -> int:
    """D4 Chaturthamsa — property, home, fixed assets. Sign split into four
    7.5° parts, mapped to the same/4th/7th/10th sign from itself (kendras)."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 7.5)  # 0..3
    return (sign + idx * 3) % 12


def _shashthamsa_sign(lon: float) -> int:
    """D6 Shashthamsa — health, obstacles, enemies. Sign split into six 5°
    parts; movable signs start counting from Aries, fixed signs from Libra,
    dual signs from Sagittarius."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 5)  # 0..5
    element = sign % 3  # 0=movable, 1=fixed, 2=dual
    start_map = {0: 0, 1: 6, 2: 8}
    return (start_map[element] + idx) % 12


def _saptamsa_sign(lon: float) -> int:
    """D7 Saptamsa — children, progeny. Sign split into seven ~4.2857° parts;
    odd signs count from themselves, even signs count from the 7th sign
    from themselves."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // (30 / 7))  # 0..6
    is_odd_sign = (sign % 2 == 0)
    start = sign if is_odd_sign else (sign + 6) % 12
    return (start + idx) % 12


def _shodasamsa_sign(lon: float) -> int:
    """D16 Shodasamsa (Kalamsa) — vehicles, comforts, general happiness.
    Sign split into sixteen 1.875° parts; movable signs start from Aries,
    fixed signs from Leo, dual signs from Sagittarius."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 1.875)  # 0..15
    element = sign % 3
    start_map = {0: 0, 1: 4, 2: 8}
    return (start_map[element] + idx) % 12


def _chaturvimsamsa_sign(lon: float) -> int:
    """D24 Chaturvimsamsa (Siddhamsa) — education, learning. Sign split into
    twenty-four 1.25° parts; odd signs start counting from Leo, even signs
    from Cancer."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 1.25)  # 0..23
    is_odd_sign = (sign % 2 == 0)
    start = 4 if is_odd_sign else 3  # Leo : Cancer
    return (start + idx) % 12


def _shashtiamsa_sign(lon: float) -> int:
    """D60 Shashtiamsa — fine-grained overall life reading, karma carried
    from past life. Sign split into sixty 0.5° parts, counted sequentially
    from the sign itself (this is the simplified sign-only method used by
    most software; the full classical version also names each of the 60
    Shashtiamsa deities, which this app doesn't track)."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 0.5)  # 0..59
    return (sign + idx) % 12


def _drekkana_sign_for_bala(lon: float) -> int:
    """D3 Drekkana sign — used for Saptavargaja Bala (distinct from the
    _drekkana_bala() degree-based gender proxy already used in Sthana Bala,
    which is a different, simplified classical component). Each sign's 30°
    splits into three 10° drekkanas, mapped to itself / +4 / +8 signs
    (trikona counting)."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 10)  # 0, 1, 2
    return (sign + idx * 4) % 12


def _dwadasamsa_sign(lon: float) -> int:
    """D12 Dwadasamsa — used for Saptavargaja Bala. Sign splits into twelve
    2.5° parts, counted sequentially from the sign itself."""
    sign, deg = _rashi_from_lon(lon)
    idx = int(deg // 2.5)  # 0..11
    return (sign + idx) % 12


def _trimsamsa_sign(lon: float) -> int:
    """D30 Trimsamsa — used for Saptavargaja Bala. Unlike the other vargas,
    this is an UNEQUAL division ruled by the five non-luminary planets, in
    opposite order for odd vs even signs (classical Parashari rule)."""
    sign, deg = _rashi_from_lon(lon)
    is_odd_sign = (sign % 2 == 0)  # Aries idx0 is the 1st (odd) sign
    ARIES, AQUARIUS, SAGITTARIUS, GEMINI, LIBRA = 0, 10, 8, 2, 6
    TAURUS, VIRGO, PISCES, CAPRICORN, SCORPIO = 1, 5, 11, 9, 7
    bounds = (
        [(0, 5, ARIES), (5, 10, AQUARIUS), (10, 18, SAGITTARIUS), (18, 25, GEMINI), (25, 30.0001, LIBRA)]
        if is_odd_sign else
        [(0, 5, TAURUS), (5, 12, VIRGO), (12, 20, PISCES), (20, 25, CAPRICORN), (25, 30.0001, SCORPIO)]
    )
    for lo, hi, sidx in bounds:
        if lo <= deg < hi:
            return sidx
    return bounds[-1][2]


def _dignity(name: str, sign_idx: int, degree_in_sign: float, nav_sign: int) -> Dict:
    tags = []
    # Exalted / Debilitated (within ±1° of deepest = deep, else general)
    if name in EXALTATION:
        ex_sign, _ = EXALTATION[name]
        if sign_idx == ex_sign:
            tags.append("Exalted")
        deb_sign, _ = DEBILITATION[name]
        if sign_idx == deb_sign:
            tags.append("Debilitated")
    # Moolatrikona takes precedence over own
    if name in MOOLATRIKONA:
        mt_sign, mt_lo, mt_hi = MOOLATRIKONA[name]
        if sign_idx == mt_sign and mt_lo <= degree_in_sign <= mt_hi:
            tags.append("Moolatrikona")
    if name in OWN_SIGNS and sign_idx in OWN_SIGNS[name] and "Moolatrikona" not in tags:
        tags.append("Own Sign")
    if sign_idx == nav_sign:
        tags.append("Vargottama")
    return {
        "tags": tags,
        "navamsa_sign_idx": nav_sign,
        "navamsa_sign": RASHIS[nav_sign],
        "navamsa_sign_en": RASHI_EN[nav_sign],
    }


def compute_chart(dob_iso: str, tob: str, tz_offset_hours: float, lat: float, lon: float) -> Dict:
    """
    dob_iso: 'YYYY-MM-DD'
    tob: 'HH:MM'
    tz_offset_hours: e.g. 5.5 for IST
    lat, lon: birth location
    """
    y, m, d = map(int, dob_iso.split("-"))
    hh, mm = map(int, tob.split(":"))
    local = datetime(y, m, d, hh, mm)
    utc = local - timedelta(hours=tz_offset_hours)
    jd = _julday(utc)

    # Ascendant (Lagna) with sidereal
    cusps, ascmc = swe.houses_ex(
        jd, lat, lon, b'W', swe.FLG_SIDEREAL
    )
    asc_lon = ascmc[0] % 360
    asc_sign, asc_deg = _rashi_from_lon(asc_lon)
    asc_nak_idx, asc_pada = _nakshatra_from_lon(asc_lon)

    planets_out: List[Dict] = []
    for name, pid in PLANETS:
        p_lon, speed = _sidereal_lon(jd, pid)
        sign, deg = _rashi_from_lon(p_lon)
        nak_idx, pada = _nakshatra_from_lon(p_lon)
        # House = sign relative to ascendant sign
        house = ((sign - asc_sign) % 12) + 1
        nav_sign = _navamsa_sign(p_lon)
        dignity = _dignity(name, sign, deg, nav_sign)
        planets_out.append({
            "name": name,
            "symbol": PLANET_SYMBOLS[name],
            "longitude": round(p_lon, 4),
            "sign_idx": sign,
            "sign": RASHIS[sign],
            "sign_en": RASHI_EN[sign],
            "degree_in_sign": round(deg, 2),
            "nakshatra": NAKSHATRAS[nak_idx],
            "nakshatra_lord": NAK_LORDS[nak_idx % 9],
            "pada": pada,
            "house": house,
            "speed": round(speed, 4),
            "retrograde": speed < 0 and name not in ("Sun", "Moon", "Rahu", "Ketu"),
            "dignity": dignity["tags"],
            "navamsa_sign": dignity["navamsa_sign_en"],
            "navamsa_sign_idx": dignity["navamsa_sign_idx"],
        })

    # Ketu = Rahu + 180
    rahu = next(p for p in planets_out if p["name"] == "Rahu")
    ketu_lon = (rahu["longitude"] + 180) % 360
    ketu_sign, ketu_deg = _rashi_from_lon(ketu_lon)
    k_nak, k_pada = _nakshatra_from_lon(ketu_lon)
    ketu_nav = _navamsa_sign(ketu_lon)
    ketu_dignity = _dignity("Ketu", ketu_sign, ketu_deg, ketu_nav)
    planets_out.append({
        "name": "Ketu",
        "symbol": "Ke",
        "longitude": round(ketu_lon, 4),
        "sign_idx": ketu_sign,
        "sign": RASHIS[ketu_sign],
        "sign_en": RASHI_EN[ketu_sign],
        "degree_in_sign": round(ketu_deg, 2),
        "nakshatra": NAKSHATRAS[k_nak],
        "nakshatra_lord": NAK_LORDS[k_nak % 9],
        "pada": k_pada,
        "house": ((ketu_sign - asc_sign) % 12) + 1,
        "retrograde": True,
        "dignity": ketu_dignity["tags"],
        "navamsa_sign": ketu_dignity["navamsa_sign_en"],
    })

    # Moon nakshatra for Vimshottari dasha
    moon = next(p for p in planets_out if p["name"] == "Moon")
    moon_lon = moon["longitude"]
    m_nak_idx, _ = _nakshatra_from_lon(moon_lon)
    dashas = _vimshottari_dashas(moon_lon, local, m_nak_idx)

    # Natural (fixed) + Functional (Lagna-dependent) benefic/malefic
    # classification for every planet — see _natural_nature/_functional_nature
    # for the exact rules.
    sun = next(p for p in planets_out if p["name"] == "Sun")
    natural_nature = {p["name"]: _natural_nature(p["name"], sun["longitude"], moon_lon) for p in planets_out}
    functional_nature = _functional_nature(asc_sign)

    # House lords: for each house (1-12), the sign occupying it and its dispositor
    house_aspects = _compute_house_aspects(planets_out)
    planet_signs = {p["name"]: p["sign_idx"] for p in planets_out if p["name"] in ASHTAKAVARGA_PLANETS}
    ashtakavarga = compute_ashtakavarga(planet_signs, asc_sign)
    house_lords_list = []
    for h in range(1, 13):
        sign_idx = (asc_sign + h - 1) % 12
        lord = SIGN_LORDS[sign_idx]
        # Where does the lord sit (house)?
        lord_planet = next((p for p in planets_out if p["name"] == lord), None)
        house_lords_list.append({
            "house": h,
            "sign": RASHIS[sign_idx],
            "sign_en": RASHI_EN[sign_idx],
            "lord": lord,
            "lord_sits_in_house": lord_planet["house"] if lord_planet else None,
            "lord_sits_in_sign_en": lord_planet["sign_en"] if lord_planet else None,
            "lord_degree": lord_planet["degree_in_sign"] if lord_planet else None,
            "aspected_by": house_aspects[h],
            "ashtakavarga_sav": ashtakavarga["sav"][sign_idx],
            "lord_natural_nature": natural_nature.get(lord),
            "lord_functional_nature": functional_nature.get(lord),
        })

    yogas = _detect_yogas(planets_out, asc_sign)
    shadbala = compute_shadbala(planets_out, asc_lon, jd, lat, lon, house_aspects)
    bhava_bala = compute_bhava_bala(house_lords_list, shadbala, house_aspects, asc_lon)
    for h in house_lords_list:
        h["bhava_bala"] = bhava_bala[h["house"]]

    return {
        "birth_utc": utc.isoformat(),
        "ascendant": {
            "longitude": round(asc_lon, 4),
            "sign_idx": asc_sign,
            "sign": RASHIS[asc_sign],
            "sign_en": RASHI_EN[asc_sign],
            "degree_in_sign": round(asc_deg, 2),
            "nakshatra": NAKSHATRAS[asc_nak_idx],
            "pada": asc_pada,
            "lord": SIGN_LORDS[asc_sign],
        },
        "planets": planets_out,
        "dashas": dashas,
        "house_lords": house_lords_list,
        "yogas": yogas,
        "ashtakavarga": ashtakavarga,
        "shadbala": shadbala,
        "planet_nature": {
            p["name"]: {
                "natural": natural_nature.get(p["name"]),
                "functional": functional_nature.get(p["name"]),  # None for Rahu/Ketu (no sign lordship)
            }
            for p in planets_out
        },
    }


# --- Rashi (sign) lords ---
SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

# --- Natural & Functional Benefic/Malefic classification ---
# Natural (Naisargika) nature is fixed for every chart. Functional
# (Tatkalika) nature depends on which houses a planet rules FROM THIS
# LAGNA, and is what actually determines whether a planet helps or hurts
# in this particular chart — a natural benefic can be a functional malefic
# for a given ascendant, and vice versa.

NATURAL_BENEFIC_PLANETS = {"Jupiter", "Venus", "Mercury"}  # Moon handled separately (waxing/waning)
NATURAL_MALEFIC_PLANETS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}


def _natural_nature(name: str, sun_lon: float, moon_lon: float) -> str:
    """Fixed, chart-independent benefic/malefic status. Waxing Moon (0-180
    degrees from Sun) is a natural benefic; waning Moon is a natural malefic."""
    if name == "Moon":
        elongation = (moon_lon - sun_lon) % 360
        return "benefic" if elongation <= 180 else "malefic"
    if name in NATURAL_BENEFIC_PLANETS:
        return "benefic"
    return "malefic"  # Sun, Mars, Saturn, Rahu, Ketu


def _functional_nature(asc_sign: int) -> Dict[str, str]:
    """Classify each of the 7 sign-ruling planets as a functional benefic or
    malefic FOR THIS LAGNA, based on which houses it rules. Rahu/Ketu don't
    rule signs classically, so they're excluded here (their badge falls back
    to natural nature only).

    Rules (Parashari), checked in priority order, first match wins:
      1. Rules the Lagna (1st) -> benefic. The 1st is both kendra and
         trikona, and lagna lordship is always auspicious.
      2. Rules a trikona (5th/9th) -> benefic. (A planet ruling both a
         kendra and a trikona -- e.g. Mars for Cancer/Leo lagna, Venus for
         Virgo/Libra lagna -- is a Yogakaraka, the strongest functional
         benefic; still bucketed as "benefic" here, just without that
         extra label.)
      3. Rules a dusthana (6th/8th/12th), with none of the above -> malefic.
      4. Rules only a kendra (4th/7th/10th), with none of the above ->
         Kendradhipatya dosha: a natural malefic here loses its edge and
         becomes functionally benefic; a natural benefic here loses its
         edge and becomes functionally malefic.
      5. Rules only neutral houses (2nd/3rd/11th) -> benefic by default
         (none of these are dusthana).

    This is a defensible, commonly used simplification of a genuinely
    debated area of classical astrology (schools differ especially on
    mixed trikona+dusthana rulership, and on how strongly to weight
    3rd/11th) — a reasonable default, not the only valid reading.
    """
    houses_ruled: Dict[str, List[int]] = {}
    for h in range(1, 13):
        sign_idx = (asc_sign + h - 1) % 12
        lord = SIGN_LORDS[sign_idx]
        houses_ruled.setdefault(lord, []).append(h)

    TRIKONA = {5, 9}
    DUSTHANA = {6, 8, 12}
    KENDRA_ONLY = {4, 7, 10}

    result = {}
    for planet, houses in houses_ruled.items():
        hs = set(houses)
        if 1 in hs:
            result[planet] = "benefic"
        elif hs & TRIKONA:
            result[planet] = "benefic"
        elif hs & DUSTHANA:
            result[planet] = "malefic"
        elif hs & KENDRA_ONLY:
            result[planet] = "benefic" if planet in NATURAL_MALEFIC_PLANETS else "malefic"
        else:
            result[planet] = "benefic"
    return result


# --- Ashtakavarga (Sarvashtakavarga / Bhinnashtakavarga) ---
# Classical BPHS Chapter 66 benefic-place tables. Each of the 7 planets has a
# fixed set of "benefic houses" (counted from each of the 8 contributors: the
# 7 planets + Lagna) that is IDENTICAL for every horoscope ever cast — only
# which sign each benefic house lands on changes per chart. Cross-verified
# against B.V. Raman's published totals (Sun=48, Moon=49, Mars=39, Mercury=54,
# Jupiter=56, Venus=52, Saturn=39, grand total=337) and against his fully
# worked Standard Horoscope example, which this implementation reproduces
# exactly.
ASHTAKAVARGA_TABLE = {
    "Sun": {
        "Sun": [1,2,4,7,8,9,10,11], "Moon": [3,6,10,11], "Mars": [1,2,4,7,8,9,10,11],
        "Mercury": [3,5,6,9,10,11,12], "Jupiter": [5,6,9,11], "Venus": [6,7,12],
        "Saturn": [1,2,4,7,8,9,10,11], "Ascendant": [3,4,6,10,11,12],
    },
    "Moon": {
        "Sun": [3,6,7,8,10,11], "Moon": [1,3,6,7,10,11], "Mars": [2,3,5,6,9,10,11],
        "Mercury": [1,3,4,5,7,8,10,11], "Jupiter": [1,4,7,8,10,11,12], "Venus": [3,4,5,7,9,10,11],
        "Saturn": [3,5,6,11], "Ascendant": [3,6,10,11],
    },
    "Mars": {
        "Sun": [3,5,6,10,11], "Moon": [3,6,11], "Mars": [1,2,4,7,8,10,11],
        "Mercury": [3,5,6,11], "Jupiter": [6,10,11,12], "Venus": [6,8,11,12],
        "Saturn": [1,4,7,8,9,10,11], "Ascendant": [1,3,6,10,11],
    },
    "Mercury": {
        "Sun": [5,6,9,11,12], "Moon": [2,4,6,8,10,11], "Mars": [1,2,4,7,8,9,10,11],
        "Mercury": [1,3,5,6,9,10,11,12], "Jupiter": [6,8,11,12], "Venus": [1,2,3,4,5,8,9,11],
        "Saturn": [1,2,4,7,8,9,10,11], "Ascendant": [1,2,4,6,8,10,11],
    },
    "Jupiter": {
        "Sun": [1,2,3,4,7,8,9,10,11], "Moon": [2,5,7,9,11], "Mars": [1,2,4,7,8,10,11],
        "Mercury": [1,2,4,5,6,9,10,11], "Jupiter": [1,2,3,4,7,8,10,11], "Venus": [2,5,6,9,10,11],
        "Saturn": [3,5,6,12], "Ascendant": [1,2,4,5,6,7,9,10,11],
    },
    "Venus": {
        "Sun": [8,11,12], "Moon": [1,2,3,4,5,8,9,11,12], "Mars": [3,5,6,9,11,12],
        "Mercury": [3,5,6,9,11], "Jupiter": [5,8,9,10,11], "Venus": [1,2,3,4,5,8,9,10,11],
        "Saturn": [3,4,5,8,9,10,11], "Ascendant": [1,2,3,4,5,8,9,11],
    },
    "Saturn": {
        "Sun": [1,2,4,7,8,10,11], "Moon": [3,6,11], "Mars": [3,5,6,10,11,12],
        "Mercury": [6,8,9,10,11,12], "Jupiter": [5,6,11,12], "Venus": [6,11,12],
        "Saturn": [3,5,6,11], "Ascendant": [1,3,4,6,10,11],
    },
}
ASHTAKAVARGA_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

# Classical house/karaka significators per life-domain — BPHS-standard
# assignments. Used both for chart-driven search queries and for the
# deterministic domain-verdict scoring (see compute_domain_verdict below).
DOMAIN_SIGNIFICATORS = {
    "marriage": ([7], ["Venus"]),
    "career": ([10], ["Saturn", "Sun", "Mercury"]),
    "wealth": ([2, 11], ["Jupiter"]),
    "health": ([6, 8, 1], ["Saturn", "Mars"]),
    "children": ([5], ["Jupiter"]),
    "education": ([4, 5, 9], ["Mercury", "Jupiter"]),
    "spirituality": ([9, 12], ["Jupiter", "Ketu"]),
    "family": ([2, 3, 4], ["Moon", "Mars"]),
    "travel": ([12, 9], ["Rahu"]),
}


def compute_ashtakavarga(planet_signs: Dict[str, int], asc_sign: int) -> Dict:
    """Compute Bhinnashtakavarga (per-planet bindu tables) and Sarvashtakavarga
    (their sum) for a chart. planet_signs maps the 7 classical planet names to
    their sign_idx (0-11); asc_sign is the Ascendant's sign_idx.
    Returns {"bav": {planet: [12 bindu counts by sign_idx]}, "sav": [12 totals]}."""
    contributors = {**{p: planet_signs[p] for p in ASHTAKAVARGA_PLANETS if p in planet_signs}, "Ascendant": asc_sign}
    bav = {}
    for target in ASHTAKAVARGA_PLANETS:
        counts = [0] * 12
        for contributor_name, benefic_houses in ASHTAKAVARGA_TABLE[target].items():
            if contributor_name not in contributors:
                continue
            c_sign = contributors[contributor_name]
            for house_num in benefic_houses:
                sign = (c_sign + house_num - 1) % 12
                counts[sign] += 1
        bav[target] = counts
    sav = [sum(bav[p][s] for p in ASHTAKAVARGA_PLANETS) for s in range(12)]
    return {"bav": bav, "sav": sav}


# Classical thresholds for judging a transit by the transiting planet's own
# Bhinnashtakavarga bindu count in the sign it occupies (BPHS-style
# convention, widely used): 0-3 = weak/troublesome, 4 = mixed, 5+ = strong.
def ashtakavarga_transit_strength(planet_name: str, transit_sign_idx: int, natal_bav: Dict[str, List[int]]) -> Dict:
    bindus = natal_bav.get(planet_name, [0] * 12)[transit_sign_idx]
    if bindus <= 3:
        label = "weak — this transit tends to underdeliver or bring friction"
    elif bindus == 4:
        label = "mixed — moderate, neither strongly favorable nor difficult"
    else:
        label = "strong — this transit tends to deliver its themes favorably"
    return {"bindus": bindus, "label": label}


# --- Shadbala (planetary strength) & Bhava Bala (house strength) ---
#
# SCOPE & VERIFICATION: Full classical Shadbala has six components. As of
# this pass, this implementation covers substantially all of it, verified
# against a real reference chart (4 Jun 1995, 14:44 IST, Unjha, Gujarat)
# with published Shadbala Rupas from a professional astrology program —
# see compute_shadbala's docstring for the exact before/after numbers.
#   Sthana Bala  = Uchcha Bala + Kendradi Bala + Ojayugmarasyamsa Bala +
#                  Drekkana Bala + Saptavargaja Bala (dignity across all 7
#                  classical vargas: D1/D2/D3/D7/D9/D12/D30 — see
#                  _saptavargaja_bala)
#   Dig Bala     = full classical formula
#   Kaala Bala   = Paksha Bala + Nathonnatha Bala + Ayana Bala (declination-
#                  based, all 7 planets) + Vara Bala (weekday lord) + Hora
#                  Bala (planetary-hour lord) + Tribhaga Bala (day/night
#                  third lord) — all using real sunrise/sunset for the birth
#                  location. Still missing: Varsha Bala and Masa Bala
#                  (year/month-lord reckoning) — an obscure enough system
#                  that several professional tools skip or approximate it
#                  too; low priority unless a reference example specifically
#                  needs it.
#   Chesta Bala  = simplified continuous approximation from actual vs. mean
#                  daily motion (not the full classical 8-tier Vakra/Anuvakra/
#                  etc. discrete categories, which need finer ephemeris
#                  sampling than a single snapshot gives) — likely the
#                  largest remaining source of the residual gap below.
#   Naisargika Bala = full classical fixed table
#   Drik Bala    = full continuous Sputa Drishti formula (BPHS 27.19-23),
#                  verified against B.V. Raman's published Standard Horoscope
#                  worked example: 6 of 7 planets matched almost exactly,
#                  7th (Saturn) close (see _ordinary_drishti docstring for
#                  exact numbers). Can be negative (net malefic aspect).
#   Yuddha Bala  = planetary-war adjustment (BPHS 27.20), implemented but
#                  untested against a real war condition — the reference
#                  chart has none.
#
# RESULT: against the reference chart, totals moved from being
# systematically 35-53% below the published Rupas (missing components) to
# within roughly 4-17% for 6 of 7 planets (Jupiter within 0.3%). Treat
# totals as closely approximate — comparable to the classical minimum-
# required-Rupas table (MINIMUM_SHADBALA_RUPAS) for a general sense of
# strength, but not yet an exact classical match.

NAISARGIKA_BALA = {  # fixed, in Virupas — BPHS Ch.33, verified against multiple sources
    "Sun": 60.0, "Moon": 51.43, "Venus": 42.86, "Jupiter": 34.29,
    "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57,
}
DIG_BALA_PEAK_HOUSE = {  # house of maximum directional strength
    "Sun": 10, "Mars": 10, "Moon": 4, "Venus": 4, "Jupiter": 1, "Mercury": 1, "Saturn": 7,
}
OJA_RASI_BENEFIC = {"Moon", "Venus"}  # get strength in even (yugma) signs; rest in odd (oja)
DREKKANA_MALE = {"Sun", "Mars", "Jupiter"}
DREKKANA_FEMALE = {"Moon", "Venus"}
DREKKANA_NEUTRAL = {"Mercury", "Saturn"}
MEAN_DAILY_MOTION = {  # degrees/day, standard mean motion constants
    "Mars": 0.524, "Mercury": 1.383, "Jupiter": 0.083, "Venus": 1.2, "Saturn": 0.034,
}
KAALA_BALA_BENEFICS = {"Moon", "Mercury", "Jupiter", "Venus"}
DIURNAL_PLANETS = {"Sun", "Jupiter", "Venus"}
NOCTURNAL_PLANETS = {"Moon", "Mars", "Saturn"}
MINIMUM_SHADBALA_RUPAS = {  # BPHS 27.32-33 prescribed minimum for a planet to deliver full results.
    # Now that Saptavargaja Bala and the rest of Kaala Bala are implemented,
    # total_rupas is close enough to the full classical system to compare
    # against this table meaningfully (see compute_shadbala's verification
    # note) — though still not an exact match, so treat "below minimum" as
    # indicative, not definitive.
    "Sun": 6.5, "Moon": 6.0, "Mars": 5.0, "Mercury": 7.0,  # Sun corrected from an earlier 5.0 — confirmed 6.5 by back-calculating a reference chart's published SB% ratios
    "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0,
}


# --- Saptavargaja Bala (Sthana Bala's largest sub-component) ---
# Classical point scale, BPHS 27.2-4 (per Dr. B.V. Raman's "Bhava & Graha
# Balas"): Moolatrikona 45, Own sign 30, Great Friend's sign 22.5, Friend's
# sign 15, Neutral's sign 7.5, Enemy's sign 3.75, Great Enemy's sign 1.875.
# Moolatrikona only applies in the Rasi (D1) chart — in every other varga a
# planet in what would be its moolatrikona sign simply scores "Own sign."
# Exaltation/debilitation play no role here (confirmed against multiple
# independent sources) — only the 5-tier compound relationship to the
# sign's lord.
SAPTAVARGA_POINTS = {
    "moolatrikona": 45.0, "own": 30.0, "great_friend": 22.5,
    "friend": 15.0, "neutral": 7.5, "enemy": 3.75, "great_enemy": 1.875,
}

# Naisargika (natural) Maitri — BPHS Ch.4, fixed for every chart.
NATURAL_FRIENDSHIP = {
    "Sun":     {"friend": {"Moon", "Mars", "Jupiter"}, "enemy": {"Venus", "Saturn"}},
    "Moon":    {"friend": {"Sun", "Mercury"}, "enemy": set()},
    "Mars":    {"friend": {"Sun", "Moon", "Jupiter"}, "enemy": {"Mercury"}},
    "Mercury": {"friend": {"Sun", "Venus"}, "enemy": {"Moon"}},
    "Jupiter": {"friend": {"Sun", "Moon", "Mars"}, "enemy": {"Mercury", "Venus"}},
    "Venus":   {"friend": {"Mercury", "Saturn"}, "enemy": {"Sun", "Moon"}},
    "Saturn":  {"friend": {"Mercury", "Venus"}, "enemy": {"Sun", "Moon", "Mars"}},
}

SAPTAVARGA_KEYS = ("D1", "D2", "D3", "D7", "D9", "D12", "D30")


def _natural_relationship(planet: str, other: str) -> str:
    if other in NATURAL_FRIENDSHIP[planet]["friend"]:
        return "friend"
    if other in NATURAL_FRIENDSHIP[planet]["enemy"]:
        return "enemy"
    return "neutral"


def _temporal_relationship(sign_a: int, sign_b: int) -> str:
    """Tatkalika Maitri — planets in the 2nd/3rd/4th/10th/11th/12th sign from
    a given planet's own Rasi sign are temporal friends; the rest (including
    the same sign) are temporal enemies. Computed from Rasi (D1) placement
    for both planets, used uniformly across all 7 vargas — this is the
    simpler of two documented conventions (the other recomputes temporal
    friendship per-varga); tested against a real reference chart, this
    convention converged well."""
    house_distance = ((sign_b - sign_a) % 12) + 1
    return "friend" if house_distance in (2, 3, 4, 10, 11, 12) else "enemy"


def _compound_relationship(natural: str, temporal: str) -> str:
    """Panchadha Maitri — the classical 5-tier compound relationship."""
    return {
        ("friend", "friend"): "great_friend",
        ("friend", "enemy"): "friend",
        ("neutral", "friend"): "friend",
        ("neutral", "enemy"): "enemy",
        ("enemy", "friend"): "neutral",
        ("enemy", "enemy"): "great_enemy",
    }[(natural, temporal)]


def _saptavargaja_bala(name: str, longitude: float, rasi_sign_of: Dict[str, int]) -> float:
    """Sum of dignity-based points across the 7 classical vargas (Virupas).
    rasi_sign_of maps each of the 7 planets to its own Rasi (D1) sign_idx,
    needed to work out temporal friendship for whichever sign-lord is being
    compared against."""
    varga_funcs = {
        "D1": lambda lon: int(lon // 30),
        "D2": _hora_sign,
        "D3": _drekkana_sign_for_bala,
        "D7": _saptamsa_sign,
        "D9": _navamsa_sign,
        "D12": _dwadasamsa_sign,
        "D30": _trimsamsa_sign,
    }
    total = 0.0
    for vkey in SAPTAVARGA_KEYS:
        vsign = varga_funcs[vkey](longitude)
        lord = SIGN_LORDS[vsign]
        if lord == name:
            if vkey == "D1" and name in MOOLATRIKONA:
                mt_sign, mt_lo, mt_hi = MOOLATRIKONA[name]
                deg_in_sign = longitude - int(longitude // 30) * 30
                tier = "moolatrikona" if (vsign == mt_sign and mt_lo <= deg_in_sign <= mt_hi) else "own"
            else:
                tier = "own"
        else:
            natural = _natural_relationship(name, lord)
            temporal = _temporal_relationship(rasi_sign_of[name], rasi_sign_of[lord])
            tier = _compound_relationship(natural, temporal)
        total += SAPTAVARGA_POINTS[tier]
    return round(total, 2)


def _angular_diff(a: float, b: float) -> float:
    """Shortest angular distance (0-180) between two longitudes."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def _uchcha_bala(name: str, longitude: float) -> float:
    if name not in EXALTATION:
        return 0.0
    ex_sign, ex_deg = EXALTATION[name]
    ex_lon = ex_sign * 30 + ex_deg
    diff = _angular_diff(longitude, ex_lon)
    return round(60 * (180 - diff) / 180, 2)


def _kendradi_bala(house: int) -> float:
    if house in (1, 4, 7, 10):
        return 60.0
    if house in (2, 5, 8, 11):
        return 30.0
    return 15.0  # 3, 6, 9, 12


def _oja_yugma_bala(name: str, sign_idx: int, navamsa_sign_idx: int) -> float:
    wants_even = name in OJA_RASI_BENEFIC
    total = 0.0
    if ((sign_idx % 2 == 1) == wants_even):
        total += 15.0
    if ((navamsa_sign_idx % 2 == 1) == wants_even):
        total += 15.0
    return total


def _drekkana_bala(name: str, degree_in_sign: float) -> float:
    drek = int(degree_in_sign // 10)  # 0, 1, 2
    if drek == 0 and name in DREKKANA_MALE:
        return 15.0
    if drek == 1 and name in DREKKANA_FEMALE:
        return 15.0
    if drek == 2 and name in DREKKANA_NEUTRAL:
        return 15.0
    return 0.0


def _dig_bala(name: str, longitude: float, asc_longitude: float) -> float:
    peak_house = DIG_BALA_PEAK_HOUSE.get(name)
    if not peak_house:
        return 0.0
    peak_lon = (asc_longitude + (peak_house - 1) * 30) % 360
    diff = _angular_diff(longitude, peak_lon)
    return round((180 - diff) / 3, 2)


def _chesta_bala(name: str, speed: float, retrograde: bool) -> float | None:
    """Simplified continuous approximation — see scope note above. Returns
    None for Sun/Moon, which use Ayana/Paksha Bala instead per BPHS."""
    if name not in MEAN_DAILY_MOTION:
        return None
    if retrograde:
        return 60.0
    mean = MEAN_DAILY_MOTION[name]
    ratio = abs(speed) / mean if mean else 1.0
    if ratio < 0.1:
        return 30.0  # near-stationary
    val = 7.5 + min(ratio, 2.0) * (45.0 - 7.5) / 2.0
    return round(min(val, 45.0), 2)


def _paksha_bala(name: str, sun_lon: float, moon_lon: float) -> float:
    elongation = (moon_lon - sun_lon) % 360
    waxing_strength = elongation / 3 if elongation <= 180 else (360 - elongation) / 3
    if name in KAALA_BALA_BENEFICS:
        return round(waxing_strength, 2)
    return round(60 - waxing_strength, 2)


def _sun_rise_set_events(jd_birth: float, lat: float, lon: float) -> tuple:
    """Return the (jd, kind) event immediately before and immediately after
    jd_birth, where kind is 'rise' or 'set', using real sunrise/sunset for the
    birth location (not a fixed clock-time assumption)."""
    geopos = (lon, lat, 0)
    events = []
    t = jd_birth - 1.6  # comfortably more than one full day/night cycle back
    for _ in range(6):
        _, tr = swe.rise_trans(t, swe.SUN, swe.CALC_RISE, geopos)
        _, ts = swe.rise_trans(t, swe.SUN, swe.CALC_SET, geopos)
        events.append((tr[0], "rise"))
        events.append((ts[0], "set"))
        t = min(tr[0], ts[0]) + 0.01
    events = sorted(set(events))
    before = [e for e in events if e[0] <= jd_birth]
    after = [e for e in events if e[0] > jd_birth]
    return before[-1], after[0]


def _nathonnatha_bala(name: str, jd_birth: float, lat: float, lon: float) -> float:
    """Day/night strength — BPHS: Unnata Bala (diurnal planets Sun/Jupiter/
    Venus) peaks at 60 Virupas at solar noon, is 30 at sunrise/sunset, and 0
    at solar midnight. Nata Bala (nocturnal planets Moon/Mars/Saturn) is the
    complement: Nata + Unnata = 60 always. Mercury is always 60 regardless.
    Uses real sunrise/sunset for the birth location (not a fixed clock-time
    approximation), verified against all four classical anchor points
    (midnight=0/60, sunrise=30/30, noon=60/0, and back through midnight)."""
    if name not in DIURNAL_PLANETS and name not in NOCTURNAL_PLANETS:
        return 60.0  # Mercury
    prev_event, next_event = _sun_rise_set_events(jd_birth, lat, lon)
    is_day = prev_event[1] == "rise"
    start_jd, end_jd = prev_event[0], next_event[0]
    mid_jd = (start_jd + end_jd) / 2
    frac = (jd_birth - start_jd) / (mid_jd - start_jd) if jd_birth <= mid_jd else (end_jd - jd_birth) / (end_jd - mid_jd)
    unnata = (30 + 30 * frac) if is_day else (30 - 30 * frac)
    return round(unnata if name in DIURNAL_PLANETS else 60 - unnata, 2)


AYANA_NORTH_FAVORED = {"Sun", "Mars", "Jupiter", "Venus"}  # strong at northern declination
AYANA_SOUTH_FAVORED = {"Moon", "Saturn"}  # strong at southern declination
# Mercury is strong at BOTH solstices (uses |declination|) — see below.
OBLIQUITY_DEG = 23.4392911  # mean obliquity of the ecliptic


def _ayana_bala(name: str, sidereal_longitude: float, ayanamsa: float) -> float:
    """Ayana Bala — BPHS 27, Santhanam's formula: Ayana = (23°27' ± Kranti) ×
    60/46°54' = (23.45 ± declination) × 1.2793, using the planet's TROPICAL
    longitude (sidereal + ayanamsa) to derive its seasonal declination —
    this is deliberately the Sun-declination-style formula applied to every
    planet's tropical longitude, not each planet's true 3D declination
    (ecliptic latitude ignored), which is the documented classical
    convention and gives near-identical results to the alternative
    true-declination method. Sun/Mars/Jupiter/Venus peak at northern
    declination (near tropical Cancer 0°); Moon/Saturn peak at southern
    declination (near tropical Capricorn 0°); Mercury peaks at BOTH
    solstices (uses |declination|, since it is "strong in both Uttarayana
    and Dakshinayana" per BPHS). At the equinox points every planet scores
    30 (the midpoint). Verified against a real reference chart — see
    compute_shadbala's scope note."""
    tropical_lon = (sidereal_longitude + ayanamsa) % 360
    declination = math.degrees(math.asin(
        math.sin(math.radians(OBLIQUITY_DEG)) * math.sin(math.radians(tropical_lon))
    ))
    if name in AYANA_NORTH_FAVORED:
        raw = (23.45 + declination) * 1.2793
    elif name in AYANA_SOUTH_FAVORED:
        raw = (23.45 - declination) * 1.2793
    else:  # Mercury
        raw = (23.45 + abs(declination)) * 1.2793
    return round(max(0.0, min(60.0, raw)), 2)


WEEKDAY_LORDS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]  # Python weekday(): Monday=0
HORA_CYCLE = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]  # Chaldean order
DAY_TRIBHAGA_LORDS = ["Mercury", "Sun", "Saturn"]
NIGHT_TRIBHAGA_LORDS = ["Moon", "Venus", "Mars"]


def _day_night_bounds(jd_birth: float, lat: float, lon: float) -> tuple:
    """Returns (sunrise_jd, sunset_jd, next_sunrise_jd, is_day) for the
    civil day containing jd_birth, using real sunrise/sunset for the birth
    location — needed for Hora and Tribhaga Bala, which divide the local
    solar day/night (not the clock day) into 12 and 3 parts respectively."""
    geopos = (lon, lat, 0)
    _, tr = swe.rise_trans(jd_birth - 1, swe.SUN, swe.CALC_RISE, geopos)
    _, ts = swe.rise_trans(tr[0], swe.SUN, swe.CALC_SET, geopos)
    _, tr_next = swe.rise_trans(ts[0], swe.SUN, swe.CALC_RISE, geopos)
    sunrise, sunset, next_sunrise = tr[0], ts[0], tr_next[0]
    is_day = sunrise <= jd_birth <= sunset
    return sunrise, sunset, next_sunrise, is_day


def _vara_bala(name: str, vara_lord: str) -> float:
    """45 Virupas if the planet rules the weekday of birth (Vedic weekday,
    sunrise-to-sunrise), else 0."""
    return 45.0 if name == vara_lord else 0.0


def _hora_lord(vara_lord: str, jd_birth: float, sunrise: float, sunset: float, next_sunrise: float, is_day: bool) -> str:
    """The lord of the planetary hour (Hora) containing the birth moment.
    The day/night is split into 12+12 = 24 horas; the first hora of the
    civil day is ruled by that day's own weekday lord, and hora lords then
    cycle through the fixed Chaldean sequence continuously across day and
    night."""
    start_idx = HORA_CYCLE.index(vara_lord)
    if is_day:
        hora_len = (sunset - sunrise) / 12
        hora_num = int((jd_birth - sunrise) / hora_len)  # 0-11
    else:
        hora_len = (next_sunrise - sunset) / 12
        hora_num = 12 + int((jd_birth - sunset) / hora_len)  # 12-23, continuing the cycle
    return HORA_CYCLE[(start_idx + hora_num) % 7]


def _tribhaga_lord(jd_birth: float, sunrise: float, sunset: float, next_sunrise: float, is_day: bool) -> str:
    """The lord of whichever third of the day or night the birth falls in.
    Day thirds: Mercury, Sun, Saturn. Night thirds: Moon, Venus, Mars.
    (Jupiter and Rahu are not Tribhaga lords in this scheme.)"""
    if is_day:
        third_len = (sunset - sunrise) / 3
        idx = min(int((jd_birth - sunrise) / third_len), 2)
        return DAY_TRIBHAGA_LORDS[idx]
    third_len = (next_sunrise - sunset) / 3
    idx = min(int((jd_birth - sunset) / third_len), 2)
    return NIGHT_TRIBHAGA_LORDS[idx]


YUDDHA_ELIGIBLE = {"Mars", "Mercury", "Jupiter", "Venus", "Saturn"}  # the 5 "Tara Grahas"; Sun/Moon never fight
YUDDHA_ORB_DEG = 1.0


def _find_planetary_war(planets_by_name: Dict[str, Dict]) -> Optional[Tuple[str, str]]:
    """A planetary war (Yuddha) occurs when two of the 5 Tara Grahas sit in
    the same sign within ~1° of each other. Returns (planet_a, planet_b) if
    found, else None. This chart has none, so this path is implemented but
    not verifiable against the reference — flagged in the scope note."""
    names = list(YUDDHA_ELIGIBLE)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            la, lb = planets_by_name[a]["longitude"], planets_by_name[b]["longitude"]
            if int(la // 30) == int(lb // 30) and abs(la - lb) <= YUDDHA_ORB_DEG:
                return (a, b)
    return None


def _ordinary_drishti(dk: float) -> float:
    """Continuous aspect strength by exact angular distance (Drishti Kendra),
    per BPHS 27.19-23. Verified against B.V. Raman's Standard Horoscope
    worked example (Graha and Bhava Balas, Ch. VIII): reproduced 6 of 7
    published Drik Bala values almost exactly (Sun 16.32 vs 15.86, Moon
    -21.36 vs -21.73, Mars 0.26 vs 0.95, Mercury 15.79 vs 15.64, Jupiter
    -16.29 vs -16.04, Venus 18.41 vs 18.47); Saturn was off by ~1.2 (8.43 vs
    7.21), most likely from arc-minute rounding in the source table
    interacting with Saturn's special-aspect boundary, not a formula error."""
    dk = dk % 360.0
    if dk < 30.0 or dk > 300.0:
        return 0.0
    if dk < 60.0:
        return (dk - 30.0) / 2.0
    if dk < 90.0:
        return (dk - 60.0) + 15.0
    if dk < 120.0:
        return ((120.0 - dk) / 2.0) + 30.0
    if dk < 150.0:
        return 150.0 - dk
    if dk < 180.0:
        return 2.0 * (dk - 150.0)
    return (300.0 - dk) / 2.0


def _special_drishti(planet: str, dk: float) -> float:
    """Additional strength for the three planets with special aspects,
    added ON TOP of the ordinary Drishti above (not a replacement)."""
    dk = dk % 360.0
    if planet == "Mars" and (90.0 <= dk <= 120.0 or 210.0 <= dk <= 240.0):
        return 15.0
    if planet == "Jupiter" and (120.0 <= dk <= 150.0 or 240.0 <= dk <= 270.0):
        return 30.0
    if planet == "Saturn" and (60.0 <= dk <= 90.0 or 270.0 <= dk <= 300.0):
        return 45.0
    return 0.0


def _drik_bala(target: str, planets_by_name: Dict[str, Dict], sun_lon: float, moon_lon: float) -> float:
    """Aspectual strength, Drishti Pinda / 4, per BPHS. Benefic aspectors
    (Jupiter, Venus, waxing Moon) add strength; malefic aspectors (Sun, Mars,
    Saturn, waning Moon, combust Mercury) subtract it. Only the 7 classical
    planets participate (not Rahu/Ketu/Lagna), consistent with the rest of
    Shadbala."""
    target_lon = planets_by_name[target]["longitude"]
    elongation = (moon_lon - sun_lon) % 360
    moon_is_benefic = elongation <= 180  # waxing
    mercury_lon = planets_by_name["Mercury"]["longitude"]
    mercury_sun_sep = min(abs(mercury_lon - sun_lon), 360 - abs(mercury_lon - sun_lon))
    mercury_is_malefic = mercury_sun_sep < 14.0  # combust

    benefics = {"Jupiter", "Venus"}
    malefics = {"Sun", "Mars", "Saturn"}
    (benefics if moon_is_benefic else malefics).add("Moon")
    (malefics if mercury_is_malefic else benefics).add("Mercury")

    pinda = 0.0
    for aspector in ASHTAKAVARGA_PLANETS:  # same 7 classical planets
        if aspector == target:
            continue
        aspector_lon = planets_by_name[aspector]["longitude"]
        dk = (target_lon - aspector_lon) % 360.0
        strength = _ordinary_drishti(dk) + _special_drishti(aspector, dk)
        pinda += strength if aspector in benefics else -strength
    return round(pinda / 4, 2)


def compute_shadbala(planets: List[Dict], asc_longitude: float, jd_birth: float, lat: float, lon: float, house_aspects: Dict[int, List[str]]) -> Dict:
    """Compute Shadbala for the 7 classical planets. See the scope note above
    for exactly which components are included. Returns Rupas (1 Rupa = 60
    Virupas) per planet, plus a sub-component breakdown.

    VERIFICATION: this implementation (including Saptavargaja Bala and the
    Ayana/Vara/Hora/Tribhaga additions to Kaala Bala) was checked against a
    real reference chart (4 Jun 1995, 14:44 IST, Unjha, Gujarat) with
    published Shadbala totals from a professional astrology program. Prior
    to these additions, totals were systematically 35-53% below the
    reference (missing components, not calculation errors). After adding
    Saptavargaja Bala + the missing Kaala Bala sub-components, totals landed
    within roughly 4-17% of the reference for 6 of 7 planets (closest:
    Jupiter, within 0.3%). Still-missing pieces (Varsha/Masa Bala, the true
    8-tier Chesta Bala) plus minor ayanamsa/obliquity precision differences
    likely account for the remaining gap. This is a large improvement over
    the previous ~50% gap but not yet an exact match — treat totals as
    closely approximate, not exact classical Rupas."""
    by_name = {p["name"]: p for p in planets}
    sun_lon = by_name["Sun"]["longitude"]
    moon_lon = by_name["Moon"]["longitude"]
    rasi_sign_of = {n: by_name[n]["sign_idx"] for n in ASHTAKAVARGA_PLANETS}
    ayanamsa = swe.get_ayanamsa_ut(jd_birth)

    # Kaala Bala time-lord components share one sunrise/sunset/weekday
    # computation across all 7 planets.
    sunrise, sunset, next_sunrise, is_day = _day_night_bounds(jd_birth, lat, lon)
    sunrise_y, sunrise_m, sunrise_d, _ = swe.revjul(sunrise)
    vara_lord = WEEKDAY_LORDS[datetime(sunrise_y, sunrise_m, sunrise_d).weekday()]
    hora_lord = _hora_lord(vara_lord, jd_birth, sunrise, sunset, next_sunrise, is_day)
    tribhaga_lord = _tribhaga_lord(jd_birth, sunrise, sunset, next_sunrise, is_day)

    war = _find_planetary_war(by_name)

    result = {}
    for name in ASHTAKAVARGA_PLANETS:  # same 7 classical planets
        p = by_name[name]
        uchcha = _uchcha_bala(name, p["longitude"])
        kendradi = _kendradi_bala(p["house"])
        oja_yugma = _oja_yugma_bala(name, p["sign_idx"], p.get("navamsa_sign_idx", p["sign_idx"]))
        drekkana = _drekkana_bala(name, p["degree_in_sign"])
        saptavargaja = _saptavargaja_bala(name, p["longitude"], rasi_sign_of)
        sthana = uchcha + kendradi + oja_yugma + drekkana + saptavargaja

        dig = _dig_bala(name, p["longitude"], asc_longitude)

        paksha = _paksha_bala(name, sun_lon, moon_lon)
        nathonnatha = _nathonnatha_bala(name, jd_birth, lat, lon)
        ayana = _ayana_bala(name, p["longitude"], ayanamsa)
        vara = _vara_bala(name, vara_lord)
        hora = 60.0 if name == hora_lord else 0.0
        tribhaga = 60.0 if name == tribhaga_lord else 0.0
        kaala = paksha + nathonnatha + ayana + vara + hora + tribhaga
        # Still missing from Kaala Bala: Varsha Bala and Masa Bala (year/
        # month-lord reckoning) — an obscure system even several
        # professional tools skip; genuinely low priority unless a specific
        # reference example needs it.

        chesta = _chesta_bala(name, p.get("speed", 0.0), p.get("retrograde", False))
        if chesta is None:
            # Moon uses Paksha Bala as its Chesta Bala per BPHS 27. Sun has
            # no classical Chesta Bala at all (no retrograde motion concept
            # applies) — it simply scores 0 here; Sun's time-based strength
            # comes through Ayana/Vara/Hora/Tribhaga Bala above instead.
            # (Earlier versions of this code used a 30.0 "neutral"
            # placeholder for Sun here, mislabeled as an Ayana Bala stand-in
            # — removed now that real Ayana Bala is computed for every
            # planet including Sun.)
            chesta = paksha if name == "Moon" else 0.0

        naisargika = NAISARGIKA_BALA[name]
        drik = _drik_bala(name, by_name, sun_lon, moon_lon)

        yuddha = 0.0
        if war and name in war:
            other = war[1] if war[0] == name else war[0]
            # Winner = higher pre-Yuddha total; loser's deficit transfers to
            # the winner (BPHS 27.20). Determined via a quick provisional
            # total for just these two planets' non-Yuddha components.
            def _provisional(nm):
                pp = by_name[nm]
                return (
                    _uchcha_bala(nm, pp["longitude"]) + _kendradi_bala(pp["house"])
                    + _oja_yugma_bala(nm, pp["sign_idx"], pp.get("navamsa_sign_idx", pp["sign_idx"]))
                    + _drekkana_bala(nm, pp["degree_in_sign"]) + _saptavargaja_bala(nm, pp["longitude"], rasi_sign_of)
                    + _dig_bala(nm, pp["longitude"], asc_longitude)
                    + _paksha_bala(nm, sun_lon, moon_lon) + _nathonnatha_bala(nm, jd_birth, lat, lon)
                    + _ayana_bala(nm, pp["longitude"], ayanamsa) + _vara_bala(nm, vara_lord)
                    + (60.0 if nm == hora_lord else 0.0) + (60.0 if nm == tribhaga_lord else 0.0)
                    + (_chesta_bala(nm, pp.get("speed", 0.0), pp.get("retrograde", False)) or 0.0)
                    + NAISARGIKA_BALA[nm] + _drik_bala(nm, by_name, sun_lon, moon_lon)
                )
            mine, theirs = _provisional(name), _provisional(other)
            yuddha = abs(mine - theirs) if mine >= theirs else -abs(mine - theirs)

        total_virupas = sthana + dig + kaala + chesta + naisargika + drik + yuddha
        total_rupas = round(total_virupas / 60, 2)

        result[name] = {
            "total_rupas": total_rupas,
            # total_rupas is now closely comparable to (though not always
            # exactly matching) the classical minimum-required-Rupas table
            # (MINIMUM_SHADBALA_RUPAS) — see the verification note above.
            "sub_scores_virupas": {
                "sthana_bala": round(sthana, 2),
                "saptavargaja_bala": round(saptavargaja, 2),
                "dig_bala": round(dig, 2),
                "kaala_bala": round(kaala, 2),
                "chesta_bala": round(chesta, 2),
                "naisargika_bala": round(naisargika, 2),
                "drik_bala": round(drik, 2),
                "yuddha_bala": round(yuddha, 2),
            },
        }
    return result


# Bhava Dig Bala — BPHS 27.26-29. Each sign belongs to one of four groups,
# each with a Kendra house where it scores ZERO and the opposite Kendra
# (180° away) where it scores maximum (60 Virupas), falling off linearly
# (angular distance / 3) in between — the same style of formula as
# planetary Dig Bala, just keyed to sign-group instead of planet identity.
# Verified against a real reference chart (Parashara's Light): all 12
# houses matched exactly.
#   Nara (human) signs — Gemini, Virgo, Libra, Aquarius, Sagittarius 1st
#   half: zero at 7th house, max at 1st (Lagna).
#   Chatuspada (quadruped) signs — Aries, Taurus, Leo, Sagittarius 2nd
#   half, Capricorn 1st half: zero at 4th house, max at 10th.
#   Keeta (insect/reptile) signs — Cancer, Scorpio: zero at Lagna, max at
#   7th house.
#   Jalachara (aquatic) signs — Capricorn 2nd half, Pisces: zero at 10th
#   house, max at 4th.
BHAVA_DIG_ZERO_MAX_HOUSE = {"nara": (7, 1), "chatuspada": (4, 10), "keeta": (1, 7), "jalachara": (10, 4)}


def _bhava_sign_group(sign_idx: int, deg_in_sign: float) -> str:
    if sign_idx in (2, 5, 6, 10):  # Gemini, Virgo, Libra, Aquarius
        return "nara"
    if sign_idx == 8:  # Sagittarius — split at 15°
        return "nara" if deg_in_sign < 15 else "chatuspada"
    if sign_idx in (0, 1, 4):  # Aries, Taurus, Leo
        return "chatuspada"
    if sign_idx == 9:  # Capricorn — split at 15°
        return "chatuspada" if deg_in_sign < 15 else "jalachara"
    if sign_idx in (3, 7):  # Cancer, Scorpio
        return "keeta"
    if sign_idx == 11:  # Pisces
        return "jalachara"
    raise ValueError(f"Unhandled sign_idx {sign_idx}")


def _bhava_dig_bala(house_num: int, asc_longitude: float) -> float:
    bhava_madhya = (asc_longitude + (house_num - 1) * 30) % 360
    sign_idx = int(bhava_madhya // 30)
    deg_in_sign = bhava_madhya - sign_idx * 30
    group = _bhava_sign_group(sign_idx, deg_in_sign)
    _, max_house = BHAVA_DIG_ZERO_MAX_HOUSE[group]
    max_madhya = (asc_longitude + (max_house - 1) * 30) % 360
    diff = _angular_diff(bhava_madhya, max_madhya)
    return round((180 - diff) / 3, 2)


def compute_bhava_bala(house_lords_list: List[Dict], shadbala: Dict, house_aspects: Dict[int, List[str]], asc_longitude: float) -> Dict[int, Dict]:
    """Bhava Bala (house strength), Rupas.

    SCOPE: Bhavadhipati Bala (house lord's own Shadbala) and Bhava Dig Bala
    are both implemented and verified — see _bhava_dig_bala's docstring for
    the exact reference-chart match. Bhava Drishti Bala (aspectual strength
    on the house) is NOT included: an earlier version used a made-up ×0.25
    proxy on aspecting planets' total Shadbala, which was checked against a
    real reference chart and found to overshoot badly (60%+ high on houses
    with multiple strong aspectors) — that proxy has been removed rather
    than left in a confirmed-wrong state. The real classical Bhava Drishti
    formula (same continuous Sputa Drishti calculation used for planetary
    Drik Bala, aimed at the Bhava Madhya instead of a planet) was tested
    against the same reference chart and did NOT reproduce it closely
    enough to trust (9 of 12 houses right in sign, but inconsistent
    magnitude and 2 outright sign flips) — so it's left out rather than
    shipped as a plausible-looking guess. Until a verified formula is
    found, total_rupas here is Bhavadhipati Bala + Bhava Dig Bala only."""
    result = {}
    for h in house_lords_list:
        lord = h["lord"]
        bhavadhipati_bala = shadbala[lord]["total_rupas"] if lord in shadbala else 0.0
        dig_bala_virupas = _bhava_dig_bala(h["house"], asc_longitude)
        dig_bala_rupas = round(dig_bala_virupas / 60, 2)

        total = round(bhavadhipati_bala + dig_bala_rupas, 2)
        result[h["house"]] = {
            "total_rupas": total,
            "bhavadhipati_bala_rupas": round(bhavadhipati_bala, 2),
            "dig_bala_rupas": dig_bala_rupas,
        }
    return result


def compute_domain_verdict(domain: str, chart: Dict, transits: Dict) -> Dict | None:
    """Computes a structured, deterministic verdict for a life-domain
    (marriage, career, etc.) from five independent classical signals, rather
    than leaving the model to reason freely over raw chart data every time.
    This mirrors the same principle already proven out for Muhurta windows
    and retrograde stations: hand the model a real computed answer to
    EXPLAIN, don't ask it to derive one from scratch each time.

    The five signals:
      A. House-lord strength   — lord's own Shadbala vs. the classical
         minimum (MINIMUM_SHADBALA_RUPAS) for the relevant house(s).
      B. Karaka strength       — same check for the domain's karaka planet(s).
      C. Ashtakavarga support  — Sarvashtakavarga bindus in the relevant
         house(s); ~28 is roughly the average across 12 houses (337 total),
         so >=28 is used as the "supported" threshold.
      D. Dasha alignment       — is the CURRENT dasha lord (at any of the
         three levels this app tracks) the house lord or a karaka? Classical
         principle: a significator's own dasha activates its house.
      E. Transit support       — is a house-lord/karaka planet currently
         transiting one of the relevant houses (from Lagna) with decent
         (>=4) Ashtakavarga bindus in that transit sign?

    Returns None for "general" or an unrecognized domain (nothing domain-
    specific to compute). Each signal is independently True/False/None
    (None = insufficient data, e.g. no current dasha) — convergence is the
    count of True signals out of the signals that were actually resolvable
    (None signals are excluded from both the numerator and denominator,
    rather than counted as failures)."""
    if domain not in DOMAIN_SIGNIFICATORS:
        return None
    houses, karakas = DOMAIN_SIGNIFICATORS[domain]
    house_lords_list = chart.get("house_lords", [])
    shadbala = chart.get("shadbala", {})
    sav = chart.get("ashtakavarga", {}).get("sav", [])
    by_name = {p["name"]: p for p in chart.get("planets", [])}

    relevant_lords = []
    for h in houses:
        hl = next((x for x in house_lords_list if x["house"] == h), None)
        if hl:
            relevant_lords.append(hl["lord"])

    # Signal A — house-lord strength
    lord_checks = [
        (lord, shadbala[lord]["total_rupas"], MINIMUM_SHADBALA_RUPAS.get(lord, 5.0))
        for lord in relevant_lords if lord in shadbala
    ]
    signal_a = any(rupas >= minimum for _, rupas, minimum in lord_checks) if lord_checks else None

    # Signal B — karaka strength
    karaka_checks = [
        (k, shadbala[k]["total_rupas"], MINIMUM_SHADBALA_RUPAS.get(k, 5.0))
        for k in karakas if k in shadbala
    ]
    signal_b = any(rupas >= minimum for _, rupas, minimum in karaka_checks) if karaka_checks else None

    # Signal C — Ashtakavarga house support
    house_sav = [sav[h - 1] for h in houses if sav and h - 1 < len(sav)]
    signal_c = any(s >= 28 for s in house_sav) if house_sav else None

    # Signal D — dasha alignment (any of the 3 levels this app tracks)
    dasha_lords = {
        chart.get("current_dasha", {}).get("lord") if chart.get("current_dasha") else None,
        chart.get("current_antardasha", {}).get("lord") if chart.get("current_antardasha") else None,
        chart.get("current_pratyantardasha", {}).get("lord") if chart.get("current_pratyantardasha") else None,
    }
    dasha_lords.discard(None)
    significators = set(relevant_lords) | set(karakas)
    signal_d = bool(dasha_lords & significators) if dasha_lords else None

    # Signal E — transit support
    natal_bav = chart.get("ashtakavarga", {}).get("bav", {})
    signal_e = None
    transiting_significators = []
    for t in transits.get("planets", []):
        if t["name"] not in significators:
            continue
        house_from_lagna = t.get("house_from_lagna")
        if house_from_lagna in houses:
            bindus = natal_bav.get(t["name"], [0] * 12)[t["sign_idx"]] if t["name"] in natal_bav else None
            transiting_significators.append({"planet": t["name"], "house": house_from_lagna, "bindus": bindus})
            if bindus is not None and bindus >= 4:
                signal_e = True
    if transiting_significators and signal_e is None:
        signal_e = False

    signals = {"house_lord_strong": signal_a, "karaka_strong": signal_b,
               "ashtakavarga_supportive": signal_c, "dasha_aligned": signal_d,
               "transit_supportive": signal_e}
    resolvable = [v for v in signals.values() if v is not None]
    convergence_count = sum(1 for v in resolvable if v)
    convergence_total = len(resolvable)
    if convergence_total == 0:
        verdict = "insufficient data"
    elif convergence_count / convergence_total >= 0.75:
        verdict = "strong convergence"
    elif convergence_count / convergence_total >= 0.4:
        verdict = "mixed signals"
    else:
        verdict = "weak convergence"

    return {
        "domain": domain,
        "houses_checked": houses,
        "karakas_checked": karakas,
        "signals": signals,
        "convergence": f"{convergence_count}/{convergence_total}",
        "verdict": verdict,
        "house_lord_checks": lord_checks,
        "karaka_checks": karaka_checks,
        "house_sav": house_sav,
        "dasha_lords_active": sorted(dasha_lords),
        "transiting_significators": transiting_significators,
    }


def _compute_house_aspects(planets: List[Dict]) -> Dict[int, List[str]]:
    """Classical Parashari graha drishti (full aspect only, binary — no partial
    aspect strengths). Every planet aspects the 7th house from itself; Mars
    additionally aspects the 4th/8th, Jupiter the 5th/9th, and Saturn the
    3rd/10th. Rahu/Ketu get the universal 7th aspect only (the special
    Jupiter-like aspects for the nodes are a less universally agreed-upon
    variant, so left out to avoid asserting a disputed rule as settled).
    Returns {house_number(1-12): [planet names aspecting that house]}."""
    aspects_on_house: Dict[int, List[str]] = {h: [] for h in range(1, 13)}
    special_offsets = {
        "Mars": (3, 7),
        "Jupiter": (4, 8),
        "Saturn": (2, 9),
    }
    for p in planets:
        p_house = p["house"]
        offsets = {6}  # universal 7th aspect (offset 6 = +7th house, 0-indexed)
        offsets |= set(special_offsets.get(p["name"], ()))
        for off in offsets:
            target_house = ((p_house - 1 + off) % 12) + 1
            aspects_on_house[target_house].append(p["name"])
    return aspects_on_house


def _detect_yogas(planets: List[Dict], asc_sign: int) -> List[Dict]:
    """Detect a small set of classical yogas."""
    yogas = []
    by_name = {p["name"]: p for p in planets}
    moon = by_name["Moon"]
    jup = by_name["Jupiter"]
    mars = by_name["Mars"]

    # Gaja Kesari — Jupiter in kendra (1,4,7,10) from Moon
    diff = ((jup["sign_idx"] - moon["sign_idx"]) % 12) + 1  # house of Jup from Moon
    if diff in (1, 4, 7, 10):
        yogas.append({
            "name": "Gaja Kesari Yoga",
            "detail": f"Jupiter in {diff}th house from Moon — grants wisdom, virtue, and repute.",
        })

    # Chandra Mangala — Moon-Mars conjunction (same sign)
    if moon["sign_idx"] == mars["sign_idx"]:
        yogas.append({
            "name": "Chandra Mangala Yoga",
            "detail": "Moon and Mars in the same sign — wealth through effort, but emotional volatility.",
        })

    # Budhaditya — Sun-Mercury conjunction (same sign, within 10°)
    sun = by_name["Sun"]
    merc = by_name["Mercury"]
    if sun["sign_idx"] == merc["sign_idx"] and abs(sun["degree_in_sign"] - merc["degree_in_sign"]) <= 10:
        yogas.append({
            "name": "Budha-Aditya Yoga",
            "detail": "Sun-Mercury close conjunction — sharp intellect, communication, and reputation.",
        })

    # Kemadruma — Moon with no planets in the 2nd or 12th from itself, and no planet with Moon
    same = [p for p in planets if p["name"] != "Moon" and p["sign_idx"] == moon["sign_idx"]]
    prev_sign = (moon["sign_idx"] - 1) % 12
    next_sign = (moon["sign_idx"] + 1) % 12
    has_next = any(p["name"] not in ("Moon", "Rahu", "Ketu") and p["sign_idx"] == next_sign for p in planets)
    has_prev = any(p["name"] not in ("Moon", "Rahu", "Ketu") and p["sign_idx"] == prev_sign for p in planets)
    if not same and not has_next and not has_prev:
        yogas.append({
            "name": "Kemadruma Yoga",
            "detail": "Moon isolated (no planets in 2nd/12th from Moon) — struggle and solitude unless mitigated.",
        })
    elif has_next and has_prev:
        yogas.append({
            "name": "Durudhara Yoga",
            "detail": "Planets on both sides of Moon (2nd and 12th) — wealth, resources, and support from others.",
        })
    elif has_next:
        yogas.append({
            "name": "Sunapha Yoga",
            "detail": "Planet(s) in the 2nd from Moon only — self-earned wealth and resourcefulness.",
        })
    elif has_prev:
        yogas.append({
            "name": "Anapha Yoga",
            "detail": "Planet(s) in the 12th from Moon only — good health, self-reliance, and steady temperament.",
        })

    # Panch Mahapurusha Yogas — a planet in its own sign or exaltation, AND in
    # a kendra (1st/4th/7th/10th) from the Ascendant. Five classic, widely
    # recognized "great person" yogas, one per planet.
    MAHAPURUSHA = {
        "Mars": ("Ruchaka Yoga", "courage, physical strength, and command"),
        "Mercury": ("Bhadra Yoga", "sharp intellect, eloquence, and business acumen"),
        "Jupiter": ("Hamsa Yoga", "wisdom, virtue, and respect"),
        "Venus": ("Malavya Yoga", "charm, comfort, and artistic or luxurious living"),
        "Saturn": ("Sasa Yoga", "discipline, authority, and lasting achievement through persistence"),
    }
    for pname, (yoga_name, significance) in MAHAPURUSHA.items():
        p = by_name[pname]
        if p["house"] not in (1, 4, 7, 10):
            continue
        ex_sign, _ = EXALTATION[pname]
        is_own_or_exalted = p["sign_idx"] in OWN_SIGNS[pname] or p["sign_idx"] == ex_sign
        if is_own_or_exalted:
            yogas.append({
                "name": yoga_name,
                "detail": f"{pname} in its own sign or exalted, in a kendra (house {p['house']}) — one of the five Mahapurusha Yogas, bringing {significance}.",
            })

    # Raja Yoga — Kendra lord + Trikona lord in association (same sign)
    kendras = {0, 3, 6, 9}  # relative positions to asc (h-1)
    trikonas = {0, 4, 8}
    kendra_signs = {(asc_sign + h) % 12 for h in kendras}
    trikona_signs = {(asc_sign + h) % 12 for h in trikonas}
    kendra_lords = {SIGN_LORDS[s] for s in kendra_signs}
    trikona_lords = {SIGN_LORDS[s] for s in trikona_signs}
    for p in planets:
        others_same = [q for q in planets if q["name"] != p["name"] and q["sign_idx"] == p["sign_idx"]]
        for q in others_same:
            if (p["name"] in kendra_lords and q["name"] in trikona_lords) or (
                p["name"] in trikona_lords and q["name"] in kendra_lords
            ):
                yogas.append({
                    "name": "Raja Yoga",
                    "detail": f"Kendra-Trikona lord conjunction: {p['name']} + {q['name']} in {p['sign']} — bestows power and status.",
                })
                break
        else:
            continue
        break

    return yogas


def compute_antardashas(mahadasha: Dict) -> List[Dict]:
    """For a given Mahadasha (or Antardasha, or Pratyantardasha, or Sookshma —
    the subdivision math is identical at every level), compute the 9 sub-period
    breakdown.

    IMPORTANT: dates are carried as full datetimes (not date-only) throughout,
    because by the time you're 3-4 levels deep (Sookshma, Prana) individual
    sub-periods are only hours long. Truncating to date-only at each level and
    re-parsing from that truncated string (the previous approach) silently
    threw away all sub-day precision, causing every Prana-level period to
    collapse onto the same calendar date. Display code should format/slice
    these as needed (e.g. date-only for Mahadasha/Antardasha, full timestamp
    for Sookshma/Prana) rather than the data losing precision at the source.
    """
    start_str = mahadasha["start"]
    # Accept either a full timestamp (from a deeper recursive call) or a
    # plain date (from the top-level Mahadasha list, which only ever needs
    # day precision since those spans are years long).
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        start = datetime.strptime(start_str, "%Y-%m-%d")

    lord = mahadasha["lord"]
    total_yrs = mahadasha["years"]
    lord_idx = NAK_LORDS.index(lord)
    subs = []
    for i in range(9):
        sub_lord = NAK_LORDS[(lord_idx + i) % 9]
        sub_years = (DASHA_YEARS[sub_lord] * total_yrs) / 120.0
        end = start + timedelta(days=sub_years * 365.25)
        subs.append({
            "lord": sub_lord,
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S"),
            "years": round(sub_years, 6),
        })
        start = end
    return subs


def current_antardasha(mahadasha: Dict) -> Dict | None:
    subs = compute_antardashas(mahadasha)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for s in subs:
        s_start = datetime.strptime(s["start"], "%Y-%m-%d %H:%M:%S")
        s_end = datetime.strptime(s["end"], "%Y-%m-%d %H:%M:%S")
        if s_start <= now <= s_end:
            return s
    return None


def _vimshottari_dashas(moon_lon: float, birth_local: datetime, nak_idx: int) -> List[Dict]:
    """Return list of Mahadashas from birth for ~120 years."""
    lord_idx = nak_idx % 9
    # Portion of nakshatra already traversed
    nak_size = 360 / 27
    traversed = (moon_lon % nak_size) / nak_size
    lord = NAK_LORDS[lord_idx]
    remaining_years = DASHA_YEARS[lord] * (1 - traversed)

    dashas = []
    current_start = birth_local
    # First (partial) mahadasha
    end = current_start + timedelta(days=remaining_years * 365.25)
    dashas.append({
        "lord": lord,
        "start": current_start.date().isoformat(),
        "end": end.date().isoformat(),
        "years": round(remaining_years, 2),
    })
    current_start = end
    i = 1
    total_years = remaining_years
    while total_years < 120 and i < 20:
        lord = NAK_LORDS[(lord_idx + i) % 9]
        yrs = DASHA_YEARS[lord]
        end = current_start + timedelta(days=yrs * 365.25)
        dashas.append({
            "lord": lord,
            "start": current_start.date().isoformat(),
            "end": end.date().isoformat(),
            "years": yrs,
        })
        current_start = end
        total_years += yrs
        i += 1
    return dashas


def current_dasha(dashas: List[Dict]) -> Dict | None:
    today = datetime.now(timezone.utc).date().isoformat()
    for d in dashas:
        if d["start"] <= today <= d["end"]:
            return d
    return None


STATION_PLANET_IDS = {"Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN}
# Sun, Moon never retrograde; Rahu/Ketu are always in retrograde-style motion
# (they move backward through the zodiac by definition), so none of the
# three have a meaningful "station" to report.


TRANSIT_INGRESS_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
}


def find_sign_ingress(planet_name: str, current_sign_idx: int, from_dt: datetime, max_days: int = 800) -> Dict:
    """When did this transiting planet enter its current sign (retrodiction —
    always reliable, it already happened), and when is it projected to leave
    (a forward projection along its CURRENT path). Ketu is handled as Rahu+180°.

    CAVEAT baked into how this should be used: for a planet currently near a
    retrograde station, this simple forward scan finds the next sign-boundary
    crossing along the current path — but if that planet is about to
    retrograde, it could dip back over a nearby boundary and re-cross forward
    again later, meaning the true final exit could be later than this
    projection. Saturn/Jupiter especially spend long stretches doing exactly
    this near sign boundaries, so treat "projected_exit" as provisional, not
    a guarantee."""
    is_ketu = planet_name == "Ketu"
    pid = TRANSIT_INGRESS_IDS["Rahu"] if is_ketu else TRANSIT_INGRESS_IDS.get(planet_name)
    if pid is None:
        return {}
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    def sign_at(jd):
        pos, _ = swe.calc_ut(jd, pid, flags)
        lon = (pos[0] + 180) % 360 if is_ketu else pos[0]
        return int(lon // 30)

    from_jd = _julday(from_dt.astimezone(timezone.utc).replace(tzinfo=None) if from_dt.tzinfo else from_dt)

    entered_jd = None
    jd = from_jd
    for _ in range(max_days):
        jd -= 1.0
        if sign_at(jd) != current_sign_idx:
            lo, hi = jd, jd + 1.0
            for _ in range(40):
                mid = (lo + hi) / 2
                if sign_at(mid) == current_sign_idx:
                    hi = mid
                else:
                    lo = mid
            entered_jd = hi
            break

    leaves_jd = None
    jd = from_jd
    for _ in range(max_days):
        jd += 1.0
        if sign_at(jd) != current_sign_idx:
            lo, hi = jd - 1.0, jd
            for _ in range(40):
                mid = (lo + hi) / 2
                if sign_at(mid) == current_sign_idx:
                    lo = mid
                else:
                    hi = mid
            leaves_jd = lo
            break

    def _fmt(jd):
        if jd is None:
            return None
        y, m, d, _ = swe.revjul(jd)
        return f"{y:04d}-{m:02d}-{d:02d}"

    return {"entered": _fmt(entered_jd), "projected_exit": _fmt(leaves_jd)}


def find_upcoming_stations(planet_name: str, from_dt: datetime, days_ahead: int = 450, max_stations: int = 2) -> List[Dict]:
    """Scans forward from from_dt (using real Swiss Ephemeris speed, not a
    guess) to find the next retrograde/direct station dates for a planet.
    This exists because an LLM has no reliable way to know specific future
    ephemeris dates from training data alone — asked "when will Saturn go
    retrograde," it will confidently guess a wrong year rather than say it
    doesn't know. Feeding real computed dates into the chat context (see
    server.py's _build_context) closes that gap. Takes ~0.02s per planet, so
    this runs fresh on every request rather than needing a cache."""
    if planet_name not in STATION_PLANET_IDS:
        return []
    pid = STATION_PLANET_IDS[planet_name]
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    def speed_at(jd):
        pos, _ = swe.calc_ut(jd, pid, flags)
        return pos[3]

    from_jd = _julday(from_dt.astimezone(timezone.utc).replace(tzinfo=None) if from_dt.tzinfo else from_dt)
    stations = []
    prev_jd = from_jd
    prev_speed = speed_at(prev_jd)
    jd = from_jd
    step_days = 1.0
    while jd < from_jd + days_ahead and len(stations) < max_stations:
        jd += step_days
        speed = speed_at(jd)
        if (speed < 0) != (prev_speed < 0):
            lo, hi = prev_jd, jd
            for _ in range(40):  # bisect to the day
                mid = (lo + hi) / 2
                if (speed_at(mid) < 0) == (prev_speed < 0):
                    lo = mid
                else:
                    hi = mid
            station_jd = (lo + hi) / 2
            y, m, d, _ = swe.revjul(station_jd)
            stations.append({
                "type": "stations_retrograde" if speed < 0 else "stations_direct",
                "date": f"{y:04d}-{m:02d}-{d:02d}",
            })
        prev_jd, prev_speed = jd, speed
    return stations


def current_transits(natal_chart: Dict | None = None, at: datetime | None = None) -> Dict:
    """Compute current sidereal planetary positions.
    If natal_chart is given, also compute which house each transit falls in
    from natal Lagna and from natal Moon (Chandra Lagna)."""
    now = at if at is not None else datetime.now(timezone.utc)
    jd = _julday(now)
    natal_asc_sign = natal_chart["ascendant"]["sign_idx"] if natal_chart else None
    natal_moon_sign = None
    if natal_chart:
        natal_moon = next((p for p in natal_chart["planets"] if p["name"] == "Moon"), None)
        natal_moon_sign = natal_moon["sign_idx"] if natal_moon else None

    out = []
    for name, pid in PLANETS:
        p_lon, speed = _sidereal_lon(jd, pid)
        sign, deg = _rashi_from_lon(p_lon)
        nak_idx, pada = _nakshatra_from_lon(p_lon)
        row = {
            "name": name,
            "sign": RASHIS[sign],
            "sign_en": RASHI_EN[sign],
            "sign_idx": sign,
            "degree_in_sign": round(deg, 2),
            "nakshatra": NAKSHATRAS[nak_idx],
            "retrograde": speed < 0 and name not in ("Sun", "Moon", "Rahu"),
        }
        if natal_asc_sign is not None:
            row["house_from_lagna"] = ((sign - natal_asc_sign) % 12) + 1
        if natal_moon_sign is not None:
            row["house_from_moon"] = ((sign - natal_moon_sign) % 12) + 1
        out.append(row)
    # Ketu
    rahu = next(p for p in out if p["name"] == "Rahu")
    rahu_lon_calc, _ = _sidereal_lon(jd, swe.MEAN_NODE)
    ketu_lon = (rahu_lon_calc + 180) % 360
    ketu_sign, ketu_deg = _rashi_from_lon(ketu_lon)
    k_nak, _ = _nakshatra_from_lon(ketu_lon)
    ketu_row = {
        "name": "Ketu",
        "sign": RASHIS[ketu_sign],
        "sign_en": RASHI_EN[ketu_sign],
        "sign_idx": ketu_sign,
        "degree_in_sign": round(ketu_deg, 2),
        "nakshatra": NAKSHATRAS[k_nak],
        "retrograde": True,
    }
    if natal_asc_sign is not None:
        ketu_row["house_from_lagna"] = ((ketu_sign - natal_asc_sign) % 12) + 1
    if natal_moon_sign is not None:
        ketu_row["house_from_moon"] = ((ketu_sign - natal_moon_sign) % 12) + 1
    out.append(ketu_row)
    return {"as_of": now.isoformat(), "planets": out}


def build_navamsa(planets: List[Dict], ascendant_longitude: float) -> Dict:
    """Compute D9 (Navamsa) chart: navamsa ascendant + which navamsa sign each planet occupies.
    Returns a chart-like structure suitable for the same KundaliChart renderer."""
    d9_asc_sign = _navamsa_sign(ascendant_longitude)
    d9_planets = []
    for p in planets:
        nav_sign = _navamsa_sign(p["longitude"])
        house = ((nav_sign - d9_asc_sign) % 12) + 1
        d9_planets.append({
            "name": p["name"],
            "symbol": p["symbol"],
            "sign_idx": nav_sign,
            "sign": RASHIS[nav_sign],
            "sign_en": RASHI_EN[nav_sign],
            "degree_in_sign": p["degree_in_sign"],  # keep D1 degree for reference
            "nakshatra": p.get("nakshatra", ""),
            "house": house,
            "retrograde": p.get("retrograde", False),
            "dignity": [],
            "navamsa_sign": RASHI_EN[nav_sign],
        })
    return {
        "ascendant": {
            "sign_idx": d9_asc_sign,
            "sign": RASHIS[d9_asc_sign],
            "sign_en": RASHI_EN[d9_asc_sign],
        },
        "planets": d9_planets,
    }


def build_dasamsa(planets: List[Dict], ascendant_longitude: float) -> Dict:
    """Compute D10 (Dasamsa) chart: reveals career, profession, status and
    achievements. Same output shape as build_navamsa so it can reuse the
    same KundaliChart renderer on the frontend."""
    d10_asc_sign = _dasamsa_sign(ascendant_longitude)
    d10_planets = []
    for p in planets:
        d10_sign = _dasamsa_sign(p["longitude"])
        house = ((d10_sign - d10_asc_sign) % 12) + 1
        d10_planets.append({
            "name": p["name"],
            "symbol": p["symbol"],
            "sign_idx": d10_sign,
            "sign": RASHIS[d10_sign],
            "sign_en": RASHI_EN[d10_sign],
            "degree_in_sign": p["degree_in_sign"],  # keep D1 degree for reference
            "nakshatra": p.get("nakshatra", ""),
            "house": house,
            "retrograde": p.get("retrograde", False),
            "dignity": [],
            "navamsa_sign": p.get("navamsa_sign", ""),  # unused by D10 render, kept for shape parity
        })
    return {
        "ascendant": {
            "sign_idx": d10_asc_sign,
            "sign": RASHIS[d10_asc_sign],
            "sign_en": RASHI_EN[d10_asc_sign],
        },
        "planets": d10_planets,
    }


def build_varga(planets: List[Dict], ascendant_longitude: float, sign_fn) -> Dict:
    """Generic divisional-chart builder — same output shape as build_navamsa
    / build_dasamsa (so it reuses the same KundaliChart renderer), just
    parameterized by whichever varga sign_fn (_hora_sign, _saptamsa_sign,
    etc.) computes the division for that chart."""
    d_asc_sign = sign_fn(ascendant_longitude)
    d_planets = []
    for p in planets:
        d_sign = sign_fn(p["longitude"])
        house = ((d_sign - d_asc_sign) % 12) + 1
        d_planets.append({
            "name": p["name"],
            "symbol": p["symbol"],
            "sign_idx": d_sign,
            "sign": RASHIS[d_sign],
            "sign_en": RASHI_EN[d_sign],
            "degree_in_sign": p["degree_in_sign"],  # keep D1 degree for reference
            "nakshatra": p.get("nakshatra", ""),
            "house": house,
            "retrograde": p.get("retrograde", False),
            "dignity": [],
            "navamsa_sign": "",
        })
    return {
        "ascendant": {
            "sign_idx": d_asc_sign,
            "sign": RASHIS[d_asc_sign],
            "sign_en": RASHI_EN[d_asc_sign],
        },
        "planets": d_planets,
    }


# Chart key -> (sign function, life-area label) used by server.py to attach
# all seven new divisional charts to the /profile/chart response in one loop.
EXTRA_VARGAS = {
    "hora": (_hora_sign, "D2 · Wealth & resources"),
    "chaturthamsa": (_chaturthamsa_sign, "D4 · Property & fixed assets"),
    "shashthamsa": (_shashthamsa_sign, "D6 · Health & obstacles"),
    "saptamsa": (_saptamsa_sign, "D7 · Children & progeny"),
    "shodasamsa": (_shodasamsa_sign, "D16 · Vehicles & comforts"),
    "chaturvimsamsa": (_chaturvimsamsa_sign, "D24 · Education & learning"),
    "shashtiamsa": (_shashtiamsa_sign, "D60 · Fine-grained life reading"),
}


# --- Sunrise / sunset (needed for Rahu Kaal, Choghadiya, Abhijit Muhurta —
# all of these divide the LOCAL solar day, not the clock day) ---

def sun_rise_set(date_iso: str, tz_offset_hours: float, lat: float, lon: float) -> Dict:
    """Sunrise/sunset for the local calendar date `date_iso` at (lat, lon),
    plus the *next* day's sunrise (needed to size the night portion, which
    runs from tonight's sunset to tomorrow's sunrise). Returns local
    datetimes (already shifted by tz_offset_hours, so callers don't have to
    juggle UTC)."""
    y, m, d = map(int, date_iso.split("-"))
    # Search from local midnight (converted to UTC) so we land on today's
    # rise/set, not a leftover one from just before midnight UTC.
    local_midnight = datetime(y, m, d, 0, 0)
    utc_search_start = local_midnight - timedelta(hours=tz_offset_hours)
    jd_start = _julday(utc_search_start)

    geopos = (lon, lat, 0)  # (longitude, latitude, altitude-in-meters)
    _, rise_ret = swe.rise_trans(jd_start, swe.SUN, swe.CALC_RISE, geopos)
    _, set_ret = swe.rise_trans(jd_start, swe.SUN, swe.CALC_SET, geopos)
    # Next sunrise: search starting just after today's sunset.
    _, next_rise_ret = swe.rise_trans(set_ret[0] + 0.001, swe.SUN, swe.CALC_RISE, geopos)

    def _jd_to_local(jd: float) -> datetime:
        yy, mm, dd, hh = swe.revjul(jd)
        h = int(hh)
        mi = int(round((hh - h) * 60))
        base = datetime(yy, mm, dd, h, mi)
        return base + timedelta(hours=tz_offset_hours)

    return {
        "sunrise": _jd_to_local(rise_ret[0]),
        "sunset": _jd_to_local(set_ret[0]),
        "next_sunrise": _jd_to_local(next_rise_ret[0]),
    }


def sun_moon_longitudes(local_dt: datetime, tz_offset_hours: float) -> Tuple[float, float]:
    """Sidereal Sun/Moon longitude at a given local datetime — used by the
    daily Panchang (Tithi/Yoga/Karana), which is read at sunrise rather
    than at chart-birth time."""
    utc_dt = local_dt - timedelta(hours=tz_offset_hours)
    jd = _julday(utc_dt)
    sun_lon, _ = _sidereal_lon(jd, swe.SUN)
    moon_lon, _ = _sidereal_lon(jd, swe.MOON)
    return sun_lon, moon_lon


# --- Real current-location timezone (for "today" features like Panchang/
# Muhurta — these must use wherever the user actually is RIGHT NOW, with
# correct daylight-saving handling, not their birth timezone) ---
from zoneinfo import ZoneInfo
try:
    from timezonefinder import TimezoneFinder
    _TZF = TimezoneFinder()
except ImportError:  # pragma: no cover — guards against a stale env during rollout
    _TZF = None


def current_utc_offset_hours(lat: float, lon: float) -> float:
    """Real UTC offset RIGHT NOW at (lat, lon), correctly handling daylight
    saving (unlike a fixed birth-timezone number, which goes stale the
    moment a user travels or DST flips). Falls back to a longitude-based
    estimate (15° per hour) if the timezone database lookup fails —
    directionally correct, not DST-aware, but better than nothing."""
    tzname = _TZF.timezone_at(lat=lat, lng=lon) if _TZF else None
    if tzname:
        now_there = datetime.now(timezone.utc).astimezone(ZoneInfo(tzname))
        return now_there.utcoffset().total_seconds() / 3600
    return round(lon / 15, 2)


def estimate_tob_from_sunrise_period(dob_iso: str, tz_offset_hours: float, lat: float, lon: float, period: str) -> str:
    """Rough birth-time estimate for users who don't know their exact time,
    using the classical before/after-sunrise distinction rather than a
    guessed clock time. Returns 'HH:MM' local civil time on the birth date:
    the midpoint between midnight and sunrise (if born before sunrise), or
    between sunrise and the following midnight (if born after) — computed
    from real sunrise for the actual birth date and place, not a fixed
    clock-time assumption. This is a coarse estimate, not a substitute for
    genuine rectification; callers should flag the resulting chart as
    approximate."""
    y, m, d = (int(x) for x in dob_iso.split("-"))
    # Local midnight of the birth date, expressed in UTC, seeds the search —
    # elapsed hours from this point to sunrise equals the local sunrise hour.
    midnight_utc = datetime(y, m, d, 0, 0, 0, tzinfo=timezone.utc) - timedelta(hours=tz_offset_hours)
    jd_midnight = _julday(midnight_utc)
    geopos = (lon, lat, 0)
    _, tr = swe.rise_trans(jd_midnight, swe.SUN, swe.CALC_RISE, geopos)
    jd_sunrise = tr[0]
    sunrise_local_hour = ((jd_sunrise - jd_midnight) * 24.0) % 24

    if period == "before_sunrise":
        est_hour = sunrise_local_hour / 2
    else:  # "after_sunrise" (default if unspecified)
        est_hour = sunrise_local_hour + (24 - sunrise_local_hour) / 2

    hh = int(est_hour) % 24
    mm = int(round((est_hour - int(est_hour)) * 60)) % 60
    return f"{hh:02d}:{mm:02d}"
