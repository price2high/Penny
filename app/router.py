"""
🚦 PENNY Request Router - Enhanced for Azure ML Production
Routes incoming requests to appropriate agents and tools based on intent classification.
Integrates with enhanced logging, location detection, and intent classification.

Mission: Ensure every resident request reaches the right civic service with proper tracking.
"""

import logging
import time
import asyncio
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.model_loader import ModelLoader
from app.tool_agent import handle_tool_request
from app.weather_agent import (
    get_weather_for_location,
    weather_to_event_recommendations,
    recommend_outfit
)
from app.intents import classify_intent_detailed, IntentType
from app.event_weather import get_event_recommendations_with_weather
from app.location_utils import (
    detect_location_from_text,
    get_city_info,
    validate_coordinates
)
from app.logging_utils import log_interaction, sanitize_for_logging

logger = logging.getLogger(__name__)

# Initialize FastAPI router
router = APIRouter(prefix="/api", tags=["Penny API"])

# Initialize model loader
models = ModelLoader()

# Supported languages for translation routing
SUPPORTED_LANGUAGES = [
    "arabic", "french", "german", "hindi", "mandarin",
    "portuguese", "russian", "spanish", "swahili",
    "tagalog", "urdu", "vietnamese", "translate", "translation"
]

def validate_request_payload(payload: dict) -> tuple[bool, Optional[str]]:
    """
    Validate incoming request payload for required fields and data types.
    
    Args:
        payload: Request payload dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"
    
    # Check for required input field
    if "input" not in payload:
        return False, "Missing required field: 'input'"
    
    user_input = payload.get("input")
    if not isinstance(user_input, str):
        return False, "Field 'input' must be a string"
    
    if not user_input.strip():
        return False, "Input cannot be empty"
    
    # Validate coordinates if provided
    lat = payload.get("lat")
    lon = payload.get("lon")
    
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            return False, "Both 'lat' and 'lon' must be provided together"
        
        try:
            lat = float(lat)
            lon = float(lon)
            is_valid, error = validate_coordinates(lat, lon)
            if not is_valid:
                return False, f"Invalid coordinates: {error}"
        except (ValueError, TypeError):
            return False, "Coordinates must be numeric values"
    
    # Validate tenant_id if provided
    tenant_id = payload.get("tenant_id")
    if tenant_id is not None:
        if not isinstance(tenant_id, str):
            return False, "Field 'tenant_id' must be a string"
        if not tenant_id.strip():
            return False, "Field 'tenant_id' cannot be empty"
    
    return True, None


def extract_location_info(payload: dict, user_input: str) -> Dict[str, Any]:
    """
    Extract and validate location information from payload or user input.
    
    Args:
        payload: Request payload
        user_input: User's input text
        
    Returns:
        Dictionary with location info: {lat, lon, tenant_id, city_info, location_source}
    """
    location_info = {
        "lat": payload.get("lat"),
        "lon": payload.get("lon"),
        "tenant_id": payload.get("tenant_id", "default"),
        "city_info": None,
        "location_source": "none"
    }
    
    try:
        # Try to get location from coordinates
        if location_info["lat"] is not None and location_info["lon"] is not None:
            location_info["location_source"] = "coordinates"
            
            # Try to map coordinates to a tenant city
            if location_info["tenant_id"] == "default":
                city_info = get_city_info(location_info["tenant_id"])
                if city_info:
                    location_info["city_info"] = city_info
        
        # Try to detect location from text if not provided
        elif "near me" in user_input.lower() or any(
            keyword in user_input.lower() 
            for keyword in ["in", "at", "near", "around"]
        ):
            detected = detect_location_from_text(user_input)
            if detected.get("found"):
                location_info["tenant_id"] = detected.get("tenant_id", "default")
                location_info["city_info"] = detected.get("city_info")
                location_info["location_source"] = "text_detection"
                logger.info(
                    f"Detected location from text: {location_info['tenant_id']}"
                )
        
        # Get city info for tenant_id if we have it
        if not location_info["city_info"] and location_info["tenant_id"] != "default":
            location_info["city_info"] = get_city_info(location_info["tenant_id"])
            
    except Exception as e:
        logger.warning(f"Error extracting location info: {e}")
    
    return location_info


def route_request(payload: dict) -> dict:
    """
    Main routing function for PENNY requests.
    Routes requests to appropriate agents based on intent classification.
    
    Args:
        payload: Request payload with user input and metadata
        
    Returns:
        Response dictionary with agent output and metadata
    """
    start_time = time.time()
    
    try:
        # Validate request payload
        is_valid, error_msg = validate_request_payload(payload)
        if not is_valid:
            logger.warning(f"Invalid request payload: {error_msg}")
            return {
                "error": "Oops! I couldn't understand that request. " + error_msg,
                "status": "validation_error",
                "response_time_ms": round((time.time() - start_time) * 1000)
            }
        
        # Extract basic request info
        user_input = payload.get("input", "").strip()
        role = payload.get("role", "unknown")
        
        # Sanitize input for logging (remove PII)
        sanitized_input = sanitize_for_logging(user_input)
        
        # Extract location information
        location_info = extract_location_info(payload, user_input)
        tenant_id = location_info["tenant_id"]
        lat = location_info["lat"]
        lon = location_info["lon"]
        
        logger.info(
            f"Routing request from tenant '{tenant_id}', role '{role}', "
            f"location_source: {location_info['location_source']}"
        )
        
        # Classify intent using enhanced intent classifier
        try:
            intent_result = classify_intent_detailed(user_input)
            intent = intent_result["intent"]
            confidence = intent_result["confidence"]
            is_compound = intent_result["is_compound"]
            
            logger.info(
                f"Intent classified: {intent} (confidence: {confidence:.2f}, "
                f"compound: {is_compound})"
            )
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            intent = IntentType.GENERAL
            confidence = 0.0
            is_compound = False
        
        # EMERGENCY ROUTING - Highest priority
        if intent == IntentType.EMERGENCY:
            logger.critical(
                f"EMERGENCY intent detected from tenant '{tenant_id}'. "
                f"Routing to safety protocols."
            )
            
            # Log emergency interaction for compliance
            log_interaction(
                tenant_id=tenant_id,
                interaction_type="emergency",
                intent="emergency",
                response_time_ms=round((time.time() - start_time) * 1000),
                success=True,
                metadata={
                    "sanitized_input": sanitized_input,
                    "requires_followup": True,
                    "escalation_level": "critical"
                }
            )
            
            return {
                "response": (
                    "I can see you might need urgent help. Please contact:\n\n"
                    "🚨 **Emergency Services**: 911\n"
                    "💚 **National Crisis Hotline**: 988\n"
                    "💬 **Crisis Text Line**: Text HOME to 741741\n\n"
                    "You're not alone, and help is available 24/7."
                ),
                "intent": "emergency",
                "model_id": "safety-agent",
                "tenant_id": tenant_id,
                "user_role": role,
                "response_time_ms": round((time.time() - start_time) * 1000),
                "escalation_required": True
            }
        
        # WEATHER ROUTING
        if intent == IntentType.WEATHER:
            return handle_weather_request(
                user_input, lat, lon, tenant_id, role, start_time
            )
        
        # WEATHER + EVENTS ROUTING (compound intent)
        if intent == IntentType.WEATHER_EVENTS or (
            is_compound and "weather" in intent_result.get("components", [])
        ):
            return handle_weather_events_request(
                user_input, lat, lon, tenant_id, role, start_time
            )
        
        # EVENTS ROUTING
        if intent == IntentType.EVENTS:
            return handle_events_request(
                user_input, tenant_id, role, start_time
            )
        
        # TOOL-BASED ROUTING (transit, alerts, resources, etc.)
        if intent in [
            IntentType.TRANSIT, IntentType.ALERTS, IntentType.RESOURCES,
            IntentType.PUBLIC_WORKS
        ]:
            return handle_tool_based_request(
                user_input, intent, tenant_id, role, start_time
            )
        
        # TRANSLATION ROUTING
        if intent == IntentType.TRANSLATION or any(
            lang in user_input.lower() for lang in SUPPORTED_LANGUAGES
        ):
            return handle_translation_request(
                user_input, tenant_id, role, start_time
            )
        
        # DOCUMENT/PDF ROUTING
        if any(term in user_input.lower() for term in ["form", "upload", "document", "pdf"]):
            return handle_document_request(
                user_input, tenant_id, role, start_time
            )
        
        # SENTIMENT ANALYSIS ROUTING
        if any(term in user_input.lower() for term in ["angry", "sentiment", "how do i feel"]):
            return handle_sentiment_request(
                user_input, tenant_id, role, start_time
            )
        
        # BIAS DETECTION ROUTING
        if any(term in user_input.lower() for term in ["bias", "is this fair", "offensive"]):
            return handle_bias_request(
                user_input, tenant_id, role, start_time
            )
        
        # GENERAL/FALLBACK ROUTING
        return handle_general_request(
            user_input, tenant_id, role, start_time
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in route_request: {e}", exc_info=True)
        
        return {
            "error": (
                "I'm having trouble processing that right now. "
                "Could you try rephrasing your question? 💛"
            ),
            "status": "server_error",
            "response_time_ms": round((time.time() - start_time) * 1000)
        }


def handle_weather_request(
    user_input: str, lat: Optional[float], lon: Optional[float],
    tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle weather-specific requests."""
    try:
        if lat is None or lon is None:
            return {
                "response": (
                    "I'd love to help with the weather! To give you accurate info, "
                    "I need your location. Can you share your coordinates or tell me "
                    "what city you're in? 🌤️"
                ),
                "intent": "weather",
                "model_id": "weather-agent",
                "tenant_id": tenant_id,
                "user_role": role,
                "response_time_ms": round((time.time() - start_time) * 1000),
                "location_required": True
            }
        
        # Get weather data
        weather = asyncio.run(get_weather_for_location(lat, lon))
        
        # Generate recommendations
        recs = weather_to_event_recommendations(weather)
        outfit = recommend_outfit(
            weather.get("temperature", {}).get("value"),
            weather.get("phrase", "")
        )
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000)
        
        # Log successful interaction
        log_interaction(
            tenant_id=tenant_id,
            interaction_type="weather",
            intent="weather",
            response_time_ms=response_time,
            success=True
        )
        
        return {
            "response": {
                "weather": weather,
                "recommendations": recs,
                "outfit": outfit
            },
            "intent": "weather",
            "model_id": "weather-agent",
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": response_time
        }
        
    except Exception as e:
        logger.error(f"Error handling weather request: {e}")
        
        return {
            "response": (
                "I'm having trouble getting the weather right now. "
                "The weather service might be down. Want to try again in a moment? 🌦️"
            ),
            "intent": "weather",
            "model_id": "weather-agent",
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "weather_service_unavailable"
        }


