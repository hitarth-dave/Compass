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
        })

    # Ketu = Rahu + 180
    rahu = next(p for p in planets_out if p["name"] == "Rahu")
    ketu_lon = (rahu["longitude"] + 180) % 360
    ketu_sign, ketu_deg = _rashi_from_lon(ketu_lon)
    k_nak, k_pada = _nakshatra_from_lon(ketu_lon)
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
    })

    # Moon nakshatra for Vimshottari dasha
    moon = next(p for p in planets_out if p["name"] == "Moon")
    moon_lon = moon["longitude"]
    m_nak_idx, _ = _nakshatra_from_lon(moon_lon)
    dashas = _vimshottari_dashas(moon_lon, local, m_nak_idx)

    return {
        "birth_utc": utc.isoformat(),
        "ascendant": {
            "longitude": round(asc_lon, 4),
            "sign_idx": asc_sign,
            "sign": RASHIS[asc_sign],
            "sign_en": RASHI_EN[asc_sign],
            "degree_in_sign": round(asc_deg, 2),
        },
        "planets": planets_out,
        "dashas": dashas,
    }


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


def current_transits() -> Dict:
    """Compute current sidereal planetary positions."""
    now = datetime.now(timezone.utc)
    jd = _julday(now)
    out = []
    for name, pid in PLANETS:
        p_lon, speed = _sidereal_lon(jd, pid)
        sign, deg = _rashi_from_lon(p_lon)
        nak_idx, pada = _nakshatra_from_lon(p_lon)
        out.append({
            "name": name,
            "sign": RASHIS[sign],
            "sign_en": RASHI_EN[sign],
            "degree_in_sign": round(deg, 2),
            "nakshatra": NAKSHATRAS[nak_idx],
            "retrograde": speed < 0 and name not in ("Sun", "Moon", "Rahu"),
        })
    # Ketu
    rahu = next(p for p in out if p["name"] == "Rahu")
    rahu_lon_calc, _ = _sidereal_lon(jd, swe.MEAN_NODE)
    ketu_lon = (rahu_lon_calc + 180) % 360
    ketu_sign, ketu_deg = _rashi_from_lon(ketu_lon)
    k_nak, _ = _nakshatra_from_lon(ketu_lon)
    out.append({
        "name": "Ketu",
        "sign": RASHIS[ketu_sign],
        "sign_en": RASHI_EN[ketu_sign],
        "degree_in_sign": round(ketu_deg, 2),
        "nakshatra": NAKSHATRAS[k_nak],
        "retrograde": True,
    })
    return {"as_of": now.isoformat(), "planets": out}
