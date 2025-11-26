# app/intents.py
"""
🎯 Penny's Intent Classification System
Rule-based intent classifier designed for civic engagement queries.

CURRENT: Simple keyword matching (fast, predictable, debuggable)
FUTURE: Will upgrade to ML/embedding-based classification (Gemma/LayoutLM)

This approach allows Penny to understand resident needs and route them
to the right civic systems — weather, resources, events, translation, etc.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# --- LOGGING SETUP (Azure-friendly) ---
logger = logging.getLogger(__name__)


# --- INTENT CATEGORIES (Enumerated for type safety) ---
class IntentType(str, Enum):
    """
    Penny's supported intent categories.
    Each maps to a specific civic assistance pathway.
    """
    WEATHER = "weather"
    GREETING = "greeting"
    LOCAL_RESOURCES = "local_resources"
    EVENTS = "events"
    TRANSLATION = "translation"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    BIAS_DETECTION = "bias_detection"
    DOCUMENT_PROCESSING = "document_processing"
    HELP = "help"
    EMERGENCY = "emergency"  # Critical safety routing
    UNKNOWN = "unknown"


@dataclass
class IntentMatch:
    """
    Structured intent classification result.
    Includes confidence score and matched keywords for debugging.
    """
    intent: IntentType
    confidence: float  # 0.0 - 1.0
    matched_keywords: List[str]
    is_compound: bool = False  # True if query spans multiple intents
    secondary_intents: List[IntentType] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging and API responses."""
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "matched_keywords": self.matched_keywords,
            "is_compound": self.is_compound,
            "secondary_intents": [intent.value for intent in self.secondary_intents]
        }


# --- INTENT KEYWORD PATTERNS (Organized by priority) ---
class IntentPatterns:
    """
    Penny's keyword patterns for intent matching.
    Organized by priority — critical intents checked first.
    """
    
    # 🚨 PRIORITY 1: EMERGENCY & SAFETY (Always check first)
    EMERGENCY = [
        "911", "emergency", "urgent", "crisis", "danger", "help me",
        "suicide", "overdose", "assault", "abuse", "threatening",
        "hurt myself", "hurt someone", "life threatening"
    ]
    
    # 🌍 PRIORITY 2: TRANSLATION (High civic value)
    TRANSLATION = [
        "translate", "in spanish", "in french", "in portuguese", 
        "in german", "in chinese", "in arabic", "in vietnamese",
        "in russian", "in korean", "in japanese", "in tagalog",
        "convert to", "say this in", "how do i say", "what is", "in hindi"
    ]
    
    # 📄 PRIORITY 3: DOCUMENT PROCESSING (Forms, PDFs)
    DOCUMENT_PROCESSING = [
        "process this document", "extract data", "analyze pdf",
        "upload form", "read this file", "scan this", "form help",
        "fill out", "document", "pdf", "application", "permit"
    ]
    
    # 🔍 PRIORITY 4: ANALYSIS TOOLS
    SENTIMENT_ANALYSIS = [
        "how does this sound", "is this positive", "is this negative",
        "analyze", "sentiment", "feel about", "mood", "tone"
    ]
    
    BIAS_DETECTION = [
        "is this biased", "check bias", "check fairness", "is this neutral",
        "biased", "objective", "subjective", "fair", "discriminatory"
    ]
    
    # 🌤️ PRIORITY 5: WEATHER + EVENTS (Compound intent handling)
    WEATHER = [
        "weather", "rain", "snow", "sunny", "forecast", "temperature",
        "hot", "cold", "storm", "wind", "outside", "climate",
        "degrees", "celsius", "fahrenheit"
    ]
    
    # Specific date/time keywords that suggest event context
    DATE_TIME = [
        "today", "tomorrow", "this weekend", "next week",
        "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "tonight", "this morning", "this afternoon", "this evening"
    ]
    
    EVENTS = [
        "event", "things to do", "what's happening", "activities",
        "festival", "concert", "activity", "community event",
        "show", "performance", "gathering", "meetup", "celebration"
    ]
    
    # 🏛️ PRIORITY 6: LOCAL RESOURCES (Core civic mission)
    LOCAL_RESOURCES = [
        "resource", "shelter", "library", "help center",
        "food bank", "warming center", "cooling center", "csb",
        "mental health", "housing", "community service",
        "trash", "recycling", "transit", "bus", "schedule",
        "clinic", "hospital", "pharmacy", "assistance",
        "utility", "water", "electric", "gas", "bill"
    ]
    
    # 💬 PRIORITY 7: CONVERSATIONAL
    GREETING = [
        "hi", "hello", "hey", "what's up", "good morning",
        "good afternoon", "good evening", "howdy", "yo",
        "greetings", "sup", "hiya"
    ]
    
    HELP = [
        "help", "how do i", "can you help", "i need help",
        "what can you do", "how does this work", "instructions",
        "guide", "tutorial", "show me how"
    ]


