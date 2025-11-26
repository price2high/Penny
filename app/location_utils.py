# app/location_utils.py
"""
🗺️ Penny's Location Intelligence System
Handles city detection, tenant routing, and geographic data loading.

MISSION: Connect residents to the right local resources, regardless of how
they describe their location — whether it's "Atlanta", "ATL", "30303", or "near me".

CURRENT: Rule-based city matching with 6 supported cities
FUTURE: Will add ZIP→city mapping, geocoding API, and user location preferences
"""

import re
import json
import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# --- LOGGING SETUP (Azure-friendly) ---
logger = logging.getLogger(__name__)

# --- BASE PATHS (OS-agnostic for Azure/Windows/Linux) ---
BASE_DIR = Path(__file__).parent.parent.resolve()
DATA_PATH = BASE_DIR / "data"
EVENTS_PATH = DATA_PATH / "events"
RESOURCES_PATH = DATA_PATH / "resources"

# Ensure critical directories exist (Azure deployment safety)
for path in [DATA_PATH, EVENTS_PATH, RESOURCES_PATH]:
    path.mkdir(parents=True, exist_ok=True)


# ============================================================
# CITY REGISTRY (Penny's Supported Cities)
# ============================================================

@dataclass
class CityInfo:
    """
    Structured information about a city Penny supports.
    Makes it easy to add new cities with metadata.
    """
    tenant_id: str          # Standard format: cityname_state (e.g., "atlanta_ga")
    full_name: str          # Display name: "Atlanta, GA"
    state: str              # Two-letter state code
    aliases: List[str]      # Common variations users might say
    timezone: str           # IANA timezone (e.g., "America/New_York")
    lat: Optional[float] = None  # For weather API fallback
    lon: Optional[float] = None
    
    def __post_init__(self):
        # Normalize all aliases to lowercase for matching
        self.aliases = [alias.lower().strip() for alias in self.aliases]


class SupportedCities:
    """
    🏙️ Penny's city registry.
    Each city gets standardized metadata for consistent routing.
    """
    
    ATLANTA = CityInfo(
        tenant_id="atlanta_ga",
        full_name="Atlanta, GA",
        state="GA",
        timezone="America/New_York",
        lat=33.7490,
        lon=-84.3880,
        aliases=[
            "atlanta", "atl", "atlanta ga", "atlanta, ga",
            "city of atlanta", "hotlanta", "the atl"
        ]
    )
    
    BIRMINGHAM = CityInfo(
        tenant_id="birmingham_al",
        full_name="Birmingham, AL",
        state="AL",
        timezone="America/Chicago",
        lat=33.5207,
        lon=-86.8025,
        aliases=[
            "birmingham", "birmingham al", "birmingham, al",
            "city of birmingham", "bham"
        ]
    )
    
    CHESTERFIELD = CityInfo(
        tenant_id="chesterfield_va",
        full_name="Chesterfield, VA",
        state="VA",
        timezone="America/New_York",
        lat=37.3771,
        lon=-77.5047,
        aliases=[
            "chesterfield", "chesterfield va", "chesterfield, va",
            "chesterfield county"
        ]
    )
    
    EL_PASO = CityInfo(
        tenant_id="el_paso_tx",
        full_name="El Paso, TX",
        state="TX",
        timezone="America/Denver",
        lat=31.7619,
        lon=-106.4850,
        aliases=[
            "el paso", "el paso tx", "el paso, tx",
            "city of el paso", "elpaso"
        ]
    )
    
    PROVIDENCE = CityInfo(
        tenant_id="providence_ri",
        full_name="Providence, RI",
        state="RI",
        timezone="America/New_York",
        lat=41.8240,
        lon=-71.4128,
        aliases=[
            "providence", "providence ri", "providence, ri",
            "city of providence", "pvd"
        ]
    )
    
    SEATTLE = CityInfo(
        tenant_id="seattle_wa",
        full_name="Seattle, WA",
        state="WA",
        timezone="America/Los_Angeles",
        lat=47.6062,
        lon=-122.3321,
        aliases=[
            "seattle", "seattle wa", "seattle, wa",
            "city of seattle", "emerald city", "sea"
        ]
    )
    
    @classmethod
    def get_all_cities(cls) -> List[CityInfo]:
        """Returns list of all supported cities."""
        return [
            cls.ATLANTA,
            cls.BIRMINGHAM,
            cls.CHESTERFIELD,
            cls.EL_PASO,
            cls.PROVIDENCE,
            cls.SEATTLE
        ]
    
    @classmethod
    def get_city_by_tenant_id(cls, tenant_id: str) -> Optional[CityInfo]:
        """Lookup city info by tenant ID."""
        for city in cls.get_all_cities():
            if city.tenant_id == tenant_id:
                return city
        return None


