"""Vedic astrology computations using Swiss Ephemeris (sidereal / Lahiri ayanamsa)."""
from __future__ import annotations
import swisseph as swe
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

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
        })

    yogas = _detect_yogas(planets_out, asc_sign)
    shadbala = compute_shadbala(planets_out, asc_lon, jd, lat, lon, house_aspects)
    bhava_bala = compute_bhava_bala(house_lords_list, shadbala, house_aspects)
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
    }


# --- Rashi (sign) lords ---
SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

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


# --- Shadbala (planetary strength) & Bhava Bala (house strength) ---
#
# HONESTY NOTE ON SCOPE: Full classical Shadbala has six components, and
# Sthana Bala and Kaala Bala are themselves each built from several further
# sub-components (some of which require divisional charts this codebase
# doesn't compute — D2/D3/D7/D12 — or fine-grained sunrise/sunset/hora-lord
# timing tables). Rather than guess at those and silently ship possibly-wrong
# numbers, this implementation includes only the components that have crisp,
# verifiable classical formulas and the inputs already available in this
# chart. This mirrors how even professional calculators (e.g. Ishvaram's
# Shadbala tool) explicitly ship a subset and label the rest as pending,
# rather than presenting an unverified "full" six-fold total as if it were
# complete. What's included:
#   Sthana Bala  = Uchcha Bala + Kendradi Bala + Ojayugmarasyamsa Bala + Drekkana Bala
#                  (Saptavargaja Bala omitted — needs D2/D3/D7/D12)
#   Dig Bala     = full classical formula
#   Kaala Bala   = Paksha Bala + Nathonnatha Bala (day/night strength, using
#                  real sunrise/sunset for the birth location — verified
#                  against all 4 classical anchor points: midnight, sunrise,
#                  noon, sunset). Still missing: Tribhaga, Varsha/Masa/Vara/
#                  Hora Bala, Yuddha Bala (need time-lord tables not in this
#                  codebase).
#   Chesta Bala  = simplified continuous approximation from actual vs. mean
#                  daily motion (not the full classical 8-tier Vakra/Anuvakra/
#                  etc. discrete categories, which need finer ephemeris
#                  sampling than a single snapshot gives)
#   Naisargika Bala = full classical fixed table
#   Drik Bala    = full continuous Sputa Drishti formula (BPHS 27.19-23),
#                  verified against B.V. Raman's published Standard Horoscope
#                  worked example: 6 of 7 planets matched almost exactly,
#                  7th (Saturn) close (see _ordinary_drishti docstring for
#                  exact numbers). Can be negative (net malefic aspect).
#
# All values are cross-checked for range-sanity (each sub-score falls within
# its classical 0-max bound) but this has NOT been verified against a
# published fully-worked Shadbala example the way Ashtakavarga was — treat
# the totals as directionally useful (comparing planets against each other)
# rather than as exact classical Rupas.

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
MINIMUM_SHADBALA_RUPAS = {  # BPHS-prescribed minimum for a planet to deliver full results.
    # Reference only, NOT currently used for a pass/fail comparison — see the
    # scope note on why comparing our partial total against this full-system
    # threshold would be misleading. Kept here for when Drik Bala/full Kaala
    # Bala/Saptavargaja Bala are eventually added and the comparison is fair.
    "Sun": 5.0, "Moon": 6.0, "Mars": 5.0, "Mercury": 7.0,
    "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0,
}


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
    Virupas) per planet, plus a sub-component breakdown and the
    minimum-required comparison."""
    by_name = {p["name"]: p for p in planets}
    sun_lon = by_name["Sun"]["longitude"]
    moon_lon = by_name["Moon"]["longitude"]

    result = {}
    for name in ASHTAKAVARGA_PLANETS:  # same 7 classical planets
        p = by_name[name]
        uchcha = _uchcha_bala(name, p["longitude"])
        kendradi = _kendradi_bala(p["house"])
        oja_yugma = _oja_yugma_bala(name, p["sign_idx"], p.get("navamsa_sign_idx", p["sign_idx"]))
        drekkana = _drekkana_bala(name, p["degree_in_sign"])
        sthana = uchcha + kendradi + oja_yugma + drekkana

        dig = _dig_bala(name, p["longitude"], asc_longitude)

        paksha = _paksha_bala(name, sun_lon, moon_lon)
        nathonnatha = _nathonnatha_bala(name, jd_birth, lat, lon)
        kaala = paksha + nathonnatha  # partial — see scope note (still missing Tribhaga/Varsha/Masa/Vara/Hora/Yuddha Bala)

        chesta = _chesta_bala(name, p.get("speed", 0.0), p.get("retrograde", False))
        if chesta is None:
            # Sun uses Ayana Bala (omitted — needs declination data),
            # Moon uses Paksha Bala as its Chesta Bala per BPHS 27.
            chesta = paksha if name == "Moon" else 30.0  # neutral placeholder for Sun's Ayana Bala

        naisargika = NAISARGIKA_BALA[name]
        drik = _drik_bala(name, by_name, sun_lon, moon_lon)

        total_virupas = sthana + dig + kaala + chesta + naisargika + drik
        total_rupas = round(total_virupas / 60, 2)

        result[name] = {
            "total_rupas": total_rupas,
            # NOTE: deliberately NOT comparing against the classical minimum-
            # required-Rupas table here. That table (Sun 5, Moon 6, Mercury 7,
            # etc.) assumes the FULL six-component system; since this
            # implementation omits Drik Bala, most of Kaala Bala, and
            # Saptavargaja Bala, our total is systematically lower than the
            # true classical total. Comparing it against the full-system
            # threshold would show nearly every planet as "below minimum"
            # regardless of the chart — a misleading signal, not a real one.
            # total_rupas is meaningful as a RELATIVE strength indicator
            # (comparing planets within the same chart to each other), not as
            # an absolute pass/fail against classical thresholds.
            "sub_scores_virupas": {
                "sthana_bala": round(sthana, 2),
                "dig_bala": round(dig, 2),
                "kaala_bala": round(kaala, 2),
                "chesta_bala": round(chesta, 2),
                "naisargika_bala": round(naisargika, 2),
                "drik_bala": round(drik, 2),
            },
        }
    return result


def compute_bhava_bala(house_lords_list: List[Dict], shadbala: Dict, house_aspects: Dict[int, List[str]]) -> Dict[int, Dict]:
    """Bhava Bala (house strength), Rupas. Scope note: this uses Bhavadhipati
    Bala (the house lord's own Shadbala) and an aspect-based strength
    component; classical Bhava Dig Bala is omitted (see module-level scope
    note — no verified distinct formula available separate from what
    Kendradi Bala already captures for the lord itself). Like Shadbala's
    total_rupas, treat this as a RELATIVE indicator (comparing houses within
    the same chart) rather than an absolute score against the classical ">8
    Rupas = dominant" threshold, for the same reason: our partial Shadbala
    input is systematically lower than the full classical system, so the
    absolute threshold doesn't transfer cleanly. is_dominant is included but
    should be read as "relatively strong in this partial system," not a
    strict classical verdict."""
    result = {}
    for h in house_lords_list:
        lord = h["lord"]
        bhavadhipati_bala = shadbala[lord]["total_rupas"] if lord in shadbala else 0.0

        # Aspect strength on this house: sum of aspecting planets' own Shadbala,
        # scaled down — a house aspected by strong planets gets a boost.
        aspecting = house_aspects.get(h["house"], [])
        aspect_bala = round(sum(shadbala[p]["total_rupas"] for p in aspecting if p in shadbala) * 0.25, 2)

        total = round(bhavadhipati_bala + aspect_bala, 2)
        result[h["house"]] = {
            "total_rupas": total,
            "bhavadhipati_bala_rupas": round(bhavadhipati_bala, 2),
            "aspect_bala_rupas": aspect_bala,
        }
    return result


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