def handle_weather_events_request(
    user_input: str, lat: Optional[float], lon: Optional[float],
    tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle combined weather and events requests."""
    try:
        if lat is None or lon is None:
            return {
                "response": (
                    "I can suggest events based on the weather! "
                    "To do that, I need your location. Can you share your coordinates "
                    "or tell me what city you're in? 🎉☀️"
                ),
                "intent": "weather_events",
                "model_id": "event-weather-agent",
                "tenant_id": tenant_id,
                "user_role": role,
                "response_time_ms": round((time.time() - start_time) * 1000),
                "location_required": True
            }
        
        # Get combined weather and event recommendations
        combined = asyncio.run(
            get_event_recommendations_with_weather(tenant_id, lat, lon)
        )
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000)
        
        # Log successful interaction
        log_interaction(
            tenant_id=tenant_id,
            interaction_type="weather_events",
            intent="weather_events",
            response_time_ms=response_time,
            success=True
        )
        
        return {
            "response": combined,
            "intent": "weather_events",
            "model_id": "event-weather-agent",
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": response_time
        }
        
    except Exception as e:
        logger.error(f"Error handling weather_events request: {e}")
        
        return {
            "response": (
                "I'm having trouble combining weather and events right now. "
                "Let me try to help you with just one or the other! 🤔"
            ),
            "intent": "weather_events",
            "model_id": "event-weather-agent",
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "combined_service_unavailable"
        }


def handle_events_request(
    user_input: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle events-only requests."""
    try:
        tool_response = handle_tool_request(user_input, role, tenant_id, "events")
        end_time = time.time()
        
        return {
            "response": tool_response.get("response"),
            "intent": "events",
            "model_id": "event-agent",
            "tenant_id": tool_response.get("city", tenant_id),
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling events request: {e}")
        
        return {
            "response": (
                "I'm having trouble finding events right now. "
                "Let me know what you're interested in and I'll do my best! 🎭"
            ),
            "intent": "events",
            "model_id": "event-agent",
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "events_service_unavailable"
        }


def handle_tool_based_request(
    user_input: str, intent: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle tool-based requests (transit, alerts, resources, etc.)."""
    try:
        tool_response = handle_tool_request(user_input, role, tenant_id, intent)
        end_time = time.time()
        
        return {
            "response": tool_response.get("response"),
            "intent": str(intent),
            "model_id": tool_response.get("tool", "tool-agent"),
            "tenant_id": tool_response.get("city", tenant_id),
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling tool request for {intent}: {e}")
        
        return {
            "response": (
                f"I'm having trouble with that {intent} request right now. "
                "Could you try again or ask me something else? 💛"
            ),
            "intent": str(intent),
            "model_id": "tool-agent",
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": f"{intent}_service_unavailable"
        }


def handle_translation_request(
    user_input: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle translation requests."""
    model_id = "penny-translate-agent"
    
    try:
        model = models.get(model_id)
        if not model:
            raise ValueError(f"Translation model not found: {model_id}")
        
        result = model.predict(user_input)
        end_time = time.time()
        
        return {
            "response": result,
            "intent": "translation",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling translation request: {e}")
        
        return {
            "response": (
                "I'm having trouble with translation right now. "
                "Which language would you like help with? 🌍"
            ),
            "intent": "translation",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "translation_service_unavailable"
        }


def handle_document_request(
    user_input: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle document/PDF processing requests."""
    model_id = "penny-doc-agent"
    
    try:
        model = models.get(model_id)
        if not model:
            raise ValueError(f"Document model not found: {model_id}")
        
        result = model.predict(user_input)
        end_time = time.time()
        
        return {
            "response": result,
            "intent": "document",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling document request: {e}")
        
        return {
            "response": (
                "I'm having trouble processing documents right now. "
                "What kind of form or document do you need help with? 📄"
            ),
            "intent": "document",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "document_service_unavailable"
        }


def handle_sentiment_request(
    user_input: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle sentiment analysis requests."""
    model_id = "penny-sentiment-agent"
    
    try:
        model = models.get(model_id)
        if not model:
            raise ValueError(f"Sentiment model not found: {model_id}")
        
        result = model.predict(user_input)
        end_time = time.time()
        
        return {
            "response": result,
            "intent": "sentiment",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling sentiment request: {e}")
        
        return {
            "response": (
                "I'm having trouble analyzing sentiment right now. "
                "How are you feeling about things? 💭"
            ),
            "intent": "sentiment",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "sentiment_service_unavailable"
        }


def handle_bias_request(
    user_input: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle bias detection requests."""
    model_id = "penny-bias-checker"
    
    try:
        model = models.get(model_id)
        if not model:
            raise ValueError(f"Bias model not found: {model_id}")
        
        result = model.predict(user_input)
        end_time = time.time()
        
        return {
            "response": result,
            "intent": "bias_check",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling bias request: {e}")
        
        return {
            "response": (
                "I'm having trouble checking for bias right now. "
                "What content would you like me to review? ⚖️"
            ),
            "intent": "bias_check",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "bias_service_unavailable"
        }


def handle_general_request(
    user_input: str, tenant_id: str, role: str, start_time: float
) -> dict:
    """Handle general/fallback requests."""
    model_id = "penny-core-agent"
    
    try:
        model = models.get(model_id)
        if not model:
            raise ValueError(f"Core model not found: {model_id}")
        
        result = model.predict(user_input)
        end_time = time.time()
        
        return {
            "response": result,
            "intent": "general",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        logger.error(f"Error handling general request: {e}")
        
        return {
            "response": (
                "I'm having some technical difficulties right now. "
                "Can you try asking your question in a different way? "
                "Or let me know if you need help with weather, events, or services! 💛"
            ),
            "intent": "general",
            "model_id": model_id,
            "tenant_id": tenant_id,
            "user_role": role,
            "response_time_ms": round((time.time() - start_time) * 1000),
            "error": "general_service_unavailable"
        }


@router.post("/chat", response_model=Dict[str, Any])
async def chat_endpoint(payload: Dict[str, Any]) -> JSONResponse:
    """
    💬 Main chat endpoint for Penny.
    
    Processes user requests and routes them to appropriate handlers.
    
    Args:
        payload: Request payload with 'input', 'tenant_id', 'lat', 'lon', etc.
        
    Returns:
        JSONResponse with Penny's response
    """
    try:
        result = route_request(payload)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "I'm having trouble processing that right now. Please try again! 💛",
                "detail": str(e) if os.getenv("DEBUG_MODE", "false").lower() == "true" else None
            }
        )


@router.get("/health/router", response_model=Dict[str, Any])
async def router_health_endpoint() -> JSONResponse:
    """
    📊 Router health check endpoint.
    
    Returns:
        Health status of the router component
    """
    try:
        health = get_router_health()
        return JSONResponse(status_code=200, content=health)
    except Exception as e:
        logger.error(f"Router health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "degraded",
                "error": str(e)
            }
        )


def get_router_health() -> dict:
    """
    Check router health status.
    
    Returns:
        Health status dictionary
    """
    try:
        return {
            "status": "operational",
            "model_loader": "initialized" if models else "not_initialized",
            "supported_languages": len(SUPPORTED_LANGUAGES),
            "routing_capabilities": [
                "weather", "events", "weather_events", "translation",
                "documents", "sentiment", "bias_detection", "general"
            ]
        }
    except Exception as e:
        logger.error(f"Router health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e)
        }