# ============================================================
# BUILD DYNAMIC CITY PATTERNS (from CityInfo registry)
# ============================================================

def _build_city_patterns() -> Dict[str, str]:
    """
    Generates city matching dictionary from the CityInfo registry.
    This keeps the pattern matching backward-compatible with existing code.
    """
    patterns = {}
    for city in SupportedCities.get_all_cities():
        for alias in city.aliases:
            patterns[alias] = city.tenant_id
    return patterns


# Dynamic pattern dictionary (auto-generated from city registry)
REAL_CITY_PATTERNS = _build_city_patterns()


# ============================================================
# LOCATION DETECTION ENUMS
# ============================================================

class LocationStatus(str, Enum):
    """
    Status codes for location detection results.
    """
    FOUND = "found"                      # Valid city matched
    ZIP_DETECTED = "zip_detected"        # ZIP code found (needs mapping)
    USER_LOCATION_NEEDED = "user_location_needed"  # "near me" detected
    UNKNOWN = "unknown"                  # No match found
    AMBIGUOUS = "ambiguous"              # Multiple possible matches


@dataclass
class LocationMatch:
    """
    Structured result from location detection.
    Includes confidence and matched patterns for debugging.
    """
    status: LocationStatus
    tenant_id: Optional[str] = None
    city_info: Optional[CityInfo] = None
    confidence: float = 0.0  # 0.0 - 1.0
    matched_pattern: Optional[str] = None
    alternatives: List[str] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


# ============================================================
# ZIP CODE PATTERNS (for future expansion)
# ============================================================

ZIP_PATTERN = re.compile(r"\b\d{5}(?:-\d{4})?\b")  # Matches 12345 or 12345-6789

# Future ZIP → City mapping (placeholder)
ZIP_TO_CITY_MAP: Dict[str, str] = {
    # Atlanta metro
    "30303": "atlanta_ga",
    "30318": "atlanta_ga",
    "30309": "atlanta_ga",
    
    # Birmingham metro
    "35203": "birmingham_al",
    "35233": "birmingham_al",
    
    # Chesterfield County
    "23832": "chesterfield_va",
    "23838": "chesterfield_va",
    
    # El Paso
    "79901": "el_paso_tx",
    "79936": "el_paso_tx",
    
    # Providence
    "02903": "providence_ri",
    "02904": "providence_ri",
    
    # Seattle metro
    "98101": "seattle_wa",
    "98104": "seattle_wa",
    "98122": "seattle_wa",
}


# ============================================================
# MAIN CITY EXTRACTION LOGIC (Enhanced)
# ============================================================

def extract_city_name(text: str) -> str:
    """
    🎯 BACKWARD-COMPATIBLE location extraction (returns tenant_id string).
    
    Extracts tenant ID (e.g., 'atlanta_ga') from user input.
    
    Args:
        text: User's location input (e.g., "Atlanta", "30303", "near me")
        
    Returns:
        Tenant ID string or status code:
        - Valid tenant_id (e.g., "atlanta_ga")
        - "zip_detected" (ZIP code found, needs mapping)
        - "user_location_needed" ("near me" detected)
        - "unknown" (no match)
    """
    result = extract_location_detailed(text)
    return result.tenant_id or result.status.value


