import re

POLLUTION_KEYWORDS = {
    # English
    "pollution", "air quality", "aqi", "smog", "dust", "pm2.5", "pm10", "no2", "so2", "ozone",
    "emissions", "air", "breath", "choking", "haze", "air pollution", "pollutant",
    # Hindi
    "pradushan", "hawa", "vayu", "dhua", "dhool", "saans", "kharaab hawa", "vayu gunvatta",
    "प्रदूषण", "हवा", "वायु", "धुआं", "धूल", "सांस", "वायु गुणवत्ता",
    # Telugu
    "kaluśyam", "gali", "gali kalushyam", "dummu", "dhooli", "swasa", "naanyatha",
    "కాలుష్యం", "గాలి", "గాలి కాలుష్యం", "దుమ్ము", "ధూళి", "శ్వాస", "నాణ్యత",
}

NON_POLLUTION_KEYWORDS = {
    "traffic", "jam", "congestion", "signal", "green time", "diversion", "accident", "parking",
    "energy", "power", "electricity", "load", "grid", "outage", "blackout", "solar",
    "weather", "rain", "temperature", "heat", "cold", "storm", "flood", "cyclone", "humidity",
    # Hindi/Telugu equivalents
    "baarish", "garmi", "bijli", "jaam", "varsham", "vediga", "vidyut", "trafic"
}

def is_pollution_question(text: str) -> str:
    text_lower = text.lower()
    
    # Check for pollution keywords
    has_pollution = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in POLLUTION_KEYWORDS)
    # Also check if text has no word boundaries (for Hindi/Telugu scripts)
    if not has_pollution:
        has_pollution = any(kw in text_lower for kw in POLLUTION_KEYWORDS if not kw.isascii())
    
    has_other = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in NON_POLLUTION_KEYWORDS)
    if not has_other:
        has_other = any(kw in text_lower for kw in NON_POLLUTION_KEYWORDS if not kw.isascii())
        
    if has_pollution and has_other:
        return "mixed"
    elif has_pollution:
        return "pollution"
    else:
        return "not"
