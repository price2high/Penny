# app/event_weather.py
"""
🌤️ Penny's Event + Weather Matchmaker
Helps residents find the perfect community activity based on real-time weather.
Penny always suggests what's actually enjoyable — not just what exists.

Production-ready version with structured logging, performance tracking, and robust error handling.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from app.weather_agent import get_weather_for_location
from app.location_utils import load_city_events
from app.logging_utils import log_interaction, sanitize_for_logging

# --- LOGGING SETUP (Structured, Azure-compatible) ---
import logging
logger = logging.getLogger(__name__)


# --- CONFIGURATION CONSTANTS ---
class EventWeatherConfig:
    """Configuration constants for event recommendation system."""
    MAX_FALLBACK_EVENTS = 10
    MAX_RECOMMENDATIONS = 20
    WEATHER_TIMEOUT_SECONDS = 5.0
    SLOW_OPERATION_THRESHOLD_MS = 2000


# --- PENNY'S WEATHER WISDOM (Personality-Driven Thresholds) ---
class WeatherThresholds:
    """
    Penny's practical weather rules for event recommendations.
    These are based on real resident comfort, not just data.
    """
    WARM_THRESHOLD = 70  # F° - Great for outdoor events
    HOT_THRESHOLD = 85   # F° - Maybe too hot for some activities
    COOL_THRESHOLD = 60  # F° - Bring a jacket
    COLD_THRESHOLD = 40  # F° - Indoor events preferred
    
    RAINY_KEYWORDS = ["rain", "shower", "storm", "drizzle", "thunderstorm"]
    SNOWY_KEYWORDS = ["snow", "flurries", "blizzard", "ice"]
    NICE_KEYWORDS = ["clear", "sunny", "fair", "partly cloudy"]


class ErrorType(str, Enum):
    """Structured error types for event weather system."""
    NOT_FOUND = "event_data_not_found"
    PARSE_ERROR = "json_parse_error"
    WEATHER_ERROR = "weather_service_error"
    UNKNOWN = "unknown_error"


class EventWeatherException(Exception):
    """Base exception for event weather system."""
    def __init__(self, error_type: ErrorType, message: str, original_error: Optional[Exception] = None):
        self.error_type = error_type
        self.message = message
        self.original_error = original_error
        super().__init__(message)


# --- MAIN RECOMMENDATION FUNCTION ---
async def get_event_recommendations_with_weather(
    tenant_id: str, 
    lat: float, 
    lon: float,
    include_all_events: bool = False,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    🌤️ Penny's Event + Weather Intelligence System
    
    Combines real-time weather with community events to give residents 
    smart, helpful suggestions about what to do today.
    
    Args:
        tenant_id: City identifier (e.g., 'atlanta_ga', 'seattle_wa')
        lat: Latitude for weather lookup
        lon: Longitude for weather lookup
        include_all_events: If True, returns all events regardless of weather fit
        session_id: Optional session identifier for logging
        user_id: Optional user identifier for logging
        
    Returns:
        Dict containing:
            - weather: Current conditions
            - suggestions: Penny's prioritized recommendations
            - all_events: Optional full event list
            - metadata: Useful context (timestamp, event count, etc.)
            
    Raises:
        EventWeatherException: When critical errors occur
        
    Example:
        >>> recommendations = await get_event_recommendations_with_weather(
        ...     tenant_id="norfolk_va",
        ...     lat=36.8508,
        ...     lon=-76.2859
        ... )
        >>> print(recommendations["suggestions"][0])
        🌟 **Outdoor Concert**at Town Point Park — Perfect outdoor weather! This is the one.
    """
    start_time = time.time()
    
    # Sanitize inputs for logging
    safe_tenant_id = sanitize_for_logging(tenant_id)
    safe_coords = f"({lat:.4f}, {lon:.4f})"
    
    logger.info(
        f"🌤️ Event weather recommendation request: tenant={safe_tenant_id}, coords={safe_coords}"
    )
    
    try:
        # --- STEP 1: Load City Events (Standardized) ---
        events, event_load_time = await _load_events_with_timing(tenant_id)
        
        if not events:
            response = _create_no_events_response(tenant_id)
            _log_operation(
                operation="event_weather_recommendations",
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                success=True,
                event_count=0,
                response_time_ms=_calculate_response_time(start_time),
                fallback_used=False,
                weather_available=False
            )
            return response
        
        logger.info(f"✅ Loaded {len(events)} events for {safe_tenant_id} in {event_load_time:.2f}s")
        
        # --- STEP 2: Get Live Weather Data ---
        weather, weather_available = await _get_weather_with_fallback(lat, lon)
        
        # --- STEP 3: Generate Recommendations ---
        if weather_available:
            response = await _generate_weather_optimized_recommendations(
                tenant_id=tenant_id,
                events=events,
                weather=weather,
                include_all_events=include_all_events
            )
        else:
            # Graceful degradation: Still show events without weather optimization
            response = _create_fallback_response(tenant_id, events)
        
        # --- STEP 4: Calculate Performance Metrics ---
        response_time_ms = _calculate_response_time(start_time)
        
        # Add performance metadata
        response["performance"] = {
            "response_time_ms": response_time_ms,
            "event_load_time_ms": int(event_load_time * 1000),
            "weather_available": weather_available
        }
        
        # Warn if operation was slow
        if response_time_ms > EventWeatherConfig.SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                f"⚠️ Slow event weather operation: {response_time_ms}ms for {safe_tenant_id}"
            )
        
        # --- STEP 5: Log Structured Interaction ---
        _log_operation(
            operation="event_weather_recommendations",
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            success=True,
            event_count=len(events),
            response_time_ms=response_time_ms,
            fallback_used=not weather_available,
            weather_available=weather_available
        )
        
        logger.info(
            f"✅ Returning {len(response.get('suggestions', []))} recommendations "
            f"for {safe_tenant_id} in {response_time_ms}ms"
        )
        
        return response
        
    except EventWeatherException as e:
        # Known error with structured handling
        response_time_ms = _calculate_response_time(start_time)
        
        _log_operation(
            operation="event_weather_recommendations",
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            success=False,
            event_count=0,
            response_time_ms=response_time_ms,
            fallback_used=False,
            weather_available=False,
            error_type=e.error_type.value,
            error_message=str(e)
        )
        
        return _create_error_response(
            tenant_id=tenant_id,
            error_type=e.error_type.value,
            message=e.message
        )
        
    except Exception as e:
        # Unexpected error
        response_time_ms = _calculate_response_time(start_time)
        
        logger.error(
            f"❌ Unexpected error in event weather recommendations: {str(e)}",
            exc_info=True
        )
        
        _log_operation(
            operation="event_weather_recommendations",
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            success=False,
            event_count=0,
            response_time_ms=response_time_ms,
            fallback_used=False,
            weather_available=False,
            error_type=ErrorType.UNKNOWN.value,
            error_message="Unexpected system error"
        )
        
        return _create_error_response(
            tenant_id=tenant_id,
            error_type=ErrorType.UNKNOWN.value,
            message="Something unexpected happened. Please try again in a moment."
        )