def extract_location_detailed(text: str) -> LocationMatch:
    """
    🧠 ENHANCED location extraction with confidence scoring.
    
    This function intelligently parses location references and returns
    structured results with metadata for better error handling.
    
    Args:
        text: User's location input
        
    Returns:
        LocationMatch object with full detection details
    """
    
    if not text or not text.strip():
        logger.warning("Empty text provided to location extraction")
        return LocationMatch(
            status=LocationStatus.UNKNOWN,
            confidence=0.0
        )
    
    lowered = text.lower().strip()
    logger.debug(f"Extracting location from: '{lowered}'")
    
    # --- STEP 1: Check for "near me" / location services needed ---
    near_me_phrases = [
        "near me", "my area", "my city", "my neighborhood",
        "where i am", "current location", "my location",
        "around here", "locally", "in my town"
    ]
    
    if any(phrase in lowered for phrase in near_me_phrases):
        logger.info("User location services required")
        return LocationMatch(
            status=LocationStatus.USER_LOCATION_NEEDED,
            confidence=1.0,
            matched_pattern="near_me_detected"
        )
    
    # --- STEP 2: Check for ZIP codes ---
    zip_matches = ZIP_PATTERN.findall(text)
    if zip_matches:
        zip_code = zip_matches[0]  # Take first ZIP if multiple
        
        # Try to map ZIP to known city
        if zip_code in ZIP_TO_CITY_MAP:
            tenant_id = ZIP_TO_CITY_MAP[zip_code]
            city_info = SupportedCities.get_city_by_tenant_id(tenant_id)
            logger.info(f"ZIP {zip_code} mapped to {tenant_id}")
            return LocationMatch(
                status=LocationStatus.FOUND,
                tenant_id=tenant_id,
                city_info=city_info,
                confidence=0.95,
                matched_pattern=f"zip:{zip_code}"
            )
        else:
            logger.info(f"ZIP code detected but not mapped: {zip_code}")
            return LocationMatch(
                status=LocationStatus.ZIP_DETECTED,
                confidence=0.5,
                matched_pattern=f"zip:{zip_code}"
            )
    
    # --- STEP 3: Match against city patterns ---
    matches = []
    for pattern, tenant_id in REAL_CITY_PATTERNS.items():
        if pattern in lowered:
            matches.append((pattern, tenant_id))
    
    if not matches:
        logger.info(f"No city match found for: '{lowered}'")
        return LocationMatch(
            status=LocationStatus.UNKNOWN,
            confidence=0.0
        )
    
    # If multiple matches, pick the longest pattern (most specific)
    # Example: "atlanta" vs "city of atlanta" — pick the longer one
    matches.sort(key=lambda x: len(x[0]), reverse=True)
    best_pattern, best_tenant_id = matches[0]
    
    city_info = SupportedCities.get_city_by_tenant_id(best_tenant_id)
    
    # Calculate confidence based on match specificity
    confidence = min(len(best_pattern) / len(lowered), 1.0)
    
    result = LocationMatch(
        status=LocationStatus.FOUND,
        tenant_id=best_tenant_id,
        city_info=city_info,
        confidence=confidence,
        matched_pattern=best_pattern
    )
    
    # Check for ambiguity (multiple different cities matched)
    unique_tenant_ids = set(tid for _, tid in matches)
    if len(unique_tenant_ids) > 1:
        result.status = LocationStatus.AMBIGUOUS
        result.alternatives = [tid for _, tid in matches if tid != best_tenant_id]
        logger.warning(f"Ambiguous location match: {unique_tenant_ids}")
    
    logger.info(f"Location matched: {best_tenant_id} (confidence: {confidence:.2f})")
    return result


# ============================================================
# DATA LOADING UTILITIES (Enhanced with error handling)
# ============================================================

def load_city_data(directory: Path, tenant_id: str) -> Dict[str, Any]:
    """
    🗄️ Generic utility to load JSON data for a given tenant ID.
    
    Args:
        directory: Base path (EVENTS_PATH or RESOURCES_PATH)
        tenant_id: City identifier (e.g., 'atlanta_ga')
        
    Returns:
        Parsed JSON content as dictionary
        
    Raises:
        FileNotFoundError: If the JSON file doesn't exist
        json.JSONDecodeError: If the file is malformed
    """
    
    file_path = directory / f"{tenant_id}.json"
    
    if not file_path.exists():
        logger.error(f"Data file not found: {file_path}")
        raise FileNotFoundError(f"Data file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"Loaded data from {file_path}")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}", exc_info=True)
        raise


