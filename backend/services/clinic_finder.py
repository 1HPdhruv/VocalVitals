import os
import httpx
from urllib.parse import quote

NOMINATIM_UA = os.getenv("NOMINATIM_USER_AGENT", "vocal-vitals-app/1.0")

SPECIALIST_QUERY_MAP = {
    "neurologist":    "neurology clinic",
    "pulmonologist":  "pulmonology respiratory clinic",
    "ent":            "ENT ear nose throat clinic",
    "general":        "general practice clinic",
    "cardiologist":   "cardiology clinic",
    "psychiatrist":   "psychiatry mental health clinic",
    "gastroenterologist": "gastroenterology clinic",
}


def _map_specialist(specialist_recommended: str) -> str:
    s = specialist_recommended.lower().strip()
    for key, query in SPECIALIST_QUERY_MAP.items():
        if key in s:
            return query
    return "general practice clinic"


async def find_nearby_clinic(specialist_recommended: str, lat: float, lon: float) -> dict | None:
    """
    Query Nominatim for nearest specialist clinic.
    Returns clinic dict or None if not found.
    """
    query = _map_specialist(specialist_recommended)

    params = {
        "q":       query,
        "lat":     lat,
        "lon":     lon,
        "format":  "json",
        "limit":   1,
        "addressdetails": 1,
    }

    headers = {"User-Agent": NOMINATIM_UA}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            results = resp.json()

            if not results:
                return None

            r = results[0]
            name    = r.get("display_name", "Unknown Clinic")
            # Shorten display name to first two components
            name_parts = name.split(",")
            short_name = ", ".join(name_parts[:2]).strip()
            address    = ", ".join(name_parts[1:4]).strip()

            # Haversine distance
            import math
            rlat = float(r.get("lat", lat))
            rlon = float(r.get("lon", lon))
            R = 6371
            dlat = math.radians(rlat - lat)
            dlon = math.radians(rlon - lon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(rlat)) * math.sin(dlon/2)**2
            distance_km = round(R * 2 * math.asin(math.sqrt(a)), 2)

            maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(address or short_name)}"

            return {
                "name":        short_name,
                "address":     address,
                "distance_km": distance_km,
                "maps_url":    maps_url,
            }
    except Exception as e:
        print(f"Nominatim lookup failed: {e}")
        return None
