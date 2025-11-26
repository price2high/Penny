# app/tool_agent.py
"""
🛠️ PENNY Tool Agent - Civic Data & Services Handler

Routes requests to civic data sources (events, resources, transit, etc.)
and integrates with real-time weather information.

MISSION: Connect residents to local civic services by intelligently
processing their requests and returning relevant, actionable information.

FEATURES:
- Real-time weather integration with outfit recommendations
- Event discovery with weather-aware suggestions
- Resource lookup (trash, transit, emergency services)
- City-specific data routing
- Graceful fallback for missing data

ENHANCEMENTS (Phase 1):
- ✅ Structured logging with performance tracking
- ✅ Enhanced error handling with user-friendly messages
- ✅ Type hints for all functions
- ✅ Health check integration
- ✅ Service availability tracking
- ✅ Integration with enhanced modules
- ✅ Penny's friendly voice throughout
"""

import logging
import time
from typing import Optional, Dict, Any

# --- ENHANCED MODULE IMPORTS ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- AGENT IMPORTS (with availability tracking) ---
try:
    from app.weather_agent import (
        get_weather_for_location,
        weather_to_event_recommendations,
        recommend_outfit,
        format_weather_summary
    )
    WEATHER_AGENT_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Weather agent not available: {e}")
    WEATHER_AGENT_AVAILABLE = False

# --- UTILITY IMPORTS (with availability tracking) ---
try:
    from app.location_utils import (
        extract_city_name,
        load_city_events,
        load_city_resources,
        get_city_coordinates
    )
    LOCATION_UTILS_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Location utils not available: {e}")
    LOCATION_UTILS_AVAILABLE = False

# --- LOGGING SETUP ---
logger = logging.getLogger(__name__)

# --- TRACKING COUNTERS ---
_tool_request_count = 0
_weather_request_count = 0
_event_request_count = 0
_resource_request_count = 0


# ============================================================
# MAIN TOOL REQUEST HANDLER (ENHANCED)
# ============================================================