def load_city_events(tenant_id: str) -> Dict[str, Any]:
    """
    📅 Loads structured event data for a given city.
    
    Args:
        tenant_id: City identifier (e.g., 'atlanta_ga')
        
    Returns:
        Event data structure with 'events' key containing list of events
        
    Example:
        {
            "city": "Atlanta, GA",
            "events": [
                {"name": "Jazz Festival", "category": "outdoor", ...},
                ...
            ]
        }
    """
    logger.info(f"Loading events for {tenant_id}")
    return load_city_data(EVENTS_PATH, tenant_id)


def load_city_resources(tenant_id: str) -> Dict[str, Any]:
    """
    🏛️ Loads civic resource data for a given city.
    
    Args:
        tenant_id: City identifier (e.g., 'atlanta_ga')
        
    Returns:
        Resource data structure with categorized resources
        
    Example:
        {
            "city": "Atlanta, GA",
            "resources": {
                "shelters": [...],
                "food_banks": [...],
                "libraries": [...]
            }
        }
    """
    logger.info(f"Loading resources for {tenant_id}")
    return load_city_data(RESOURCES_PATH, tenant_id)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def normalize_location_name(text: str) -> str:
    """
    🧹 Normalize location names into consistent format.
    Removes spaces, hyphens, and special characters.
    
    Example:
        "El Paso, TX" → "elpasotx"
        "Chesterfield County" → "chesterfieldcounty"
    """
    if not text:
        return ""
    
    # Remove punctuation and spaces
    normalized = re.sub(r"[\s\-,\.]+", "", text.lower().strip())
    return normalized


def get_city_coordinates(tenant_id: str) -> Optional[Dict[str, float]]:
    """
    🗺️ Returns coordinates for a city as a dictionary.
    Useful for weather API calls.
    
    Args:
        tenant_id: City identifier
        
    Returns:
        Dictionary with "lat" and "lon" keys, or None if not found
        
    Note: This function returns a dict for consistency with orchestrator usage.
    Use tuple unpacking: coords = get_city_coordinates(tenant_id); lat, lon = coords["lat"], coords["lon"]
    """
    city_info = SupportedCities.get_city_by_tenant_id(tenant_id)
    if city_info and city_info.lat is not None and city_info.lon is not None:
        return {"lat": city_info.lat, "lon": city_info.lon}
    return None