def classify_intent(message: str) -> str:
    """
    🎯 Main classification function (backward-compatible).
    Returns intent as string for existing API compatibility.
    
    Args:
        message: User's query text
        
    Returns:
        Intent string (e.g., "weather", "events", "translation")
    """
    try:
        result = classify_intent_detailed(message)
        return result.intent.value
    except Exception as e:
        logger.error(f"Intent classification failed: {e}", exc_info=True)
        return IntentType.UNKNOWN.value


def classify_intent_detailed(message: str) -> IntentMatch:
    """
    🧠 Enhanced classification with confidence scores and metadata.
    
    This function:
    1. Checks for emergency keywords FIRST (safety routing)
    2. Detects compound intents (e.g., "weather + events")
    3. Returns structured result with confidence + matched keywords
    
    Args:
        message: User's query text
        
    Returns:
        IntentMatch object with full classification details
    """
    
    if not message or not message.strip():
        logger.warning("Empty message received for intent classification")
        return IntentMatch(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            matched_keywords=[]
        )
    
    try:
        text = message.lower().strip()
        logger.debug(f"Classifying intent for: '{text[:50]}...'")
        
        # --- PRIORITY 1: EMERGENCY (Critical safety routing) ---
        emergency_matches = _find_keyword_matches(text, IntentPatterns.EMERGENCY)
        if emergency_matches:
            logger.warning(f"🚨 EMERGENCY intent detected: {emergency_matches}")
            return IntentMatch(
                intent=IntentType.EMERGENCY,
                confidence=1.0,  # Always high confidence for safety
                matched_keywords=emergency_matches
            )
        
        # --- PRIORITY 2: TRANSLATION ---
        translation_matches = _find_keyword_matches(text, IntentPatterns.TRANSLATION)
        if translation_matches:
            return IntentMatch(
                intent=IntentType.TRANSLATION,
                confidence=0.9,
                matched_keywords=translation_matches
            )
        
        # --- PRIORITY 3: DOCUMENT PROCESSING ---
        doc_matches = _find_keyword_matches(text, IntentPatterns.DOCUMENT_PROCESSING)
        if doc_matches:
            return IntentMatch(
                intent=IntentType.DOCUMENT_PROCESSING,
                confidence=0.9,
                matched_keywords=doc_matches
            )
        
        # --- PRIORITY 4: ANALYSIS TOOLS ---
        sentiment_matches = _find_keyword_matches(text, IntentPatterns.SENTIMENT_ANALYSIS)
        if sentiment_matches:
            return IntentMatch(
                intent=IntentType.SENTIMENT_ANALYSIS,
                confidence=0.85,
                matched_keywords=sentiment_matches
            )
        
        bias_matches = _find_keyword_matches(text, IntentPatterns.BIAS_DETECTION)
        if bias_matches:
            return IntentMatch(
                intent=IntentType.BIAS_DETECTION,
                confidence=0.85,
                matched_keywords=bias_matches
            )
        
        # --- PRIORITY 5: COMPOUND INTENT HANDLING (Weather + Events) ---
        weather_matches = _find_keyword_matches(text, IntentPatterns.WEATHER)
        event_matches = _find_keyword_matches(text, IntentPatterns.EVENTS)
        date_matches = _find_keyword_matches(text, IntentPatterns.DATE_TIME)
        
        # Compound detection: "What events are happening this weekend?"
        # or "What's the weather like for Sunday's festival?"
        if event_matches and (weather_matches or date_matches):
            logger.info("Compound intent detected: events + weather/date")
            return IntentMatch(
                intent=IntentType.EVENTS,  # Primary intent
                confidence=0.85,
                matched_keywords=event_matches + weather_matches + date_matches,
                is_compound=True,
                secondary_intents=[IntentType.WEATHER]
            )
        
        # --- PRIORITY 6: SIMPLE WEATHER INTENT ---
        if weather_matches:
            return IntentMatch(
                intent=IntentType.WEATHER,
                confidence=0.9,
                matched_keywords=weather_matches
            )
        
        # --- PRIORITY 7: LOCAL RESOURCES ---
        resource_matches = _find_keyword_matches(text, IntentPatterns.LOCAL_RESOURCES)
        if resource_matches:
            return IntentMatch(
                intent=IntentType.LOCAL_RESOURCES,
                confidence=0.9,
                matched_keywords=resource_matches
            )
        
        # --- PRIORITY 8: EVENTS (Simple check) ---
        if event_matches:
            return IntentMatch(
                intent=IntentType.EVENTS,
                confidence=0.85,
                matched_keywords=event_matches
            )
        
        # --- PRIORITY 9: CONVERSATIONAL ---
        greeting_matches = _find_keyword_matches(text, IntentPatterns.GREETING)
        if greeting_matches:
            return IntentMatch(
                intent=IntentType.GREETING,
                confidence=0.8,
                matched_keywords=greeting_matches
            )
        
        help_matches = _find_keyword_matches(text, IntentPatterns.HELP)
        if help_matches:
            return IntentMatch(
                intent=IntentType.HELP,
                confidence=0.9,
                matched_keywords=help_matches
            )
        
        # --- FALLBACK: UNKNOWN ---
        logger.info(f"No clear intent match for: '{text[:50]}...'")
        return IntentMatch(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            matched_keywords=[]
        )
        
    except Exception as e:
        logger.error(f"Error during intent classification: {e}", exc_info=True)
        return IntentMatch(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            matched_keywords=[],
        )


