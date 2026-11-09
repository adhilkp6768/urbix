from __future__ import annotations

REFERENCE_GEOGRAPHY = [
    {"slug": "earth", "name": "Earth", "level_code": "global", "parent_slug": None, "country_code": None, "timezone": "UTC", "latitude": None, "longitude": None},
    {"slug": "continent-north-america", "name": "North America", "level_code": "continent", "parent_slug": "earth", "country_code": None, "timezone": None, "latitude": 46.0, "longitude": -100.0},
    {"slug": "continent-europe", "name": "Europe", "level_code": "continent", "parent_slug": "earth", "country_code": None, "timezone": None, "latitude": 54.0, "longitude": 15.0},
    {"slug": "continent-asia", "name": "Asia", "level_code": "continent", "parent_slug": "earth", "country_code": None, "timezone": None, "latitude": 34.0, "longitude": 100.0},
    {"slug": "continent-africa", "name": "Africa", "level_code": "continent", "parent_slug": "earth", "country_code": None, "timezone": None, "latitude": 2.0, "longitude": 20.0},
    {"slug": "continent-south-america", "name": "South America", "level_code": "continent", "parent_slug": "earth", "country_code": None, "timezone": None, "latitude": -15.0, "longitude": -60.0},
    {"slug": "continent-oceania", "name": "Oceania", "level_code": "continent", "parent_slug": "earth", "country_code": None, "timezone": None, "latitude": -22.0, "longitude": 140.0},
    {"slug": "country-us", "name": "United States", "level_code": "country", "parent_slug": "continent-north-america", "country_code": "US", "timezone": "America/New_York", "latitude": 39.8, "longitude": -98.5},
    {"slug": "country-sg", "name": "Singapore", "level_code": "country", "parent_slug": "continent-asia", "country_code": "SG", "timezone": "Asia/Singapore", "latitude": 1.3521, "longitude": 103.8198},
    {"slug": "country-nl", "name": "Netherlands", "level_code": "country", "parent_slug": "continent-europe", "country_code": "NL", "timezone": "Europe/Amsterdam", "latitude": 52.1, "longitude": 5.3},
    {"slug": "country-gb", "name": "United Kingdom", "level_code": "country", "parent_slug": "continent-europe", "country_code": "GB", "timezone": "Europe/London", "latitude": 54.0, "longitude": -2.0},
    {"slug": "country-de", "name": "Germany", "level_code": "country", "parent_slug": "continent-europe", "country_code": "DE", "timezone": "Europe/Berlin", "latitude": 51.2, "longitude": 10.4},
    {"slug": "country-fr", "name": "France", "level_code": "country", "parent_slug": "continent-europe", "country_code": "FR", "timezone": "Europe/Paris", "latitude": 46.2, "longitude": 2.2},
    {"slug": "country-es", "name": "Spain", "level_code": "country", "parent_slug": "continent-europe", "country_code": "ES", "timezone": "Europe/Madrid", "latitude": 40.4, "longitude": -3.7},
    {"slug": "country-it", "name": "Italy", "level_code": "country", "parent_slug": "continent-europe", "country_code": "IT", "timezone": "Europe/Rome", "latitude": 42.8, "longitude": 12.5},
    {"slug": "country-se", "name": "Sweden", "level_code": "country", "parent_slug": "continent-europe", "country_code": "SE", "timezone": "Europe/Stockholm", "latitude": 62.0, "longitude": 15.0},
    {"slug": "country-jp", "name": "Japan", "level_code": "country", "parent_slug": "continent-asia", "country_code": "JP", "timezone": "Asia/Tokyo", "latitude": 36.2, "longitude": 138.3},
    {"slug": "country-kr", "name": "South Korea", "level_code": "country", "parent_slug": "continent-asia", "country_code": "KR", "timezone": "Asia/Seoul", "latitude": 36.5, "longitude": 127.9},
    {"slug": "country-in", "name": "India", "level_code": "country", "parent_slug": "continent-asia", "country_code": "IN", "timezone": "Asia/Kolkata", "latitude": 22.0, "longitude": 79.0},
    {"slug": "country-ae", "name": "United Arab Emirates", "level_code": "country", "parent_slug": "continent-asia", "country_code": "AE", "timezone": "Asia/Dubai", "latitude": 24.0, "longitude": 54.0},
    {"slug": "country-eg", "name": "Egypt", "level_code": "country", "parent_slug": "continent-africa", "country_code": "EG", "timezone": "Africa/Cairo", "latitude": 26.8, "longitude": 30.8},
    {"slug": "country-ke", "name": "Kenya", "level_code": "country", "parent_slug": "continent-africa", "country_code": "KE", "timezone": "Africa/Nairobi", "latitude": 0.2, "longitude": 37.9},
    {"slug": "country-ng", "name": "Nigeria", "level_code": "country", "parent_slug": "continent-africa", "country_code": "NG", "timezone": "Africa/Lagos", "latitude": 9.1, "longitude": 8.7},
    {"slug": "country-za", "name": "South Africa", "level_code": "country", "parent_slug": "continent-africa", "country_code": "ZA", "timezone": "Africa/Johannesburg", "latitude": -29.0, "longitude": 24.0},
    {"slug": "country-au", "name": "Australia", "level_code": "country", "parent_slug": "continent-oceania", "country_code": "AU", "timezone": "Australia/Sydney", "latitude": -25.0, "longitude": 134.0},
    {"slug": "country-ca", "name": "Canada", "level_code": "country", "parent_slug": "continent-north-america", "country_code": "CA", "timezone": "America/Toronto", "latitude": 56.1, "longitude": -106.3},
    {"slug": "country-mx", "name": "Mexico", "level_code": "country", "parent_slug": "continent-north-america", "country_code": "MX", "timezone": "America/Mexico_City", "latitude": 23.6, "longitude": -102.5},
    {"slug": "country-br", "name": "Brazil", "level_code": "country", "parent_slug": "continent-south-america", "country_code": "BR", "timezone": "America/Sao_Paulo", "latitude": -14.2, "longitude": -51.9},
    {"slug": "region-ny", "name": "New York", "level_code": "admin_region", "parent_slug": "country-us", "country_code": "US", "timezone": "America/New_York", "latitude": 42.9, "longitude": -75.5},
    {"slug": "region-rp", "name": "Rhineland-Palatinate", "level_code": "admin_region", "parent_slug": "country-de", "country_code": "DE", "timezone": "Europe/Berlin", "latitude": 49.9, "longitude": 7.4},
    {"slug": "metro-nyc", "name": "New York-Newark-Jersey City", "level_code": "metro", "parent_slug": "region-ny", "country_code": "US", "timezone": "America/New_York", "latitude": 40.71, "longitude": -74.00},
    {
        "slug": "nyc",
        "name": "New York City",
        "level_code": "city",
        "parent_slug": "metro-nyc",
        "country_code": "US",
        "timezone": "America/New_York",
        "latitude": 40.7128,
        "longitude": -74.006,
        "properties": {"centroid_method": "reference_point", "reference_note": "Replaced by the boundary centroid after official borough polygons load."},
    },
    {"slug": "singapore", "name": "Singapore", "level_code": "city", "parent_slug": "country-sg", "country_code": "SG", "timezone": "Asia/Singapore", "latitude": 1.3521, "longitude": 103.8198, "properties": {"centroid_method": "reference_point"}},
    {"slug": "amsterdam", "name": "Amsterdam", "level_code": "city", "parent_slug": "country-nl", "country_code": "NL", "timezone": "Europe/Amsterdam", "latitude": 52.3676, "longitude": 4.9041, "properties": {"centroid_method": "reference_point"}},
    {"slug": "london", "name": "London", "level_code": "city", "parent_slug": "country-gb", "country_code": "GB", "timezone": "Europe/London", "latitude": 51.5074, "longitude": -0.1278, "properties": {"centroid_method": "reference_point"}},
    {"slug": "berlin", "name": "Berlin", "level_code": "city", "parent_slug": "country-de", "country_code": "DE", "timezone": "Europe/Berlin", "latitude": 52.52, "longitude": 13.405, "properties": {"centroid_method": "reference_point"}},
    {"slug": "trier", "name": "Trier", "level_code": "city", "parent_slug": "region-rp", "country_code": "DE", "timezone": "Europe/Berlin", "latitude": 49.749, "longitude": 6.637, "properties": {"centroid_method": "reference_point"}},
    {"slug": "paris", "name": "Paris", "level_code": "city", "parent_slug": "country-fr", "country_code": "FR", "timezone": "Europe/Paris", "latitude": 48.8566, "longitude": 2.3522, "properties": {"centroid_method": "reference_point"}},
    {"slug": "madrid", "name": "Madrid", "level_code": "city", "parent_slug": "country-es", "country_code": "ES", "timezone": "Europe/Madrid", "latitude": 40.4168, "longitude": -3.7038, "properties": {"centroid_method": "reference_point"}},
    {"slug": "rome", "name": "Rome", "level_code": "city", "parent_slug": "country-it", "country_code": "IT", "timezone": "Europe/Rome", "latitude": 41.9028, "longitude": 12.4964, "properties": {"centroid_method": "reference_point"}},
    {"slug": "stockholm", "name": "Stockholm", "level_code": "city", "parent_slug": "country-se", "country_code": "SE", "timezone": "Europe/Stockholm", "latitude": 59.3293, "longitude": 18.0686, "properties": {"centroid_method": "reference_point"}},
    {"slug": "tokyo", "name": "Tokyo", "level_code": "city", "parent_slug": "country-jp", "country_code": "JP", "timezone": "Asia/Tokyo", "latitude": 35.6762, "longitude": 139.6503, "properties": {"centroid_method": "reference_point"}},
    {"slug": "seoul", "name": "Seoul", "level_code": "city", "parent_slug": "country-kr", "country_code": "KR", "timezone": "Asia/Seoul", "latitude": 37.5665, "longitude": 126.9780, "properties": {"centroid_method": "reference_point"}},
    {"slug": "mumbai", "name": "Mumbai", "level_code": "city", "parent_slug": "country-in", "country_code": "IN", "timezone": "Asia/Kolkata", "latitude": 19.0760, "longitude": 72.8777, "properties": {"centroid_method": "reference_point"}},
    {"slug": "dubai", "name": "Dubai", "level_code": "city", "parent_slug": "country-ae", "country_code": "AE", "timezone": "Asia/Dubai", "latitude": 25.2048, "longitude": 55.2708, "properties": {"centroid_method": "reference_point"}},
    {"slug": "cairo", "name": "Cairo", "level_code": "city", "parent_slug": "country-eg", "country_code": "EG", "timezone": "Africa/Cairo", "latitude": 30.0444, "longitude": 31.2357, "properties": {"centroid_method": "reference_point"}},
    {"slug": "nairobi", "name": "Nairobi", "level_code": "city", "parent_slug": "country-ke", "country_code": "KE", "timezone": "Africa/Nairobi", "latitude": -1.2921, "longitude": 36.8219, "properties": {"centroid_method": "reference_point"}},
    {"slug": "lagos", "name": "Lagos", "level_code": "city", "parent_slug": "country-ng", "country_code": "NG", "timezone": "Africa/Lagos", "latitude": 6.5244, "longitude": 3.3792, "properties": {"centroid_method": "reference_point"}},
    {"slug": "cape-town", "name": "Cape Town", "level_code": "city", "parent_slug": "country-za", "country_code": "ZA", "timezone": "Africa/Johannesburg", "latitude": -33.9249, "longitude": 18.4241, "properties": {"centroid_method": "reference_point"}},
    {"slug": "sydney", "name": "Sydney", "level_code": "city", "parent_slug": "country-au", "country_code": "AU", "timezone": "Australia/Sydney", "latitude": -33.8688, "longitude": 151.2093, "properties": {"centroid_method": "reference_point"}},
    {"slug": "toronto", "name": "Toronto", "level_code": "city", "parent_slug": "country-ca", "country_code": "CA", "timezone": "America/Toronto", "latitude": 43.6532, "longitude": -79.3832, "properties": {"centroid_method": "reference_point"}},
    {"slug": "chicago", "name": "Chicago", "level_code": "city", "parent_slug": "country-us", "country_code": "US", "timezone": "America/Chicago", "latitude": 41.8781, "longitude": -87.6298, "properties": {"centroid_method": "reference_point"}},
    {"slug": "los-angeles", "name": "Los Angeles", "level_code": "city", "parent_slug": "country-us", "country_code": "US", "timezone": "America/Los_Angeles", "latitude": 34.0522, "longitude": -118.2437, "properties": {"centroid_method": "reference_point"}},
    {"slug": "mexico-city", "name": "Mexico City", "level_code": "city", "parent_slug": "country-mx", "country_code": "MX", "timezone": "America/Mexico_City", "latitude": 19.4326, "longitude": -99.1332, "properties": {"centroid_method": "reference_point"}},
    {"slug": "sao-paulo", "name": "São Paulo", "level_code": "city", "parent_slug": "country-br", "country_code": "BR", "timezone": "America/Sao_Paulo", "latitude": -23.5558, "longitude": -46.6396, "properties": {"centroid_method": "reference_point"}},
]


def reference_city_slugs() -> list[str]:
    return [item["slug"] for item in REFERENCE_GEOGRAPHY if item.get("level_code") == "city"]

BOROUGH_NAMES = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
    "MN": "Manhattan",
    "BX": "Bronx",
    "BK": "Brooklyn",
    "QN": "Queens",
    "SI": "Staten Island",
    "MANHATTAN": "Manhattan",
    "BRONX": "Bronx",
    "BROOKLYN": "Brooklyn",
    "QUEENS": "Queens",
    "STATEN ISLAND": "Staten Island",
    "STATENISLAND": "Staten Island",
}

COUNTY_TO_BOROUGH = {
    "061": "Manhattan",
    "005": "Bronx",
    "047": "Brooklyn",
    "081": "Queens",
    "085": "Staten Island",
}


def canonical_borough(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return BOROUGH_NAMES.get(text, BOROUGH_NAMES.get(text.upper(), text.title() if text else None))