def get_city_info(tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    🏙️ Returns city information dictionary.
    
    Args:
        tenant_id: City identifier
        
    Returns:
        Dictionary with city information (name, state, coordinates, etc.) or None
    """
    city_info = SupportedCities.get_city_by_tenant_id(tenant_id)
    if city_info:
        return {
            "tenant_id": city_info.tenant_id,
            "full_name": city_info.full_name,
            "state": city_info.state,
            "timezone": city_info.timezone,
            "lat": city_info.lat,
            "lon": city_info.lon,
            "aliases": city_info.aliases
        }
    return None


def detect_location_from_text(text: str) -> Dict[str, Any]:
    """
    🔍 Detects location from text input.
    
    Args:
        text: User input text
        
    Returns:
        Dictionary with keys:
        - found: bool (whether location was detected)
        - tenant_id: str (if found)
        - city_info: dict (if found)
        - confidence: float (0.0-1.0)
    """
    result = extract_location_detailed(text)
    
    return {
        "found": result.status == LocationStatus.FOUND,
        "tenant_id": result.tenant_id,
        "city_info": {
            "tenant_id": result.city_info.tenant_id,
            "full_name": result.city_info.full_name,
            "state": result.city_info.state
        } if result.city_info else None,
        "confidence": result.confidence,
        "status": result.status.value
    }


def validate_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """
    ✅ Validates latitude and longitude coordinates.
    
    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if coordinates are valid
        - error_message: None if valid, error description if invalid
    """
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False, "Coordinates must be numeric values"
    
    if not (-90 <= lat <= 90):
        return False, f"Latitude must be between -90 and 90, got {lat}"
    
    if not (-180 <= lon <= 180):
        return False, f"Longitude must be between -180 and 180, got {lon}"
    
    return True, None


def get_city_timezone(tenant_id: str) -> Optional[str]:
    """
    🕐 Returns IANA timezone string for a city.
    Useful for time-sensitive features (events, business hours).
    
    Args:
        tenant_id: City identifier
        
    Returns:
        IANA timezone string (e.g., "America/New_York") or None
    """
    city_info = SupportedCities.get_city_by_tenant_id(tenant_id)
    return city_info.timezone if city_info else None


def validate_tenant_id(tenant_id: str) -> bool:
    """
    ✅ Checks if a tenant_id is valid and supported.
    
    Args:
        tenant_id: City identifier to validate
        
    Returns:
        True if valid and supported, False otherwise
    """
    city_info = SupportedCities.get_city_by_tenant_id(tenant_id)
    return city_info is not None


def get_all_supported_cities() -> List[Dict[str, str]]:
    """
    📋 Returns list of all supported cities for API responses.
    
    Returns:
        List of city info dictionaries with tenant_id and display name
        
    Example:
        [
            {"tenant_id": "atlanta_ga", "name": "Atlanta, GA"},
            {"tenant_id": "seattle_wa", "name": "Seattle, WA"},
            ...
        ]
    """
    return [
        {
            "tenant_id": city.tenant_id,
            "name": city.full_name,
            "state": city.state
        }
        for city in SupportedCities.get_all_cities()
    ]


# ============================================================
# DATA VALIDATION (For startup checks)
# ============================================================

def validate_city_data_files() -> Dict[str, Dict[str, bool]]:
    """
    🧪 Validates that all expected data files exist.
    Useful for startup checks and deployment verification.
    
    Returns:
        Dictionary mapping tenant_id to file existence status
        
    Example:
        {
            "atlanta_ga": {"events": True, "resources": True},
            "seattle_wa": {"events": False, "resources": True}
        }
    """
    validation_results = {}
    
    for city in SupportedCities.get_all_cities():
        tenant_id = city.tenant_id
        events_file = EVENTS_PATH / f"{tenant_id}.json"
        resources_file = RESOURCES_PATH / f"{tenant_id}.json"
        
        validation_results[tenant_id] = {
            "events": events_file.exists(),
            "resources": resources_file.exists()
        }
        
        if not events_file.exists():
            logger.warning(f"Missing events file for {tenant_id}")
        if not resources_file.exists():
            logger.warning(f"Missing resources file for {tenant_id}")
    
    return validation_results


# ============================================================
# INITIALIZATION CHECK (Call on app startup)
# ============================================================

def initialize_location_system() -> bool:
    """
    🚀 Validates location system is ready.
    Should be called during app startup.
    
    Returns:
        True if system is ready, False if critical files missing
    """
    logger.info("🗺️ Initializing Penny's location system...")
    
    # Check directories exist
    if not DATA_PATH.exists():
        logger.error(f"Data directory not found: {DATA_PATH}")
        return False
    
    # Validate city data files
    validation = validate_city_data_files()
    
    total_cities = len(SupportedCities.get_all_cities())
    cities_with_events = sum(1 for v in validation.values() if v["events"])
    cities_with_resources = sum(1 for v in validation.values() if v["resources"])
    
    logger.info(f"✅ {total_cities} cities registered")
    logger.info(f"✅ {cities_with_events}/{total_cities} cities have event data")
    logger.info(f"✅ {cities_with_resources}/{total_cities} cities have resource data")
    
    # Warn about missing data but don't fail
    missing_data = [tid for tid, status in validation.items() 
                   if not status["events"] or not status["resources"]]
    
    if missing_data:
        logger.warning(f"⚠️ Incomplete data for cities: {missing_data}")
    
    logger.info("🗺️ Location system initialized successfully")
    return True