async def handle_tool_request(
    user_input: str,
    role: str = "unknown",
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Dict[str, Any]:
    """
    🛠️ Handles tool-based actions for civic services.
    
    Routes user requests to appropriate civic data sources and real-time
    services, including weather, events, transit, trash, and emergency info.
    
    Args:
        user_input: User's request text
        role: User's role (resident, official, etc.)
        lat: Latitude coordinate (optional)
        lon: Longitude coordinate (optional)
        
    Returns:
        Dictionary containing:
        - tool: str (which tool was used)
        - city: str (detected city name)
        - response: str or dict (user-facing response)
        - data: dict (optional, raw data)
        - tenant_id: str (optional, standardized city identifier)
        
    Example:
        result = await handle_tool_request(
            user_input="What's the weather in Atlanta?",
            role="resident",
            lat=33.7490,
            lon=-84.3880
        )
    """
    global _tool_request_count
    _tool_request_count += 1
    
    start_time = time.time()
    
    # Sanitize input for logging (PII protection)
    safe_input = sanitize_for_logging(user_input)
    logger.info(f"🛠️ Tool request #{_tool_request_count}: '{safe_input[:50]}...'")
    
    try:
        # Check if location utilities are available
        if not LOCATION_UTILS_AVAILABLE:
            logger.error("Location utilities not available")
            return {
                "tool": "error",
                "response": (
                    "I'm having trouble accessing city data right now. "
                    "Try again in a moment! 💛"
                ),
                "error": "Location utilities not loaded"
            }
        
        lowered = user_input.lower()
        city_name = extract_city_name(user_input)
        
        # Standardize tenant ID (e.g., "Atlanta" -> "atlanta_ga")
        # TODO: Enhance city_name extraction to detect state
        tenant_id = f"{city_name.lower().replace(' ', '_')}_ga"
        
        logger.info(f"Detected city: {city_name} (tenant_id: {tenant_id})")
        
        # Route to appropriate handler
        result = None
        
        # Weather queries
        if any(keyword in lowered for keyword in ["weather", "forecast", "temperature", "rain", "sunny"]):
            result = await _handle_weather_query(
                user_input=user_input,
                city_name=city_name,
                tenant_id=tenant_id,
                lat=lat,
                lon=lon
            )
        
        # Event queries
        elif any(keyword in lowered for keyword in ["events", "meetings", "city hall", "happening", "activities"]):
            result = await _handle_events_query(
                user_input=user_input,
                city_name=city_name,
                tenant_id=tenant_id,
                lat=lat,
                lon=lon
            )
        
        # Resource queries (trash, transit, emergency)
        elif any(keyword in lowered for keyword in ["trash", "recycling", "garbage", "bus", "train", "schedule", "alert", "warning", "non emergency"]):
            result = await _handle_resource_query(
                user_input=user_input,
                city_name=city_name,
                tenant_id=tenant_id,
                lowered=lowered
            )
        
        # Unknown/fallback
        else:
            result = _handle_unknown_query(city_name)
        
        # Add metadata and log interaction
        response_time = (time.time() - start_time) * 1000
        result["response_time_ms"] = round(response_time, 2)
        result["role"] = role
        
        log_interaction(
            tenant_id=tenant_id,
            interaction_type="tool_request",
            intent=result.get("tool", "unknown"),
            response_time_ms=response_time,
            success=result.get("error") is None,
            metadata={
                "city": city_name,
                "tool": result.get("tool"),
                "role": role,
                "has_location": lat is not None and lon is not None
            }
        )
        
        logger.info(
            f"✅ Tool request complete: {result.get('tool')} "
            f"({response_time:.0f}ms)"
        )
        
        return result
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Tool agent error: {e}", exc_info=True)
        
        log_interaction(
            tenant_id="unknown",
            interaction_type="tool_error",
            intent="error",
            response_time_ms=response_time,
            success=False,
            metadata={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        
        return {
            "tool": "error",
            "response": (
                "I ran into trouble processing that request. "
                "Could you try rephrasing? 💛"
            ),
            "error": str(e),
            "response_time_ms": round(response_time, 2)
        }


# ============================================================
# WEATHER QUERY HANDLER (ENHANCED)
# ============================================================

async def _handle_weather_query(
    user_input: str,
    city_name: str,
    tenant_id: str,
    lat: Optional[float],
    lon: Optional[float]
) -> Dict[str, Any]:
    """
    🌤️ Handles weather-related queries with outfit recommendations.
    """
    global _weather_request_count
    _weather_request_count += 1
    
    logger.info(f"🌤️ Weather query #{_weather_request_count} for {city_name}")
    
    # Check weather agent availability
    if not WEATHER_AGENT_AVAILABLE:
        logger.warning("Weather agent not available")
        return {
            "tool": "weather",
            "city": city_name,
            "response": "Weather service isn't available right now. Try again soon! 🌤️"
        }
    
    # Get coordinates if not provided
    if lat is None or lon is None:
        coords = get_city_coordinates(tenant_id)
        if coords:
            lat, lon = coords["lat"], coords["lon"]
            logger.info(f"Using city coordinates: {lat}, {lon}")
    
    if lat is None or lon is None:
        return {
            "tool": "weather",
            "city": city_name,
            "response": (
                f"To get weather for {city_name}, I need location coordinates. "
                f"Can you share your location? 📍"
            )
        }
    
    try:
        # Fetch weather data
        weather = await get_weather_for_location(lat, lon)
        
        # Get weather-based event recommendations
        recommendations = weather_to_event_recommendations(weather)
        
        # Get outfit recommendation
        temp = weather.get("temperature", {}).get("value", 70)
        phrase = weather.get("phrase", "Clear")
        outfit = recommend_outfit(temp, phrase)
        
        # Format weather summary
        weather_summary = format_weather_summary(weather)
        
        # Build user-friendly response
        response_text = (
            f"🌤️ **Weather for {city_name}:**\n"
            f"{weather_summary}\n\n"
            f"👕 **What to wear:** {outfit}"
        )
        
        # Add event recommendations if available
        if recommendations:
            rec = recommendations[0]  # Get top recommendation
            response_text += f"\n\n📅 **Activity suggestion:** {rec['reason']}"
        
        return {
            "tool": "weather",
            "city": city_name,
            "tenant_id": tenant_id,
            "response": response_text,
            "data": {
                "weather": weather,
                "recommendations": recommendations,
                "outfit": outfit
            }
        }
    
    except Exception as e:
        logger.error(f"Weather query error: {e}", exc_info=True)
        return {
            "tool": "weather",
            "city": city_name,
            "response": (
                f"I couldn't get the weather for {city_name} right now. "
                f"Try again in a moment! 🌤️"
            ),
            "error": str(e)
        }


# ============================================================
# EVENTS QUERY HANDLER (ENHANCED)
# ============================================================

async def _handle_events_query(
    user_input: str,
    city_name: str,
    tenant_id: str,
    lat: Optional[float],
    lon: Optional[float]
) -> Dict[str, Any]:
    """
    📅 Handles event discovery queries.
    """
    global _event_request_count
    _event_request_count += 1
    
    logger.info(f"📅 Event query #{_event_request_count} for {city_name}")
    
    try:
        # Load structured event data
        event_data = load_city_events(tenant_id)
        events = event_data.get("events", [])
        num_events = len(events)
        
        if num_events == 0:
            return {
                "tool": "civic_events",
                "city": city_name,
                "tenant_id": tenant_id,
                "response": (
                    f"I don't have any upcoming events for {city_name} right now. "
                    f"Check back soon! 📅"
                )
            }
        
        # Get top event
        top_event = events[0]
        top_event_name = top_event.get("name", "Upcoming event")
        
        # Build response
        if num_events == 1:
            response_text = (
                f"📅 **Upcoming event in {city_name}:**\n"
                f"• {top_event_name}\n\n"
                f"Check the full details in the attached data!"
            )
        else:
            response_text = (
                f"📅 **Found {num_events} upcoming events in {city_name}!**\n"
                f"Top event: {top_event_name}\n\n"
                f"Check the full list in the attached data!"
            )
        
        return {
            "tool": "civic_events",
            "city": city_name,
            "tenant_id": tenant_id,
            "response": response_text,
            "data": event_data
        }
    
    except FileNotFoundError:
        logger.warning(f"Event data file not found for {tenant_id}")
        return {
            "tool": "civic_events",
            "city": city_name,
            "response": (
                f"Event data for {city_name} isn't available yet. "
                f"I'm still learning about events in your area! 📅"
            ),
            "error": "Event data file not found"
        }
    
    except Exception as e:
        logger.error(f"Events query error: {e}", exc_info=True)
        return {
            "tool": "civic_events",
            "city": city_name,
            "response": (
                f"I had trouble loading events for {city_name}. "
                f"Try again soon! 📅"
            ),
            "error": str(e)
        }


# ============================================================
# RESOURCE QUERY HANDLER (ENHANCED)
# ============================================================

async def _handle_resource_query(
    user_input: str,
    city_name: str,
    tenant_id: str,
    lowered: str
) -> Dict[str, Any]:
    """
    ♻️ Handles resource queries (trash, transit, emergency).
    """
    global _resource_request_count
    _resource_request_count += 1
    
    logger.info(f"♻️ Resource query #{_resource_request_count} for {city_name}")
    
    # Map keywords to resource types
    resource_query_map = {
        "trash": "trash_and_recycling",
        "recycling": "trash_and_recycling",
        "garbage": "trash_and_recycling",
        "bus": "transit",
        "train": "transit",
        "schedule": "transit",
        "alert": "emergency",
        "warning": "emergency",
        "non emergency": "emergency"
    }
    
    # Find matching resource type
    resource_key = next(
        (resource_query_map[key] for key in resource_query_map if key in lowered),
        None
    )
    
    if not resource_key:
        return {
            "tool": "unknown",
            "city": city_name,
            "response": (
                "I'm not sure which resource you're asking about. "
                "Try asking about trash, transit, or emergency services! 💬"
            )
        }
    
    try:
        # Load structured resource data
        resource_data = load_city_resources(tenant_id)
        service_info = resource_data["services"].get(resource_key, {})
        
        if not service_info:
            return {
                "tool": resource_key,
                "city": city_name,
                "response": (
                    f"I don't have {resource_key.replace('_', ' ')} information "
                    f"for {city_name} yet. Check the city's official website! 🏛️"
                )
            }
        
        # Build resource-specific response
        if resource_key == "trash_and_recycling":
            pickup_days = service_info.get('pickup_days', 'Varies by address')
            response_text = (
                f"♻️ **Trash & Recycling for {city_name}:**\n"
                f"Pickup days: {pickup_days}\n\n"
                f"Check the official link for your specific schedule!"
            )
        
        elif resource_key == "transit":
            provider = service_info.get('provider', 'The local transit authority')
            response_text = (
                f"🚌 **Transit for {city_name}:**\n"
                f"Provider: {provider}\n\n"
                f"Use the provided links to find routes and schedules!"
            )
        
        elif resource_key == "emergency":
            non_emergency = service_info.get('non_emergency_phone', 'N/A')
            response_text = (
                f"🚨 **Emergency Info for {city_name}:**\n"
                f"Non-emergency: {non_emergency}\n\n"
                f"**For life-threatening emergencies, always call 911.**"
            )
        
        else:
            response_text = f"Information found for {resource_key.replace('_', ' ')}, but details aren't available yet."
        
        return {
            "tool": resource_key,
            "city": city_name,
            "tenant_id": tenant_id,
            "response": response_text,
            "data": service_info
        }
    
    except FileNotFoundError:
        logger.warning(f"Resource data file not found for {tenant_id}")
        return {
            "tool": "resource_loader",
            "city": city_name,
            "response": (
                f"Resource data for {city_name} isn't available yet. "
                f"Check back soon! 🏛️"
            ),
            "error": "Resource data file not found"
        }
    
    except Exception as e:
        logger.error(f"Resource query error: {e}", exc_info=True)
        return {
            "tool": "resource_loader",
            "city": city_name,
            "response": (
                f"I had trouble loading resource data for {city_name}. "
                f"Try again soon! 🏛️"
            ),
            "error": str(e)
        }


# ============================================================
# UNKNOWN QUERY HANDLER
# ============================================================

def _handle_unknown_query(city_name: str) -> Dict[str, Any]:
    """
    ❓ Fallback for queries that don't match any tool.
    """
    logger.info(f"❓ Unknown query for {city_name}")
    
    return {
        "tool": "unknown",
        "city": city_name,
        "response": (
            "I'm not sure which civic service you're asking about. "
            "Try asking about weather, events, trash, or transit! 💬"
        )
    }


# ============================================================
# HEALTH CHECK & DIAGNOSTICS
# ============================================================

def get_tool_agent_health() -> Dict[str, Any]:
    """
    📊 Returns tool agent health status.
    
    Used by the main application health check endpoint.
    """
    return {
        "status": "operational",
        "service_availability": {
            "weather_agent": WEATHER_AGENT_AVAILABLE,
            "location_utils": LOCATION_UTILS_AVAILABLE
        },
        "statistics": {
            "total_requests": _tool_request_count,
            "weather_requests": _weather_request_count,
            "event_requests": _event_request_count,
            "resource_requests": _resource_request_count
        },
        "supported_queries": [
            "weather",
            "events",
            "trash_and_recycling",
            "transit",
            "emergency"
        ]
    }


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":
    """🧪 Test tool agent functionality"""
    import asyncio
    
    print("=" * 60)
    print("🧪 Testing Tool Agent")
    print("=" * 60)
    
    # Display service availability
    print("\n📊 Service Availability:")
    print(f"  Weather Agent: {'✅' if WEATHER_AGENT_AVAILABLE else '❌'}")
    print(f"  Location Utils: {'✅' if LOCATION_UTILS_AVAILABLE else '❌'}")
    
    print("\n" + "=" * 60)
    
    test_queries = [
        {
            "name": "Weather query",
            "input": "What's the weather in Atlanta?",
            "lat": 33.7490,
            "lon": -84.3880
        },
        {
            "name": "Events query",
            "input": "Events in Atlanta",
            "lat": None,
            "lon": None
        },
        {
            "name": "Trash query",
            "input": "When is trash pickup?",
            "lat": None,
            "lon": None
        }
    ]
    
    async def run_tests():
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- Test {i}: {query['name']} ---")
            print(f"Query: {query['input']}")
            
            try:
                result = await handle_tool_request(
                    user_input=query["input"],
                    role="test_user",
                    lat=query["lat"],
                    lon=query["lon"]
                )
                
                print(f"Tool: {result.get('tool')}")
                print(f"City: {result.get('city')}")
                
                response = result.get('response')
                if isinstance(response, str):
                    print(f"Response: {response[:150]}...")
                else:
                    print(f"Response: [Dict with {len(response)} keys]")
                
                if result.get('response_time_ms'):
                    print(f"Response time: {result['response_time_ms']:.0f}ms")
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    asyncio.run(run_tests())
    
    print("\n" + "=" * 60)
    print("📊 Final Statistics:")
    health = get_tool_agent_health()
    for key, value in health["statistics"].items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("✅ Tests complete")
    print("=" * 60)