# --- HELPER FUNCTIONS ---

def _find_keyword_matches(text: str, keywords: List[str]) -> List[str]:
    """
    Finds which keywords from a pattern list appear in the user's message.
    
    Args:
        text: Normalized user message (lowercase)
        keywords: List of keywords to search for
        
    Returns:
        List of matched keywords (for debugging/logging)
    """
    try:
        matches = []
        for keyword in keywords:
            if keyword in text:
                matches.append(keyword)
        return matches
    except Exception as e:
        logger.error(f"Error finding keyword matches: {e}", exc_info=True)
        return []


def get_intent_description(intent: IntentType) -> str:
    """
    🗣️ Penny's plain-English explanation of what each intent does.
    Useful for help systems and debugging.
    
    Args:
        intent: IntentType enum value
        
    Returns:
        Human-readable description of the intent
    """
    descriptions = {
        IntentType.WEATHER: "Get current weather conditions and forecasts for your area",
        IntentType.GREETING: "Start a conversation with Penny",
        IntentType.LOCAL_RESOURCES: "Find community resources like shelters, libraries, and services",
        IntentType.EVENTS: "Discover local events and activities happening in your city",
        IntentType.TRANSLATION: "Translate text between 27 languages",
        IntentType.SENTIMENT_ANALYSIS: "Analyze the emotional tone of text",
        IntentType.BIAS_DETECTION: "Check text for potential bias or fairness issues",
        IntentType.DOCUMENT_PROCESSING: "Process PDFs and forms to extract information",
        IntentType.HELP: "Learn how to use Penny's features",
        IntentType.EMERGENCY: "Connect with emergency services and crisis support",
        IntentType.UNKNOWN: "I'm not sure what you're asking — can you rephrase?"
    }
    return descriptions.get(intent, "Unknown intent type")


