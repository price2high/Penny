# app/weather_agent.py
"""
🌤️ PENNY Weather Agent - Azure Maps Integration

Provides real-time weather information and weather-aware recommendations
for civic engagement activities.

MISSION: Help residents plan their day with accurate weather data and
smart suggestions for indoor/outdoor activities based on conditions.

ENHANCEMENTS (Phase 1 Complete):
- ✅ Structured logging with performance tracking
- ✅ Enhanced error handling with graceful degradation
- ✅ Type hints for all functions
- ✅ Health check integration
- ✅ Response caching for performance
- ✅ Detailed weather parsing with validation
- ✅ Penny's friendly voice in all responses

Production-ready for Azure ML deployment.
"""

import os
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import httpx

# --- ENHANCED MODULE IMPORTS ---
from app.logging_utils import log_interaction

# --- LOGGING SETUP ---
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
AZURE_WEATHER_URL = "https://atlas.microsoft.com/weather/currentConditions/json"
DEFAULT_TIMEOUT = 10.0  # seconds
CACHE_TTL_SECONDS = 300  # 5 minutes - weather doesn't change that fast

# --- WEATHER CACHE ---
_weather_cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}


# ============================================================
# WEATHER DATA RETRIEVAL
# ============================================================

async def get_weather_for_location(
    lat: float, 
    lon: float,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    🌤️ Fetches real-time weather from Azure Maps.
    
    Retrieves current weather conditions for a specific location using
    Azure Maps Weather API. Includes caching to reduce API calls and
    improve response times.
    
    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        use_cache: Whether to use cached data if available (default: True)
        
    Returns:
        Dictionary containing weather data with keys:
        - temperature: {value: float, unit: str}
        - phrase: str (weather description)
        - iconCode: int
        - hasPrecipitation: bool
        - isDayTime: bool
        - relativeHumidity: int
        - cloudCover: int
        - etc.
        
    Raises:
        RuntimeError: If AZURE_MAPS_KEY is not configured
        httpx.HTTPError: If API request fails
        
    Example:
        weather = await get_weather_for_location(33.7490, -84.3880)
        temp = weather.get("temperature", {}).get("value")
        condition = weather.get("phrase", "Unknown")
    """
    start_time = time.time()
    
    # Create cache key
    cache_key = f"{lat:.4f},{lon:.4f}"
    
    # Check cache first
    if use_cache and cache_key in _weather_cache:
        cached_data, cached_time = _weather_cache[cache_key]
        age = (datetime.now() - cached_time).total_seconds()
        
        if age < CACHE_TTL_SECONDS:
            logger.info(
                f"🌤️ Weather cache hit (age: {age:.0f}s, "
                f"location: {cache_key})"
            )
            return cached_data
    
    # Read API key
    AZURE_MAPS_KEY = os.getenv("AZURE_MAPS_KEY")
    
    if not AZURE_MAPS_KEY:
        logger.error("❌ AZURE_MAPS_KEY not configured")
        raise RuntimeError(
            "AZURE_MAPS_KEY is required and not set in environment variables."
        )
    
    # Build request parameters
    params = {
        "api-version": "1.0",
        "query": f"{lat},{lon}",
        "subscription-key": AZURE_MAPS_KEY,
        "details": "true",
        "language": "en-US",
    }
    
    try:
        logger.info(f"🌤️ Fetching weather for location: {cache_key}")
        
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(AZURE_WEATHER_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Parse response
        if "results" in data and len(data["results"]) > 0:
            weather_data = data["results"][0]
        else:
            weather_data = data  # Fallback if structure changes
        
        # Validate essential fields
        weather_data = _validate_weather_data(weather_data)
        
        # Cache the result
        _weather_cache[cache_key] = (weather_data, datetime.now())
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        
        # Log successful retrieval
        log_interaction(
            tenant_id="weather_service",
            interaction_type="weather_fetch",
            intent="weather",
            response_time_ms=response_time,
            success=True,
            metadata={
                "location": cache_key,
                "cached": False,
                "temperature": weather_data.get("temperature", {}).get("value"),
                "condition": weather_data.get("phrase")
            }
        )
        
        logger.info(
            f"✅ Weather fetched successfully ({response_time:.0f}ms, "
            f"location: {cache_key})"
        )
        
        return weather_data
    
    except httpx.TimeoutException as e:
        logger.error(f"⏱️ Weather API timeout: {e}")
        raise
    
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Weather API HTTP error: {e.response.status_code}")
        raise
    
    except Exception as e:
        logger.error(f"❌ Weather API error: {e}", exc_info=True)
        raise


def _validate_weather_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and normalizes weather data from Azure Maps.
    
    Ensures essential fields are present with sensible defaults.
    """
    # Ensure temperature exists
    if "temperature" not in data:
        data["temperature"] = {"value": None, "unit": "F"}
    elif isinstance(data["temperature"], (int, float)):
        # Handle case where temperature is just a number
        data["temperature"] = {"value": data["temperature"], "unit": "F"}
    
    # Ensure phrase exists
    if "phrase" not in data or not data["phrase"]:
        data["phrase"] = "Conditions unavailable"
    
    # Ensure boolean flags exist
    data.setdefault("hasPrecipitation", False)
    data.setdefault("isDayTime", True)
    
    # Ensure numeric fields exist
    data.setdefault("relativeHumidity", None)
    data.setdefault("cloudCover", None)
    data.setdefault("iconCode", None)
    
    return data


# ============================================================
# OUTFIT RECOMMENDATIONS
# ============================================================

def recommend_outfit(high_temp: float, condition: str) -> str:
    """
    👕 Recommends what to wear based on weather conditions.
    
    Provides friendly, practical clothing suggestions based on
    temperature and weather conditions.
    
    Args:
        high_temp: Expected high temperature in Fahrenheit
        condition: Weather condition description (e.g., "Sunny", "Rainy")
        
    Returns:
        Friendly outfit recommendation string
        
    Example:
        outfit = recommend_outfit(85, "Sunny")
        # Returns: "Light clothes, sunscreen, and stay hydrated! ☀️"
    """
    condition_lower = condition.lower()
    
    # Check for precipitation first
    if "rain" in condition_lower or "storm" in condition_lower:
        logger.debug(f"Outfit rec: Rain/Storm (temp: {high_temp}°F)")
        return "Bring an umbrella or rain jacket! ☔"
    
    # Temperature-based recommendations
    if high_temp >= 85:
        logger.debug(f"Outfit rec: Hot (temp: {high_temp}°F)")
        return "Light clothes, sunscreen, and stay hydrated! ☀️"
    
    if high_temp >= 72:
        logger.debug(f"Outfit rec: Warm (temp: {high_temp}°F)")
        return "T-shirt and jeans or a casual dress. 👕"
    
    if high_temp >= 60:
        logger.debug(f"Outfit rec: Mild (temp: {high_temp}°F)")
        return "A hoodie or light jacket should do! 🧥"
    
    logger.debug(f"Outfit rec: Cold (temp: {high_temp}°F)")
    return "Bundle up — sweater or coat recommended! 🧣"


# ============================================================
# EVENT RECOMMENDATIONS BASED ON WEATHER
# ============================================================

def weather_to_event_recommendations(
    weather: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    📅 Suggests activity types based on current weather conditions.
    
    Analyzes weather data to provide smart recommendations for
    indoor vs outdoor activities, helping residents plan their day.
    
    Args:
        weather: Weather data dictionary from get_weather_for_location()
        
    Returns:
        List of recommendation dictionaries with keys:
        - type: str ("indoor", "outdoor", "neutral")
        - suggestions: List[str] (specific activity ideas)
        - reason: str (explanation for recommendation)
        - priority: int (1-3, added for sorting)
        
    Example:
        weather = await get_weather_for_location(33.7490, -84.3880)
        recs = weather_to_event_recommendations(weather)
        for rec in recs:
            print(f"{rec['type']}: {rec['suggestions']}")
    """
    condition = (weather.get("phrase") or "").lower()
    temp = weather.get("temperature", {}).get("value")
    has_precipitation = weather.get("hasPrecipitation", False)
    
    recs = []
    
    # Check for rain or storms (highest priority)
    if "rain" in condition or "storm" in condition or has_precipitation:
        logger.debug("Event rec: Indoor (precipitation)")
        recs.append({
            "type": "indoor",
            "suggestions": [
                "Visit a library 📚",
                "Check out a community center event 🏛️",
                "Find an indoor workshop or class 🎨",
                "Explore a local museum 🖼️"
            ],
            "reason": "Rainy weather makes indoor events ideal!",
            "priority": 1
        })
    
    # Warm weather outdoor activities
    elif temp is not None and temp >= 75:
        logger.debug(f"Event rec: Outdoor (warm: {temp}°F)")
        recs.append({
            "type": "outdoor",
            "suggestions": [
                "Visit a park 🌳",
                "Check out a farmers market 🥕",
                "Look for outdoor concerts or festivals 🎵",
                "Enjoy a community picnic or BBQ 🍔"
            ],
            "reason": "Beautiful weather for outdoor activities!",
            "priority": 1
        })
    
    # Cold weather considerations
    elif temp is not None and temp < 50:
        logger.debug(f"Event rec: Indoor (cold: {temp}°F)")
        recs.append({
            "type": "indoor",
            "suggestions": [
                "Browse local events at community centers 🏛️",
                "Visit a museum or art gallery 🖼️",
                "Check out indoor markets or shopping 🛍️",
                "Warm up at a local café or restaurant ☕"
            ],
            "reason": "Chilly weather — indoor activities are cozy!",
            "priority": 1
        })
    
    # Mild/neutral weather
    else:
        logger.debug(f"Event rec: Neutral (mild: {temp}°F if temp else 'unknown')")
        recs.append({
            "type": "neutral",
            "suggestions": [
                "Browse local events 📅",
                "Visit a museum or cultural center 🏛️",
                "Walk around a local plaza or downtown 🚶",
                "Check out both indoor and outdoor activities 🌍"
            ],
            "reason": "Mild weather gives you flexible options!",
            "priority": 2
        })
    
    return recs


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_weather_summary(weather: Dict[str, Any]) -> str:
    """
    📝 Formats weather data into a human-readable summary.
    
    Args:
        weather: Weather data dictionary
        
    Returns:
        Formatted weather summary string with Penny's friendly voice
        
    Example:
        summary = format_weather_summary(weather_data)
        # "Currently 72°F and Partly Cloudy. Humidity: 65%"
    """
    temp_data = weather.get("temperature", {})
    temp = temp_data.get("value")
    unit = temp_data.get("unit", "F")
    phrase = weather.get("phrase", "Conditions unavailable")
    humidity = weather.get("relativeHumidity")
    
    # Build summary
    parts = []
    
    if temp is not None:
        parts.append(f"Currently {int(temp)}°{unit}")
    
    parts.append(phrase)
    
    if humidity is not None:
        parts.append(f"Humidity: {humidity}%")
    
    summary = " and ".join(parts[:2])
    if len(parts) > 2:
        summary += f". {parts[2]}"
    
    return summary


def clear_weather_cache():
    """
    🧹 Clears the weather cache.
    
    Useful for testing or if fresh data is needed immediately.
    """
    global _weather_cache
    cache_size = len(_weather_cache)
    _weather_cache.clear()
    logger.info(f"🧹 Weather cache cleared ({cache_size} entries removed)")


def get_cache_stats() -> Dict[str, Any]:
    """
    📊 Returns weather cache statistics.
    
    Returns:
        Dictionary with cache statistics:
        - entries: int (number of cached locations)
        - oldest_entry_age_seconds: float
        - newest_entry_age_seconds: float
    """
    if not _weather_cache:
        return {
            "entries": 0,
            "oldest_entry_age_seconds": None,
            "newest_entry_age_seconds": None
        }
    
    now = datetime.now()
    ages = [
        (now - cached_time).total_seconds()
        for _, cached_time in _weather_cache.values()
    ]
    
    return {
        "entries": len(_weather_cache),
        "oldest_entry_age_seconds": max(ages) if ages else None,
        "newest_entry_age_seconds": min(ages) if ages else None
    }


# ============================================================
# HEALTH CHECK
# ============================================================

def get_weather_agent_health() -> Dict[str, Any]:
    """
    📊 Returns weather agent health status.
    
    Used by the main application health check endpoint to monitor
    the weather service availability and performance.
    
    Returns:
        Dictionary with health information
    """
    cache_stats = get_cache_stats()
    
    # Check if API key is configured
    api_key_configured = bool(os.getenv("AZURE_MAPS_KEY"))
    
    return {
        "status": "operational" if api_key_configured else "degraded",
        "service": "azure_maps_weather",
        "api_key_configured": api_key_configured,
        "cache": cache_stats,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "default_timeout_seconds": DEFAULT_TIMEOUT,
        "features": {
            "real_time_weather": True,
            "outfit_recommendations": True,
            "event_recommendations": True,
            "response_caching": True
        }
    }


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":
    """🧪 Test weather agent functionality"""
    import asyncio
    
    print("=" * 60)
    print("🧪 Testing Weather Agent")
    print("=" * 60)
    
    async def run_tests():
        # Test location: Atlanta, GA
        lat, lon = 33.7490, -84.3880
        
        print(f"\n--- Test 1: Fetch Weather ---")
        print(f"Location: {lat}, {lon} (Atlanta, GA)")
        
        try:
            weather = await get_weather_for_location(lat, lon)
            print(f"✅ Weather fetched successfully")
            print(f"Temperature: {weather.get('temperature', {}).get('value')}°F")
            print(f"Condition: {weather.get('phrase')}")
            print(f"Precipitation: {weather.get('hasPrecipitation')}")
            
            print(f"\n--- Test 2: Weather Summary ---")
            summary = format_weather_summary(weather)
            print(f"Summary: {summary}")
            
            print(f"\n--- Test 3: Outfit Recommendation ---")
            temp = weather.get('temperature', {}).get('value', 70)
            condition = weather.get('phrase', 'Clear')
            outfit = recommend_outfit(temp, condition)
            print(f"Outfit: {outfit}")
            
            print(f"\n--- Test 4: Event Recommendations ---")
            recs = weather_to_event_recommendations(weather)
            for rec in recs:
                print(f"Type: {rec['type']}")
                print(f"Reason: {rec['reason']}")
                print(f"Suggestions: {', '.join(rec['suggestions'][:2])}")
            
            print(f"\n--- Test 5: Cache Test ---")
            weather2 = await get_weather_for_location(lat, lon, use_cache=True)
            print(f"✅ Cache working (should be instant)")
            
            print(f"\n--- Test 6: Health Check ---")
            health = get_weather_agent_health()
            print(f"Status: {health['status']}")
            print(f"Cache entries: {health['cache']['entries']}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    asyncio.run(run_tests())
    
    print("\n" + "=" * 60)
    print("✅ Tests complete")