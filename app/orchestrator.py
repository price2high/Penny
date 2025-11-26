"""
🎭 PENNY Orchestrator - Request Routing & Coordination Engine

This is Penny's decision-making brain. She analyzes each request, determines
the best way to help, and coordinates between her specialized AI models and
civic data tools.

MISSION: Route every resident request to the right resource while maintaining
Penny's warm, helpful personality and ensuring fast, accurate responses.

FEATURES:
- Enhanced intent classification with confidence scoring
- Compound intent handling (weather + events)
- Graceful fallbacks when services are unavailable
- Performance tracking for all operations
- Context-aware responses
- Emergency routing with immediate escalation

ENHANCEMENTS (Phase 1):
- ✅ Structured logging with performance tracking
- ✅ Safe imports with availability flags
- ✅ Result format checking helper
- ✅ Enhanced error handling patterns
- ✅ Service availability tracking
- ✅ Fixed function signature mismatches
- ✅ Integration with enhanced modules
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# --- ENHANCED MODULE IMPORTS ---
from app.intents import classify_intent_detailed, IntentType, IntentMatch
from app.location_utils import (
    extract_location_detailed,
    LocationMatch,
    LocationStatus,
    get_city_coordinates
)
from app.logging_utils import (
    log_interaction,
    sanitize_for_logging,
    LogLevel
)

# --- AGENT IMPORTS (with availability tracking) ---
try:
    from app.weather_agent import (
        get_weather_for_location,
        recommend_outfit,
        weather_to_event_recommendations,
        format_weather_summary
    )
    WEATHER_AGENT_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Weather agent not available: {e}")
    WEATHER_AGENT_AVAILABLE = False

try:
    from app.event_weather import get_event_recommendations_with_weather
    EVENT_WEATHER_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Event weather integration not available: {e}")
    EVENT_WEATHER_AVAILABLE = False

try:
    from app.tool_agent import handle_tool_request
    TOOL_AGENT_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Tool agent not available: {e}")
    TOOL_AGENT_AVAILABLE = False

# --- MODEL IMPORTS (with availability tracking) ---
try:
    from models.translation.translation_utils import translate_text
    TRANSLATION_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Translation service not available: {e}")
    TRANSLATION_AVAILABLE = False

try:
    from models.sentiment.sentiment_utils import get_sentiment_analysis
    SENTIMENT_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Sentiment service not available: {e}")
    SENTIMENT_AVAILABLE = False

try:
    from models.bias.bias_utils import check_bias
    BIAS_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Bias detection service not available: {e}")
    BIAS_AVAILABLE = False

try:
    from models.gemma.gemma_utils import generate_response
    LLM_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"LLM service not available: {e}")
    LLM_AVAILABLE = False

# --- LOGGING SETUP ---
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
CORE_MODEL_ID = "penny-core-agent"
MAX_RESPONSE_TIME_MS = 5000  # 5 seconds - log if exceeded

# --- TRACKING COUNTERS ---
_orchestration_count = 0
_emergency_count = 0


# ============================================================
# COMPATIBILITY HELPER - Result Format Checking
# ============================================================

def _check_result_success(
    result: Dict[str, Any],
    expected_keys: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    ✅ Check if a utility function result indicates success.
    
    Handles multiple return format patterns:
    - Explicit "success" key (preferred)
    - Presence of expected data keys (implicit success)
    - Presence of "error" key (explicit failure)
    
    This helper fixes compatibility issues where different utility
    functions return different result formats.
    
    Args:
        result: Dictionary returned from utility function
        expected_keys: List of keys that indicate successful data
        
    Returns:
        Tuple of (is_success, error_message)
        
    Example:
        result = await translate_text(message, "en", "es")
        success, error = _check_result_success(result, ["translated_text"])
        if success:
            text = result.get("translated_text")
    """
    # Check for explicit success key
    if "success" in result:
        return result["success"], result.get("error")
    
    # Check for explicit error (presence = failure)
    if "error" in result and result["error"]:
        return False, result["error"]
    
    # Check for expected data keys (implicit success)
    has_data = any(key in result for key in expected_keys)
    if has_data:
        return True, None
    
    # Unknown format - assume failure
    return False, "Unexpected response format"


# ============================================================
# SERVICE AVAILABILITY CHECK
# ============================================================

