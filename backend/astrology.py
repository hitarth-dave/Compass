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
            "retrograde": speed < 0 and name not in ("Sun", "Moon", "Rahu", "Ketu"),
            "dignity": dignity["tags"],
            "navamsa_sign": dignity["navamsa_sign_en"],
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
        })

    yogas = _detect_yogas(planets_out, asc_sign)

    return {
        "birth_utc": utc.isoformat(),
        "ascendant": {
            "longitude": round(asc_lon, 4),
            "sign_idx": asc_sign,
            "sign": RASHIS[asc_sign],
            "sign_en": RASHI_EN[asc_sign],
            "degree_in_sign": round(asc_deg, 2),
            "lord": SIGN_LORDS[asc_sign],
        },
        "planets": planets_out,
        "dashas": dashas,
        "house_lords": house_lords_list,
        "yogas": yogas,
    }


# --- Rashi (sign) lords ---
SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]


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
    around = [p for p in planets if p["name"] not in ("Moon", "Rahu", "Ketu") and p["sign_idx"] in (prev_sign, next_sign)]
    if not same and not around:
        yogas.append({
            "name": "Kemadruma Yoga",
            "detail": "Moon isolated (no planets in 2nd/12th from Moon) — struggle and solitude unless mitigated.",
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
    """For a given Mahadasha, compute the 9 Antardasha (sub-period) breakdown."""
    from datetime import date as _date
    lord = mahadasha["lord"]
    total_yrs = mahadasha["years"]
    start = datetime.strptime(mahadasha["start"], "%Y-%m-%d")
    lord_idx = NAK_LORDS.index(lord)
    subs = []
    for i in range(9):
        sub_lord = NAK_LORDS[(lord_idx + i) % 9]
        sub_years = (DASHA_YEARS[sub_lord] * total_yrs) / 120.0
        end = start + timedelta(days=sub_years * 365.25)
        subs.append({
            "lord": sub_lord,
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "years": round(sub_years, 3),
        })
        start = end
    return subs


def current_antardasha(mahadasha: Dict) -> Dict | None:
    subs = compute_antardashas(mahadasha)
    today = datetime.now(timezone.utc).date().isoformat()
    for s in subs:
        if s["start"] <= today <= s["end"]:
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


def current_transits(natal_chart: Dict | None = None) -> Dict:
    """Compute current sidereal planetary positions.
    If natal_chart is given, also compute which house each transit falls in
    from natal Lagna and from natal Moon (Chandra Lagna)."""
    now = datetime.now(timezone.utc)
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