def get_all_supported_intents() -> Dict[str, str]:
    """
    📋 Returns all supported intents with descriptions.
    Useful for /help endpoints and documentation.
    
    Returns:
        Dictionary mapping intent values to descriptions
    """
    try:
        return {
            intent.value: get_intent_description(intent)
            for intent in IntentType
            if intent != IntentType.UNKNOWN
        }
    except Exception as e:
        logger.error(f"Error getting supported intents: {e}", exc_info=True)
        return {}


# --- FUTURE ML UPGRADE HOOK ---
def classify_intent_ml(message: str, use_embedding_model: bool = False) -> IntentMatch:
    """
    🔮 PLACEHOLDER for future ML-based classification.
    
    When ready to upgrade from keyword matching to embeddings:
    1. Load Gemma-7B or sentence-transformers model
    2. Generate message embeddings
    3. Compare to intent prototype embeddings
    4. Return top match with confidence score
    
    Args:
        message: User's query
        use_embedding_model: If True, use ML model (not implemented yet)
        
    Returns:
        IntentMatch object (currently falls back to rule-based)
    """
    
    if use_embedding_model:
        logger.warning("ML-based classification not yet implemented. Falling back to rules.")
    
    # Fallback to rule-based for now
    return classify_intent_detailed(message)


# --- TESTING & VALIDATION ---
def validate_intent_patterns() -> Dict[str, List[str]]:
    """
    🧪 Validates that all intent patterns are properly configured.
    Returns any overlapping keywords that might cause conflicts.
    
    Returns:
        Dictionary of overlapping keywords between intent pairs
    """
    try:
        all_patterns = {
            "emergency": IntentPatterns.EMERGENCY,
            "translation": IntentPatterns.TRANSLATION,
            "document": IntentPatterns.DOCUMENT_PROCESSING,
            "sentiment": IntentPatterns.SENTIMENT_ANALYSIS,
            "bias": IntentPatterns.BIAS_DETECTION,
            "weather": IntentPatterns.WEATHER,
            "events": IntentPatterns.EVENTS,
            "resources": IntentPatterns.LOCAL_RESOURCES,
            "greeting": IntentPatterns.GREETING,
            "help": IntentPatterns.HELP
        }
        
        overlaps = {}
        
        # Check for keyword overlap between different intents
        for intent1, keywords1 in all_patterns.items():
            for intent2, keywords2 in all_patterns.items():
                if intent1 >= intent2:  # Avoid duplicate comparisons
                    continue
                
                overlap = set(keywords1) & set(keywords2)
                if overlap:
                    key = f"{intent1}_vs_{intent2}"
                    overlaps[key] = list(overlap)
        
        if overlaps:
            logger.warning(f"Found keyword overlaps between intents: {overlaps}")
        
        return overlaps
        
    except Exception as e:
        logger.error(f"Error validating intent patterns: {e}", exc_info=True)
        return {}


# --- LOGGING SAMPLE CLASSIFICATIONS (For monitoring) ---
def log_intent_classification(message: str, result: IntentMatch) -> None:
    """
    📊 Logs classification results for Azure Application Insights.
    Helps track intent distribution and confidence patterns.
    
    Args:
        message: Original user message (truncated for PII safety)
        result: IntentMatch classification result
    """
    try:
        # Truncate message for PII safety
        safe_message = message[:50] + "..." if len(message) > 50 else message
        
        logger.info(
            f"Intent classified | "
            f"intent={result.intent.value} | "
            f"confidence={result.confidence:.2f} | "
            f"compound={result.is_compound} | "
            f"keywords={result.matched_keywords[:5]} | "  # Limit logged keywords
            f"message_preview='{safe_message}'"
        )
    except Exception as e:
        logger.error(f"Error logging intent classification: {e}", exc_info=True)