def get_service_availability() -> Dict[str, bool]:
    """
    📊 Returns which services are currently available.
    
    Used for health checks, debugging, and deciding whether
    to attempt service calls or use fallbacks.
    
    Returns:
        Dictionary mapping service names to availability status
    """
    return {
        "translation": TRANSLATION_AVAILABLE,
        "sentiment": SENTIMENT_AVAILABLE,
        "bias_detection": BIAS_AVAILABLE,
        "llm": LLM_AVAILABLE,
        "tool_agent": TOOL_AGENT_AVAILABLE,
        "weather": WEATHER_AGENT_AVAILABLE,
        "event_weather": EVENT_WEATHER_AVAILABLE
    }


# ============================================================
# ORCHESTRATION RESULT STRUCTURE
# ============================================================

@dataclass
class OrchestrationResult:
    """
    📦 Structured result from orchestration pipeline.
    
    This format is used throughout the system for consistency
    and makes it easy to track what happened during request processing.
    """
    intent: str                                  # Detected intent
    reply: str                                   # User-facing response
    success: bool                                # Whether request succeeded
    tenant_id: Optional[str] = None              # City/location identifier
    data: Optional[Dict[str, Any]] = None        # Raw data from services
    model_id: Optional[str] = None               # Which model/service was used
    error: Optional[str] = None                  # Error message if failed
    response_time_ms: Optional[float] = None
    confidence: Optional[float] = None           # Intent confidence score
    fallback_used: bool = False                  # True if fallback logic triggered
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary for API responses."""
        return {
            "intent": self.intent,
            "reply": self.reply,
            "success": self.success,
            "tenant_id": self.tenant_id,
            "data": self.data,
            "model_id": self.model_id,
            "error": self.error,
            "response_time_ms": self.response_time_ms,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used
        }


# ============================================================
# MAIN ORCHESTRATOR FUNCTION (ENHANCED)
# ============================================================

async def run_orchestrator(
    message: str,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    🧠 Main decision-making brain of Penny.
    
    This function:
    1. Analyzes the user's message to determine intent
    2. Extracts location/city information
    3. Routes to the appropriate specialized service
    4. Handles errors gracefully with helpful fallbacks
    5. Tracks performance and logs the interaction
    
    Args:
        message: User's input text
        context: Additional context (tenant_id, lat, lon, session_id, etc.)
        
    Returns:
        Dictionary with response and metadata
        
    Example:
        result = await run_orchestrator(
            message="What's the weather in Atlanta?",
            context={"lat": 33.7490, "lon": -84.3880}
        )
    """
    global _orchestration_count
    _orchestration_count += 1
    
    start_time = time.time()
    
    # Initialize context if not provided
    if context is None:
        context = {}
    
    # Sanitize message for logging (PII protection)
    safe_message = sanitize_for_logging(message)
    logger.info(f"🎭 Orchestrator processing: '{safe_message[:50]}...'")
    
    try:
        # === STEP 1: CLASSIFY INTENT (Enhanced) ===
        intent_result = classify_intent_detailed(message)
        intent = intent_result.intent
        confidence = intent_result.confidence
        
        logger.info(
            f"Intent detected: {intent.value} "
            f"(confidence: {confidence:.2f})"
        )
        
        # === STEP 2: EXTRACT LOCATION ===
        tenant_id = context.get("tenant_id")
        lat = context.get("lat")
        lon = context.get("lon")
        
        # If tenant_id not provided, try to extract from message
        if not tenant_id or tenant_id == "unknown":
            location_result = extract_location_detailed(message)
            
            if location_result.status == LocationStatus.FOUND:
                tenant_id = location_result.tenant_id
                logger.info(f"Location extracted: {tenant_id}")
                
                # Get coordinates for this tenant if available
                coords = get_city_coordinates(tenant_id)
                if coords and lat is None and lon is None:
                    lat, lon = coords["lat"], coords["lon"]
                    logger.info(f"Coordinates loaded: {lat}, {lon}")
                    
            elif location_result.status == LocationStatus.USER_LOCATION_NEEDED:
                logger.info("User location services needed")
            else:
                logger.info(f"No location detected: {location_result.status}")
        
        # === STEP 3: HANDLE EMERGENCY INTENTS (CRITICAL) ===
        if intent == IntentType.EMERGENCY:
            return await _handle_emergency(
                message=message,
                context=context,
                start_time=start_time
            )
        
        # === STEP 4: ROUTE TO APPROPRIATE HANDLER ===
        
        # Translation
        if intent == IntentType.TRANSLATION:
            result = await _handle_translation(message, context)
        
        # Sentiment Analysis
        elif intent == IntentType.SENTIMENT_ANALYSIS:
            result = await _handle_sentiment(message, context)
        
        # Bias Detection
        elif intent == IntentType.BIAS_DETECTION:
            result = await _handle_bias(message, context)
        
        # Document Processing
        elif intent == IntentType.DOCUMENT_PROCESSING:
            result = await _handle_document(message, context)
        
        # Weather (includes compound weather+events handling)
        elif intent == IntentType.WEATHER:
            result = await _handle_weather(
                message=message,
                context=context,
                tenant_id=tenant_id,
                lat=lat,
                lon=lon,
                intent_result=intent_result
            )
        
        # Events
        elif intent == IntentType.EVENTS:
            result = await _handle_events(
                message=message,
                context=context,
                tenant_id=tenant_id,
                lat=lat,
                lon=lon,
                intent_result=intent_result
            )

        # Local Resources
        elif intent == IntentType.LOCAL_RESOURCES:
            result = await _handle_local_resources(
                message=message,
                context=context,
                tenant_id=tenant_id,
                lat=lat,
                lon=lon
            )
        
        # Greeting, Help, Unknown
        elif intent in [IntentType.GREETING, IntentType.HELP, IntentType.UNKNOWN]:
            result = await _handle_conversational(
                message=message,
                intent=intent,
                context=context
            )
        
        else:
            # Unhandled intent type (shouldn't happen, but safety net)
            result = await _handle_fallback(message, intent, context)
        
        # === STEP 5: ADD METADATA & LOG INTERACTION ===
        response_time = (time.time() - start_time) * 1000
        result.response_time_ms = round(response_time, 2)
        result.confidence = confidence
        result.tenant_id = tenant_id
        
        # Log the interaction with structured logging
        log_interaction(
            tenant_id=tenant_id or "unknown",
            interaction_type="orchestration",
            intent=intent.value,
            response_time_ms=response_time,
            success=result.success,
            metadata={
                "confidence": confidence,
                "fallback_used": result.fallback_used,
                "model_id": result.model_id,
                "orchestration_count": _orchestration_count
            }
        )
        
        # Log slow responses
        if response_time > MAX_RESPONSE_TIME_MS:
            logger.warning(
                f"⚠️ Slow response: {response_time:.0f}ms "
                f"(intent: {intent.value})"
            )
        
        logger.info(
            f"✅ Orchestration complete: {intent.value} "
            f"({response_time:.0f}ms)"
        )
        
        return result.to_dict()
    
    except Exception as e:
        # === CATASTROPHIC FAILURE HANDLER ===
        response_time = (time.time() - start_time) * 1000
        logger.error(
            f"❌ Orchestrator error: {e} "
            f"(response_time: {response_time:.0f}ms)",
            exc_info=True
        )
        
        # Log failed interaction
        log_interaction(
            tenant_id=context.get("tenant_id", "unknown"),
            interaction_type="orchestration_error",
            intent="error",
            response_time_ms=response_time,
            success=False,
            metadata={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        
        error_result = OrchestrationResult(
            intent="error",
            reply=(
                "I'm having trouble processing your request right now. "
                "Please try again in a moment, or let me know if you need "
                "immediate assistance! 💛"
            ),
            success=False,
            error=str(e),
            model_id="orchestrator",
            fallback_used=True,
            response_time_ms=round(response_time, 2)
        )
        
        return error_result.to_dict()


# ============================================================
# SPECIALIZED INTENT HANDLERS (ENHANCED)
# ============================================================

async def _handle_emergency(
    message: str,
    context: Dict[str, Any],
    start_time: float
) -> OrchestrationResult:
    """
    🚨 CRITICAL: Emergency intent handler.
    
    This function handles crisis situations with immediate routing
    to appropriate services. All emergency interactions are logged
    for compliance and safety tracking.
    
    IMPORTANT: This is a compliance-critical function. All emergency
    interactions must be logged and handled with priority.
    """
    global _emergency_count
    _emergency_count += 1
    
    # Sanitize message for logging (but keep full context for safety review)
    safe_message = sanitize_for_logging(message)
    logger.warning(f"🚨 EMERGENCY INTENT DETECTED (#{_emergency_count}): {safe_message[:100]}")
    
    # TODO: Integrate with safety_utils.py when enhanced
    # from app.safety_utils import route_emergency
    # result = await route_emergency(message, context)
    
    # For now, provide crisis resources
    reply = (
        "🚨 **If this is a life-threatening emergency, please call 911 immediately.**\n\n"
        "For crisis support:\n"
        "- **National Suicide Prevention Lifeline:** 988\n"
        "- **Crisis Text Line:** Text HOME to 741741\n"
        "- **National Domestic Violence Hotline:** 1-800-799-7233\n\n"
        "I'm here to help connect you with local resources. "
        "What kind of support do you need right now?"
    )
    
    # Log emergency interaction for compliance (CRITICAL)
    response_time = (time.time() - start_time) * 1000
    log_interaction(
        tenant_id=context.get("tenant_id", "emergency"),
        interaction_type="emergency",
        intent=IntentType.EMERGENCY.value,
        response_time_ms=response_time,
        success=True,
        metadata={
            "emergency_number": _emergency_count,
            "message_length": len(message),
            "timestamp": datetime.now().isoformat(),
            "action": "crisis_resources_provided"
        }
    )
    
    logger.critical(
        f"EMERGENCY LOG #{_emergency_count}: Resources provided "
        f"({response_time:.0f}ms)"
    )
    
    return OrchestrationResult(
        intent=IntentType.EMERGENCY.value,
        reply=reply,
        success=True,
        model_id="emergency_router",
        data={"crisis_resources_provided": True},
        response_time_ms=round(response_time, 2)
    )


async def _handle_translation(
    message: str,
    context: Dict[str, Any]
) -> OrchestrationResult:
    """
    🌍 Translation handler - 27 languages supported.
    
    Handles translation requests with graceful fallback if service
    is unavailable.
    """
    logger.info("🌍 Processing translation request")
    
    # Check service availability first
    if not TRANSLATION_AVAILABLE:
        logger.warning("Translation service not available")
        return OrchestrationResult(
            intent=IntentType.TRANSLATION.value,
            reply="Translation isn't available right now. Try again soon! 🌍",
            success=False,
            error="Service not loaded",
            fallback_used=True
        )
    
    try:
        # Extract language parameters from context
        source_lang = context.get("source_lang", "eng_Latn")
        target_lang = context.get("target_lang", "spa_Latn")
        
        # TODO: Parse languages from message when enhanced
        # Example: "Translate 'hello' to Spanish"
        
        result = await translate_text(message, source_lang, target_lang)
        
        # Use compatibility helper to check result
        success, error = _check_result_success(result, ["translated_text"])
        
        if success:
            translated = result.get("translated_text", "")
            reply = (
                f"Here's the translation:\n\n"
                f"**{translated}**\n\n"
                f"(Translated from {source_lang} to {target_lang})"
            )
            
            return OrchestrationResult(
                intent=IntentType.TRANSLATION.value,
                reply=reply,
                success=True,
                data=result,
                model_id="penny-translate-agent"
            )
        else:
            raise Exception(error or "Translation failed")
    
    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        return OrchestrationResult(
            intent=IntentType.TRANSLATION.value,
            reply=(
                "I had trouble translating that. Could you rephrase? 💬"
            ),
            success=False,
            error=str(e),
            fallback_used=True
        )


async def _handle_sentiment(
    message: str,
    context: Dict[str, Any]
) -> OrchestrationResult:
    """
    😊 Sentiment analysis handler.
    
    Analyzes the emotional tone of text with graceful fallback
    if service is unavailable.
    """
    logger.info("😊 Processing sentiment analysis")
    
    # Check service availability first
    if not SENTIMENT_AVAILABLE:
        logger.warning("Sentiment service not available")
        return OrchestrationResult(
            intent=IntentType.SENTIMENT_ANALYSIS.value,
            reply="Sentiment analysis isn't available right now. Try again soon! 😊",
            success=False,
            error="Service not loaded",
            fallback_used=True
        )
    
    try:
        result = await get_sentiment_analysis(message)
        
        # Use compatibility helper to check result
        success, error = _check_result_success(result, ["label", "score"])
        
        if success:
            sentiment = result.get("label", "neutral")
            confidence = result.get("score", 0.0)
            
            reply = (
                f"The overall sentiment detected is: **{sentiment}**\n"
                f"Confidence: {confidence:.1%}"
            )
            
            return OrchestrationResult(
                intent=IntentType.SENTIMENT_ANALYSIS.value,
                reply=reply,
                success=True,
                data=result,
                model_id="penny-sentiment-agent"
            )
        else:
            raise Exception(error or "Sentiment analysis failed")
    
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}", exc_info=True)
        return OrchestrationResult(
            intent=IntentType.SENTIMENT_ANALYSIS.value,
            reply="I couldn't analyze the sentiment right now. Try again? 😊",
            success=False,
            error=str(e),
            fallback_used=True
        )

async def _handle_bias(
    message: str,
    context: Dict[str, Any]
) -> OrchestrationResult:
    """
    ⚖️ Bias detection handler.
    
    Analyzes text for potential bias patterns with graceful fallback
    if service is unavailable.
    """
    logger.info("⚖️ Processing bias detection")
    
    # Check service availability first
    if not BIAS_AVAILABLE:
        logger.warning("Bias detection service not available")
        return OrchestrationResult(
            intent=IntentType.BIAS_DETECTION.value,
            reply="Bias detection isn't available right now. Try again soon! ⚖️",
            success=False,
            error="Service not loaded",
            fallback_used=True
        )
    
    try:
        result = await check_bias(message)
        
        # Use compatibility helper to check result
        success, error = _check_result_success(result, ["analysis"])
        
        if success:
            analysis = result.get("analysis", [])
            
            if analysis:
                top_result = analysis[0]
                label = top_result.get("label", "unknown")
                score = top_result.get("score", 0.0)
                
                reply = (
                    f"Bias analysis complete:\n\n"
                    f"**Most likely category:** {label}\n"
                    f"**Confidence:** {score:.1%}"
                )
            else:
                reply = "The text appears relatively neutral. ⚖️"
            
            return OrchestrationResult(
                intent=IntentType.BIAS_DETECTION.value,
                reply=reply,
                success=True,
                data=result,
                model_id="penny-bias-checker"
            )
        else:
            raise Exception(error or "Bias detection failed")
    
    except Exception as e:
        logger.error(f"Bias detection error: {e}", exc_info=True)
        return OrchestrationResult(
            intent=IntentType.BIAS_DETECTION.value,
            reply="I couldn't check for bias right now. Try again? ⚖️",
            success=False,
            error=str(e),
            fallback_used=True
        )


async def _handle_document(
    message: str,
    context: Dict[str, Any]
) -> OrchestrationResult:
    """
    📄 Document processing handler.
    
    Note: Actual file upload happens in router.py via FastAPI.
    This handler just provides instructions.
    """
    logger.info("📄 Document processing requested")
    
    reply = (
        "I can help you process documents! 📄\n\n"
        "Please upload your document (PDF or image) using the "
        "`/upload-document` endpoint. I can extract text, analyze forms, "
        "and help you understand civic documents.\n\n"
        "What kind of document do you need help with?"
    )
    
    return OrchestrationResult(
        intent=IntentType.DOCUMENT_PROCESSING.value,
        reply=reply,
        success=True,
        model_id="document_router"
    )


async def _handle_weather(
    message: str,
    context: Dict[str, Any],
    tenant_id: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    intent_result: IntentMatch
) -> OrchestrationResult:
    """
    🌤️ Weather handler with compound intent support.
    
    Handles both simple weather queries and compound weather+events queries.
    Uses enhanced weather_agent.py with caching and performance tracking.
    """
    logger.info("🌤️ Processing weather request")
    
    # Check service availability first
    if not WEATHER_AGENT_AVAILABLE:
        logger.warning("Weather agent not available")
        return OrchestrationResult(
            intent=IntentType.WEATHER.value,
            reply="Weather service isn't available right now. Try again soon! 🌤️",
            success=False,
            error="Weather agent not loaded",
            fallback_used=True
        )
    
    # Check for compound intent (weather + events)
    is_compound = intent_result.is_compound or IntentType.EVENTS in intent_result.secondary_intents
    
    # Validate location
    if lat is None or lon is None:
        # Try to get coordinates from tenant_id
        if tenant_id:
            coords = get_city_coordinates(tenant_id)
            if coords and lat is None and lon is None:
                lat, lon = coords["lat"], coords["lon"]
                logger.info(f"Using city coordinates for {tenant_id}: {lat}, {lon}")
    
    if lat is None or lon is None:
        return OrchestrationResult(
            intent=IntentType.WEATHER.value,
            reply=(
                "I need to know your location to check the weather! 📍 "
                "You can tell me your city, or share your location."
            ),
            success=False,
            error="Location required"
        )
    
    try:
        # Use combined weather + events if compound intent detected
        if is_compound and tenant_id and EVENT_WEATHER_AVAILABLE:
            logger.info("Using weather+events combined handler")
            result = await get_event_recommendations_with_weather(tenant_id, lat, lon)
            
            # Build response
            weather = result.get("weather", {})
            weather_summary = result.get("weather_summary", "Weather unavailable")
            suggestions = result.get("suggestions", [])
            
            reply_lines = [f"🌤️ **Weather Update:**\n{weather_summary}\n"]
            
            if suggestions:
                reply_lines.append("\n📅 **Event Suggestions Based on Weather:**")
                for suggestion in suggestions[:5]:  # Top 5 suggestions
                    reply_lines.append(f"• {suggestion}")
            
            reply = "\n".join(reply_lines)
            
            return OrchestrationResult(
                intent=IntentType.WEATHER.value,
                reply=reply,
                success=True,
                data=result,
                model_id="weather_events_combined"
            )
        
        else:
            # Simple weather query using enhanced weather_agent
            weather = await get_weather_for_location(lat, lon)
            
            # Use enhanced weather_agent's format_weather_summary
            if format_weather_summary:
                weather_text = format_weather_summary(weather)
            else:
                # Fallback formatting
                temp = weather.get("temperature", {}).get("value")
                phrase = weather.get("phrase", "Conditions unavailable")
                if temp:
                    weather_text = f"{phrase}, {int(temp)}°F"
                else:
                    weather_text = phrase
            
            # Get outfit recommendation from enhanced weather_agent
            if recommend_outfit:
                temp = weather.get("temperature", {}).get("value", 70)
                condition = weather.get("phrase", "Clear")
                outfit = recommend_outfit(temp, condition)
                reply = f"🌤️ {weather_text}\n\n👕 {outfit}"
            else:
                reply = f"🌤️ {weather_text}"
            
            return OrchestrationResult(
                intent=IntentType.WEATHER.value,
                reply=reply,
                success=True,
                data=weather,
                model_id="azure-maps-weather"
            )
    
    except Exception as e:
        logger.error(f"Weather error: {e}", exc_info=True)
        return OrchestrationResult(
            intent=IntentType.WEATHER.value,
            reply=(
                "I'm having trouble getting weather data right now. "
                "Can I help you with something else? 💛"
            ),
            success=False,
            error=str(e),
            fallback_used=True
        )


async def _handle_events(
    message: str,
    context: Dict[str, Any],
    tenant_id: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    intent_result: IntentMatch
) -> OrchestrationResult:
    """
    📅 Events handler.
    
    Routes event queries to tool_agent with proper error handling
    and graceful degradation.
    """
    logger.info("📅 Processing events request")
    
    if not tenant_id:
        return OrchestrationResult(
            intent=IntentType.EVENTS.value,
            reply=(
                "I'd love to help you find events! 📅 "
                "Which city are you interested in? "
                "I have information for Atlanta, Birmingham, Chesterfield, "
                "El Paso, Providence, and Seattle."
            ),
            success=False,
            error="City required"
        )
    
    # Check tool agent availability
    if not TOOL_AGENT_AVAILABLE:
        logger.warning("Tool agent not available")
        return OrchestrationResult(
            intent=IntentType.EVENTS.value,
            reply=(
                "Event information isn't available right now. "
                "Try again soon! 📅"
            ),
            success=False,
            error="Tool agent not loaded",
            fallback_used=True
        )
    
    try:
        # FIXED: Add role parameter (compatibility fix)
        tool_response = await handle_tool_request(
            user_input=message,
            role=context.get("role", "resident"),  # ← ADDED
            lat=lat,
            lon=lon
        )
        
        reply = tool_response.get("response", "Events information retrieved.")
        
        return OrchestrationResult(
            intent=IntentType.EVENTS.value,
            reply=reply,
            success=True,
            data=tool_response,
            model_id="events_tool"
        )
    
    except Exception as e:
        logger.error(f"Events error: {e}", exc_info=True)
        return OrchestrationResult(
            intent=IntentType.EVENTS.value,
            reply=(
                "I'm having trouble loading event information right now. "
                "Check back soon! 📅"
            ),
            success=False,
            error=str(e),
            fallback_used=True
        )

async def _handle_local_resources(
    message: str,
    context: Dict[str, Any],
    tenant_id: Optional[str],
    lat: Optional[float],
    lon: Optional[float]
) -> OrchestrationResult:
    """
    🏛️ Local resources handler (shelters, libraries, food banks, etc.).
    
    Routes resource queries to tool_agent with proper error handling.
    """
    logger.info("🏛️ Processing local resources request")
    
    if not tenant_id:
        return OrchestrationResult(
            intent=IntentType.LOCAL_RESOURCES.value,
            reply=(
                "I can help you find local resources! 🏛️ "
                "Which city do you need help in? "
                "I cover Atlanta, Birmingham, Chesterfield, El Paso, "
                "Providence, and Seattle."
            ),
            success=False,
            error="City required"
        )
    
    # Check tool agent availability
    if not TOOL_AGENT_AVAILABLE:
        logger.warning("Tool agent not available")
        return OrchestrationResult(
            intent=IntentType.LOCAL_RESOURCES.value,
            reply=(
                "Resource information isn't available right now. "
                "Try again soon! 🏛️"
            ),
            success=False,
            error="Tool agent not loaded",
            fallback_used=True
        )
    
    try:
        # FIXED: Add role parameter (compatibility fix)
        tool_response = await handle_tool_request(
            user_input=message,
            role=context.get("role", "resident"),  # ← ADDED
            lat=lat,
            lon=lon
        )
        
        reply = tool_response.get("response", "Resource information retrieved.")
        
        return OrchestrationResult(
            intent=IntentType.LOCAL_RESOURCES.value,
            reply=reply,
            success=True,
            data=tool_response,
            model_id="resources_tool"
        )
    
    except Exception as e:
        logger.error(f"Resources error: {e}", exc_info=True)
        return OrchestrationResult(
            intent=IntentType.LOCAL_RESOURCES.value,
            reply=(
                "I'm having trouble finding resource information right now. "
                "Would you like to try a different search? 💛"
            ),
            success=False,
            error=str(e),
            fallback_used=True
        )


async def _handle_conversational(
    message: str,
    intent: IntentType,
    context: Dict[str, Any]
) -> OrchestrationResult:
    """
    💬 Handles conversational intents (greeting, help, unknown).
    Uses Penny's core LLM for natural responses with graceful fallback.
    """
    logger.info(f"💬 Processing conversational intent: {intent.value}")
    
    # Check LLM availability
    use_llm = LLM_AVAILABLE
    
    try:
        if use_llm:
            # Build prompt based on intent
            if intent == IntentType.GREETING:
                prompt = (
                    f"The user greeted you with: '{message}'\n\n"
                    "Respond warmly as Penny, introduce yourself briefly, "
                    "and ask how you can help them with civic services today."
                )
            
            elif intent == IntentType.HELP:
                prompt = (
                    f"The user asked for help: '{message}'\n\n"
                    "Explain Penny's main features:\n"
                    "- Finding local resources (shelters, libraries, food banks)\n"
                    "- Community events and activities\n"
                    "- Weather information\n"
                    "- 27-language translation\n"
                    "- Document processing help\n\n"
                    "Ask which city they need assistance in."
                )
            
            else:  # UNKNOWN
                prompt = (
                    f"The user said: '{message}'\n\n"
                    "You're not sure what they need help with. "
                    "Respond kindly, acknowledge their request, and ask them to "
                    "clarify or rephrase. Mention a few things you can help with."
                )
            
            # Call Penny's core LLM
            llm_result = await generate_response(prompt=prompt, max_new_tokens=200)
            
            # Use compatibility helper to check result
            success, error = _check_result_success(llm_result, ["response"])
            
            if success:
                reply = llm_result.get("response", "")
                
                return OrchestrationResult(
                    intent=intent.value,
                    reply=reply,
                    success=True,
                    data=llm_result,
                    model_id=CORE_MODEL_ID
                )
            else:
                raise Exception(error or "LLM generation failed")
        
        else:
            # LLM not available, use fallback directly
            logger.info("LLM not available, using fallback responses")
            raise Exception("LLM service not loaded")
    
    except Exception as e:
        logger.warning(f"Conversational handler using fallback: {e}")
        
        # Hardcoded fallback responses (Penny's friendly voice)
        fallback_replies = {
            IntentType.GREETING: (
                "Hi there! 👋 I'm Penny, your civic assistant. "
                "I can help you find local resources, events, weather, and more. "
                "What city are you in?"
            ),
            IntentType.HELP: (
                "I'm Penny! 💛 I can help you with:\n\n"
                "🏛️ Local resources (shelters, libraries, food banks)\n"
                "📅 Community events\n"
                "🌤️ Weather updates\n"
                "🌍 Translation (27 languages)\n"
                "📄 Document help\n\n"
                "What would you like to know about?"
            ),
            IntentType.UNKNOWN: (
                "I'm not sure I understood that. Could you rephrase? "
                "I'm best at helping with local services, events, weather, "
                "and translation! 💬"
            )
        }
        
        return OrchestrationResult(
            intent=intent.value,
            reply=fallback_replies.get(intent, "How can I help you today? 💛"),
            success=True,
            model_id="fallback",
            fallback_used=True
        )


async def _handle_fallback(
    message: str,
    intent: IntentType,
    context: Dict[str, Any]
) -> OrchestrationResult:
    """
    🆘 Ultimate fallback handler for unhandled intents.
    
    This is a safety net that should rarely trigger, but ensures
    users always get a helpful response.
    """
    logger.warning(f"⚠️ Fallback triggered for intent: {intent.value}")
    
    reply = (
        "I've processed your request, but I'm not sure how to help with that yet. "
        "I'm still learning! 🤖\n\n"
        "I'm best at:\n"
        "🏛️ Finding local resources\n"
        "📅 Community events\n"
        "🌤️ Weather updates\n"
        "🌍 Translation\n\n"
        "Could you rephrase your question? 💛"
    )
    
    return OrchestrationResult(
        intent=intent.value,
        reply=reply,
        success=False,
        error="Unhandled intent",
        fallback_used=True
    )


# ============================================================
# HEALTH CHECK & DIAGNOSTICS (ENHANCED)
# ============================================================

def get_orchestrator_health() -> Dict[str, Any]:
    """
    📊 Returns comprehensive orchestrator health status.
    
    Used by the main application health check endpoint to monitor
    the orchestrator and all its service dependencies.
    
    Returns:
        Dictionary with health information including:
        - status: operational/degraded
        - service_availability: which services are loaded
        - statistics: orchestration counts
        - supported_intents: list of all intent types
        - features: available orchestrator features
    """
    # Get service availability
    services = get_service_availability()
    
    # Determine overall status
    # Orchestrator is operational even if some services are down (graceful degradation)
    critical_services = ["weather", "tool_agent"]  # Must have these
    critical_available = all(services.get(svc, False) for svc in critical_services)
    
    status = "operational" if critical_available else "degraded"
    
    return {
        "status": status,
        "core_model": CORE_MODEL_ID,
        "max_response_time_ms": MAX_RESPONSE_TIME_MS,
        "statistics": {
            "total_orchestrations": _orchestration_count,
            "emergency_interactions": _emergency_count
        },
        "service_availability": services,
        "supported_intents": [intent.value for intent in IntentType],
        "features": {
            "emergency_routing": True,
            "compound_intents": True,
            "fallback_handling": True,
            "performance_tracking": True,
            "context_aware": True,
            "multi_language": TRANSLATION_AVAILABLE,
            "sentiment_analysis": SENTIMENT_AVAILABLE,
            "bias_detection": BIAS_AVAILABLE,
            "weather_integration": WEATHER_AGENT_AVAILABLE,
            "event_recommendations": EVENT_WEATHER_AVAILABLE
        }
    }


def get_orchestrator_stats() -> Dict[str, Any]:
    """
    📈 Returns orchestrator statistics.
    
    Useful for monitoring and analytics.
    """
    return {
        "total_orchestrations": _orchestration_count,
        "emergency_interactions": _emergency_count,
        "services_available": sum(1 for v in get_service_availability().values() if v),
        "services_total": len(get_service_availability())
    }


# ============================================================
# TESTING & DEBUGGING (ENHANCED)
# ============================================================

if __name__ == "__main__":
    """
    🧪 Test the orchestrator with sample queries.
    Run with: python -m app.orchestrator
    """
    import asyncio
    
    print("=" * 60)
    print("🧪 Testing Penny's Orchestrator")
    print("=" * 60)
    
    # Display service availability first
    print("\n📊 Service Availability Check:")
    services = get_service_availability()
    for service, available in services.items():
        status = "✅" if available else "❌"
        print(f"  {status} {service}: {'Available' if available else 'Not loaded'}")
    
    print("\n" + "=" * 60)
    
    test_queries = [
        {
            "name": "Greeting",
            "message": "Hi Penny!",
            "context": {}
        },
        {
            "name": "Weather with location",
            "message": "What's the weather?",
            "context": {"lat": 33.7490, "lon": -84.3880}
        },
        {
            "name": "Events in city",
            "message": "Events in Atlanta",
            "context": {"tenant_id": "atlanta_ga"}
        },
        {
            "name": "Help request",
            "message": "I need help",
            "context": {}
        },
        {
            "name": "Translation",
            "message": "Translate hello",
            "context": {"source_lang": "eng_Latn", "target_lang": "spa_Latn"}
        }
    ]
    
    async def run_tests():
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- Test {i}: {query['name']} ---")
            print(f"Query: {query['message']}")
            
            try:
                result = await run_orchestrator(query["message"], query["context"])
                print(f"Intent: {result['intent']}")
                print(f"Success: {result['success']}")
                print(f"Fallback: {result.get('fallback_used', False)}")
                
                # Truncate long replies
                reply = result['reply']
                if len(reply) > 150:
                    reply = reply[:150] + "..."
                print(f"Reply: {reply}")
                
                if result.get('response_time_ms'):
                    print(f"Response time: {result['response_time_ms']:.0f}ms")
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    asyncio.run(run_tests())
    
    print("\n" + "=" * 60)
    print("📊 Final Statistics:")
    stats = get_orchestrator_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("✅ Tests complete")
    print("=" * 60)