# --- EVENT LOADING WITH TIMING ---
async def _load_events_with_timing(tenant_id: str) -> Tuple[List[Dict[str, Any]], float]:
    """
    Load city events with performance timing.
    
    Args:
        tenant_id: City identifier
        
    Returns:
        Tuple of (events list, load time in seconds)
        
    Raises:
        EventWeatherException: When event loading fails
    """
    load_start = time.time()
    
    try:
        loaded_data = load_city_events(tenant_id)
        events = loaded_data.get("events", [])
        load_time = time.time() - load_start
        
        return events, load_time
        
    except FileNotFoundError as e:
        logger.error(f"❌ Event data file not found for tenant: {tenant_id}")
        raise EventWeatherException(
            error_type=ErrorType.NOT_FOUND,
            message=f"I don't have event data for {tenant_id} yet. Let me know if you'd like me to add it!",
            original_error=e
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in event data for {tenant_id}: {e}")
        raise EventWeatherException(
            error_type=ErrorType.PARSE_ERROR,
            message="There's an issue with the event data format. Our team has been notified!",
            original_error=e
        )
        
    except Exception as e:
        logger.error(f"❌ Unexpected error loading events: {e}", exc_info=True)
        raise EventWeatherException(
            error_type=ErrorType.UNKNOWN,
            message="Something went wrong loading events. Please try again in a moment.",
            original_error=e
        )


# --- WEATHER RETRIEVAL WITH FALLBACK ---
async def _get_weather_with_fallback(
    lat: float, 
    lon: float
) -> Tuple[Dict[str, Any], bool]:
    """
    Get weather data with graceful fallback if service is unavailable.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Tuple of (weather data dict, availability boolean)
    """
    try:
        weather = await get_weather_for_location(lat, lon)
        
        temp = weather.get("temperature", {}).get("value")
        phrase = weather.get("phrase", "N/A")
        
        logger.info(f"✅ Weather retrieved: {phrase} at {temp}°F")
        
        return weather, True
        
    except Exception as e:
        logger.warning(f"⚠️ Weather service unavailable: {str(e)}")
        return {"error": "Weather service unavailable"}, False


# --- WEATHER-OPTIMIZED RECOMMENDATIONS ---
async def _generate_weather_optimized_recommendations(
    tenant_id: str,
    events: List[Dict[str, Any]],
    weather: Dict[str, Any],
    include_all_events: bool
) -> Dict[str, Any]:
    """
    Generate event recommendations optimized for current weather conditions.
    
    Args:
        tenant_id: City identifier
        events: List of available events
        weather: Weather data dictionary
        include_all_events: Whether to include full event list in response
        
    Returns:
        Structured response with weather-optimized suggestions
    """
    temp = weather.get("temperature", {}).get("value")
    phrase = weather.get("phrase", "").lower()
    
    # Analyze weather conditions
    weather_analysis = _analyze_weather_conditions(temp, phrase)
    
    # Generate Penny's smart suggestions
    suggestions = _generate_recommendations(
        events=events,
        weather_analysis=weather_analysis,
        temp=temp,
        phrase=phrase
    )
    
    # Build response
    response = {
        "weather": weather,
        "weather_summary": _create_weather_summary(temp, phrase),
        "suggestions": suggestions[:EventWeatherConfig.MAX_RECOMMENDATIONS],
        "tenant_id": tenant_id,
        "event_count": len(events),
        "timestamp": datetime.utcnow().isoformat(),
        "weather_analysis": weather_analysis
    }
    
    # Optionally include full event list
    if include_all_events:
        response["all_events"] = events
    
    return response


# --- HELPER FUNCTIONS (Penny's Intelligence Layer) ---

def _analyze_weather_conditions(temp: Optional[float], phrase: str) -> Dict[str, Any]:
    """
    🧠 Penny's weather interpretation logic.
    Returns structured analysis of current conditions.
    
    Args:
        temp: Temperature in Fahrenheit
        phrase: Weather description phrase
        
    Returns:
        Dictionary with weather analysis including outdoor suitability
    """
    analysis = {
        "is_rainy": any(keyword in phrase for keyword in WeatherThresholds.RAINY_KEYWORDS),
        "is_snowy": any(keyword in phrase for keyword in WeatherThresholds.SNOWY_KEYWORDS),
        "is_nice": any(keyword in phrase for keyword in WeatherThresholds.NICE_KEYWORDS),
        "temp_category": None,
        "outdoor_friendly": False,
        "indoor_preferred": False
    }
    
    if temp:
        if temp >= WeatherThresholds.HOT_THRESHOLD:
            analysis["temp_category"] = "hot"
        elif temp >= WeatherThresholds.WARM_THRESHOLD:
            analysis["temp_category"] = "warm"
        elif temp >= WeatherThresholds.COOL_THRESHOLD:
            analysis["temp_category"] = "mild"
        elif temp >= WeatherThresholds.COLD_THRESHOLD:
            analysis["temp_category"] = "cool"
        else:
            analysis["temp_category"] = "cold"
        
        # Outdoor-friendly = warm/mild + not rainy/snowy
        analysis["outdoor_friendly"] = (
            temp >= WeatherThresholds.COOL_THRESHOLD and
            not analysis["is_rainy"] and
            not analysis["is_snowy"]
        )
        
        # Indoor preferred = cold or rainy or snowy
        analysis["indoor_preferred"] = (
            temp < WeatherThresholds.COOL_THRESHOLD or
            analysis["is_rainy"] or
            analysis["is_snowy"]
        )
    
    return analysis


def _generate_recommendations(
    events: List[Dict[str, Any]],
    weather_analysis: Dict[str, Any],
    temp: Optional[float],
    phrase: str
) -> List[str]:
    """
    🎯 Penny's event recommendation engine.
    Prioritizes events based on weather + category fit.
    Keeps Penny's warm, helpful voice throughout.
    
    Args:
        events: List of available events
        weather_analysis: Weather condition analysis
        temp: Current temperature
        phrase: Weather description
        
    Returns:
        List of formatted event suggestions
    """
    suggestions = []
    
    # Sort events: Best weather fit first
    scored_events = []
    for event in events:
        score = _calculate_event_weather_score(event, weather_analysis)
        scored_events.append((score, event))
    
    scored_events.sort(reverse=True, key=lambda x: x[0])
    
    # Generate suggestions with Penny's personality
    for score, event in scored_events:
        event_name = event.get("name", "Unnamed Event")
        event_category = event.get("category", "").lower()
        event_location = event.get("location", "")
        
        # Build suggestion with appropriate emoji + messaging
        suggestion = _create_suggestion_message(
            event_name=event_name,
            event_category=event_category,
            event_location=event_location,
            score=score,
            weather_analysis=weather_analysis,
            temp=temp,
            phrase=phrase
        )
        
        suggestions.append(suggestion)
    
    return suggestions


def _calculate_event_weather_score(
    event: Dict[str, Any],
    weather_analysis: Dict[str, Any]
) -> int:
    """
    📊 Scores event suitability based on weather (0-100).
    Higher = better match for current conditions.
    
    Args:
        event: Event dictionary with category information
        weather_analysis: Weather condition analysis
        
    Returns:
        Integer score from 0-100
    """
    category = event.get("category", "").lower()
    score = 50  # Neutral baseline
    
    # Perfect matches
    if "outdoor" in category and weather_analysis["outdoor_friendly"]:
        score = 95
    elif "indoor" in category and weather_analysis["indoor_preferred"]:
        score = 90
    
    # Good matches
    elif "indoor" in category and not weather_analysis["outdoor_friendly"]:
        score = 75
    elif "outdoor" in category and weather_analysis["temp_category"] in ["warm", "mild"]:
        score = 70
    
    # Acceptable matches
    elif "civic" in category or "community" in category:
        score = 60  # Usually indoor, weather-neutral
    
    # Poor matches (but still list them)
    elif "outdoor" in category and weather_analysis["indoor_preferred"]:
        score = 30
    
    return score


def _create_suggestion_message(
    event_name: str,
    event_category: str,
    event_location: str,
    score: int,
    weather_analysis: Dict[str, Any],
    temp: Optional[float],
    phrase: str
) -> str:
    """
    💬 Penny's voice: Generates natural, helpful event suggestions.
    Adapts tone based on weather fit score.
    
    Args:
        event_name: Name of the event
        event_category: Event category (outdoor, indoor, etc.)
        event_location: Event location/venue
        score: Weather suitability score (0-100)
        weather_analysis: Weather condition analysis
        temp: Current temperature
        phrase: Weather description
        
    Returns:
        Formatted suggestion string with emoji and helpful context
    """
    location_text = f" at {event_location}" if event_location else ""
    
    # PERFECT MATCHES (90-100)
    if score >= 90:
        if "outdoor" in event_category:
            return f"🌟 **{event_name}**{location_text} — Perfect outdoor weather! This is the one."
        else:
            return f"🏛️ **{event_name}**{location_text} — Ideal indoor activity for today's weather!"
    
    # GOOD MATCHES (70-89)
    elif score >= 70:
        if "outdoor" in event_category:
            return f"☀️ **{event_name}**{location_text} — Great day for outdoor activities!"
        else:
            return f"🔵 **{event_name}**{location_text} — Solid indoor option!"
    
    # DECENT MATCHES (50-69)
    elif score >= 50:
        if "outdoor" in event_category:
            temp_text = f" (It's {int(temp)}°F)" if temp else ""
            return f"🌤️ **{event_name}**{location_text} — Weather's okay for outdoor events{temp_text}."
        else:
            return f"⚪ **{event_name}**{location_text} — Weather-neutral activity."
    
    # POOR MATCHES (Below 50)
    else:
        if "outdoor" in event_category and weather_analysis["is_rainy"]:
            return f"🌧️ **{event_name}**{location_text} — Outdoor event, but it's rainy. Bring an umbrella or check if it's postponed!"
        elif "outdoor" in event_category and weather_analysis.get("temp_category") == "cold":
            return f"❄️ **{event_name}**{location_text} — Outdoor event, but bundle up — it's chilly!"
        else:
            return f"⚪ **{event_name}**{location_text} — Check weather before heading out."


def _create_weather_summary(temp: Optional[float], phrase: str) -> str:
    """
    🌤️ Penny's plain-English weather summary.
    
    Args:
        temp: Temperature in Fahrenheit
        phrase: Weather description phrase
        
    Returns:
        Human-readable weather summary
    """
    if not temp:
        return f"Current conditions: {phrase.title()}"
    
    temp_desc = ""
    if temp >= 85:
        temp_desc = "hot"
    elif temp >= 70:
        temp_desc = "warm"
    elif temp >= 60:
        temp_desc = "mild"
    elif temp >= 40:
        temp_desc = "cool"
    else:
        temp_desc = "cold"
    
    return f"It's {temp_desc} at {int(temp)}°F — {phrase.lower()}."


# --- ERROR RESPONSE HELPERS (Penny stays helpful even in failures) ---

def _create_no_events_response(tenant_id: str) -> Dict[str, Any]:
    """
    Returns friendly response when no events are found.
    
    Args:
        tenant_id: City identifier
        
    Returns:
        Structured response with helpful message
    """
    return {
        "weather": {},
        "suggestions": [
            f"🤔 I don't have any events loaded for {tenant_id} right now. "
            "Let me know if you'd like me to check again or add some!"
        ],
        "tenant_id": tenant_id,
        "event_count": 0,
        "timestamp": datetime.utcnow().isoformat()
    }


def _create_error_response(
    tenant_id: str, 
    error_type: str, 
    message: str
) -> Dict[str, Any]:
    """
    Returns structured error with Penny's helpful tone.
    
    Args:
        tenant_id: City identifier
        error_type: Structured error type code
        message: User-friendly error message
        
    Returns:
        Error response dictionary
    """
    logger.error(f"Error in event_weather: {error_type} - {message}")
    return {
        "weather": {},
        "suggestions": [f"⚠️ {message}"],
        "tenant_id": tenant_id,
        "event_count": 0,
        "error_type": error_type,
        "timestamp": datetime.utcnow().isoformat()
    }


def _create_fallback_response(
    tenant_id: str, 
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Graceful degradation: Shows events even if weather service is down.
    Penny stays helpful!
    
    Args:
        tenant_id: City identifier
        events: List of available events
        
    Returns:
        Fallback response with events but no weather optimization
    """
    # Limit to configured maximum
    display_events = events[:EventWeatherConfig.MAX_FALLBACK_EVENTS]
    
    suggestions = [
        f"📅 **{event.get('name', 'Event')}** — {event.get('category', 'Community event')}"
        for event in display_events
    ]
    
    suggestions.insert(0, "⚠️ Weather service is temporarily unavailable, but here are today's events:")
    
    return {
        "weather": {"error": "Weather service unavailable"},
        "suggestions": suggestions,
        "tenant_id": tenant_id,
        "event_count": len(events),
        "timestamp": datetime.utcnow().isoformat(),
        "fallback_mode": True
    }


# --- STRUCTURED LOGGING HELPER ---

def _log_operation(
    operation: str,
    tenant_id: str,
    success: bool,
    event_count: int,
    response_time_ms: int,
    fallback_used: bool,
    weather_available: bool,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None
) -> None:
    """
    Log event weather operation with structured data.
    
    Args:
        operation: Operation name
        tenant_id: City identifier
        success: Whether operation succeeded
        event_count: Number of events processed
        response_time_ms: Total response time in milliseconds
        fallback_used: Whether fallback mode was used
        weather_available: Whether weather data was available
        session_id: Optional session identifier
        user_id: Optional user identifier
        error_type: Optional error type if failed
        error_message: Optional error message if failed
    """
    log_data = {
        "operation": operation,
        "tenant_id": sanitize_for_logging(tenant_id),
        "success": success,
        "event_count": event_count,
        "response_time_ms": response_time_ms,
        "fallback_used": fallback_used,
        "weather_available": weather_available,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if session_id:
        log_data["session_id"] = sanitize_for_logging(session_id)
    
    if user_id:
        log_data["user_id"] = sanitize_for_logging(user_id)
    
    if error_type:
        log_data["error_type"] = error_type
    
    if error_message:
        log_data["error_message"] = sanitize_for_logging(error_message)
    
    log_interaction(log_data)


def _calculate_response_time(start_time: float) -> int:
    """
    Calculate response time in milliseconds.
    
    Args:
        start_time: Operation start time from time.time()
        
    Returns:
        Response time in milliseconds
    """
    return int((time.time() - start_time) * 1000)