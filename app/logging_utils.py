# app/logging_utils.py
"""
📊 Penny's Logging & Analytics System
Tracks user interactions, system performance, and civic engagement patterns.

MISSION: Create an audit trail that helps improve Penny's service while
respecting user privacy and meeting compliance requirements.

FEATURES:
- Structured JSON logging for Azure Application Insights
- Daily log rotation for long-term storage
- Privacy-safe request/response tracking
- Performance monitoring
- Error tracking with context
- Optional Azure Blob Storage integration
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

# --- LOGGING SETUP ---
logger = logging.getLogger(__name__)

# ============================================================
# LOG PATH CONFIGURATION (Environment-aware)
# ============================================================

# Base directories (use pathlib for OS compatibility)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LOGS_BASE_DIR = PROJECT_ROOT / "data" / "logs"
DEFAULT_LOG_PATH = LOGS_BASE_DIR / "penny_combined.jsonl"

# Environment-configurable log path
LOG_PATH = Path(os.getenv("PENNY_LOG_PATH", str(DEFAULT_LOG_PATH)))

# Ensure log directory exists on import
LOGS_BASE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOG LEVEL ENUM (For categorizing log entries)
# ============================================================

class LogLevel(str, Enum):
    """
    Categorizes the importance/type of log entries.
    Maps to Azure Application Insights severity levels.
    """
    DEBUG = "debug"           # Detailed diagnostic info
    INFO = "info"             # General informational messages
    WARNING = "warning"       # Potential issues
    ERROR = "error"           # Error events
    CRITICAL = "critical"     # Critical failures
    AUDIT = "audit"           # Compliance/audit trail


class InteractionType(str, Enum):
    """
    Categorizes the type of user interaction.
    Helps track which features residents use most.
    """
    QUERY = "query"                    # General question
    RESOURCE_LOOKUP = "resource_lookup"  # Finding civic resources
    TRANSLATION = "translation"        # Language translation
    EVENT_SEARCH = "event_search"      # Looking for events
    WEATHER = "weather"                # Weather inquiry
    DOCUMENT = "document_processing"   # PDF/form processing
    EMERGENCY = "emergency"            # Crisis/emergency routing
    GREETING = "greeting"              # Conversational greeting
    HELP = "help"                      # Help request
    UNKNOWN = "unknown"                # Unclassified


# ============================================================
# STRUCTURED LOG ENTRY (Type-safe logging)
# ============================================================

@dataclass
class PennyLogEntry:
    """
    📋 Structured log entry for Penny interactions.
    
    This format is:
    - Azure Application Insights compatible
    - Privacy-safe (no PII unless explicitly needed)
    - Analytics-ready
    - Compliance-friendly
    """
    # Timestamp
    timestamp: str
    
    # Request Context
    input: str
    input_length: int
    tenant_id: str
    user_role: str
    interaction_type: InteractionType
    
    # Response Context
    intent: str
    tool_used: Optional[str]
    model_id: Optional[str]
    response_summary: str
    response_length: int
    response_time_ms: Optional[float]
    
    # Technical Context
    log_level: LogLevel
    success: bool
    error_message: Optional[str] = None
    
    # Location Context (Optional)
    lat: Optional[float] = None
    lon: Optional[float] = None
    location_detected: Optional[str] = None
    
    # Privacy & Compliance
    session_id: Optional[str] = None  # Hashed session identifier
    contains_pii: bool = False
    
    # Performance Metrics
    tokens_used: Optional[int] = None
    cache_hit: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary for JSON serialization."""
        return {k: v.value if isinstance(v, Enum) else v 
                for k, v in asdict(self).items()}


# ============================================================
# DAILY LOG ROTATION
# ============================================================

def get_daily_log_path() -> Path:
    """
    🗓️ Returns a daily unique path for log rotation.
    
    Creates files like:
        data/logs/2025-02-01.jsonl
        data/logs/2025-02-02.jsonl
    
    This helps with:
    - Log management (archive old logs)
    - Azure Blob Storage uploads (one file per day)
    - Performance (smaller files)
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_path = LOGS_BASE_DIR / f"{date_str}.jsonl"
    
    # Ensure directory exists
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    
    return daily_path


# ============================================================
# MAIN LOGGING FUNCTION (Enhanced)
# ============================================================

def log_request(
    payload: Dict[str, Any],
    response: Dict[str, Any],
    rotate_daily: bool = True,
    log_level: LogLevel = LogLevel.INFO
) -> None:
    """
    📝 Logs a user interaction with Penny.
    
    This is the primary logging function called by router.py after
    processing each request. It creates a structured, privacy-safe
    record of the interaction.
    
    Args:
        payload: Incoming request data from router.py
        response: Final response dictionary from orchestrator
        rotate_daily: If True, uses daily log files
        log_level: Severity level for this log entry
    
    Example:
        log_request(
            payload={"input": "What's the weather?", "tenant_id": "atlanta_ga"},
            response={"intent": "weather", "response": "..."}
        )
    """
    
    try:
        # --- Extract Core Fields ---
        user_input = payload.get("input", "")
        tenant_id = payload.get("tenant_id", "unknown")
        user_role = payload.get("role", "resident")
        
        # --- Determine Interaction Type ---
        intent = response.get("intent", "unknown")
        interaction_type = _classify_interaction(intent)
        
        # --- Privacy: Hash Session ID (if provided) ---
        session_id = payload.get("session_id")
        if session_id:
            session_id = _hash_identifier(session_id)
        
        # --- Detect PII (Simple check - can be enhanced) ---
        contains_pii = _check_for_pii(user_input)
        
        # --- Create Structured Log Entry ---
        log_entry = PennyLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            input=_sanitize_input(user_input, contains_pii),
            input_length=len(user_input),
            tenant_id=tenant_id,
            user_role=user_role,
            interaction_type=interaction_type,
            intent=intent,
            tool_used=response.get("tool", "none"),
            model_id=response.get("model_id"),
            response_summary=_summarize_response(response.get("response")),
            response_length=len(str(response.get("response", ""))),
            response_time_ms=response.get("response_time_ms"),
            log_level=log_level,
            success=response.get("success", True),
            error_message=response.get("error"),
            lat=payload.get("lat"),
            lon=payload.get("lon"),
            location_detected=response.get("location_detected"),
            session_id=session_id,
            contains_pii=contains_pii,
            tokens_used=response.get("tokens_used"),
            cache_hit=response.get("cache_hit", False)
        )
        
        # --- Write to File ---
        log_path = get_daily_log_path() if rotate_daily else LOG_PATH
        _write_log_entry(log_path, log_entry)
        
        # --- Optional: Send to Azure (if enabled) ---
        if os.getenv("AZURE_LOGS_ENABLED", "false").lower() == "true":
            _send_to_azure(log_entry)
        
        # --- Log to console (for Azure Application Insights) ---
        logger.info(
            f"Request logged | "
            f"tenant={tenant_id} | "
            f"intent={intent} | "
            f"interaction={interaction_type.value} | "
            f"success={log_entry.success}"
        )
        
    except Exception as e:
        # Failsafe: Never let logging failures crash the application
        logger.error(f"Failed to log request: {e}", exc_info=True)
        _emergency_log(payload, response, str(e))


# ============================================================
# LOG WRITING (With error handling)
# ============================================================

def _write_log_entry(log_path: Path, log_entry: PennyLogEntry) -> None:
    """
    📁 Writes log entry to JSONL file.
    Handles file I/O errors gracefully.
    """
    try:
        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write as JSON Lines (append mode)
        with open(log_path, "a", encoding="utf-8") as f:
            json_str = json.dumps(log_entry.to_dict(), ensure_ascii=False)
            f.write(json_str + "\n")
            
    except IOError as e:
        logger.error(f"Failed to write to log file {log_path}: {e}")
        _emergency_log_to_console(log_entry)
    except Exception as e:
        logger.error(f"Unexpected error writing log: {e}", exc_info=True)
        _emergency_log_to_console(log_entry)


def _emergency_log_to_console(log_entry: PennyLogEntry) -> None:
    """
    🚨 Emergency fallback: Print log to console if file writing fails.
    Azure Application Insights will capture console output.
    """
    print(f"[EMERGENCY LOG] {json.dumps(log_entry.to_dict())}")


def _emergency_log(payload: Dict, response: Dict, error: str) -> None:
    """
    🚨 Absolute fallback for when structured logging fails entirely.
    """
    emergency_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "CRITICAL",
        "message": "Logging system failure",
        "error": error,
        "input_preview": str(payload.get("input", ""))[:100],
        "response_preview": str(response.get("response", ""))[:100]
    }
    print(f"[LOGGING FAILURE] {json.dumps(emergency_entry)}")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _classify_interaction(intent: str) -> InteractionType:
    """
    🏷️ Maps intent to interaction type for analytics.
    """
    intent_mapping = {
        "weather": InteractionType.WEATHER,
        "events": InteractionType.EVENT_SEARCH,
        "local_resources": InteractionType.RESOURCE_LOOKUP,
        "translation": InteractionType.TRANSLATION,
        "document_processing": InteractionType.DOCUMENT,
        "emergency": InteractionType.EMERGENCY,
        "greeting": InteractionType.GREETING,
        "help": InteractionType.HELP,
    }
    return intent_mapping.get(intent.lower(), InteractionType.UNKNOWN)


def _summarize_response(resp: Optional[Any]) -> str:
    """
    ✂️ Creates a truncated summary of the response for logging.
    Prevents log files from becoming bloated with full responses.
    """
    if resp is None:
        return "No response content"
    
    if isinstance(resp, dict):
        # Try to extract the most meaningful part
        summary = (
            resp.get("response") or
            resp.get("summary") or
            resp.get("message") or
            str(resp)
        )
        return str(summary)[:250]
    
    return str(resp)[:250]


def _hash_identifier(identifier: str) -> str:
    """
    🔒 Creates a privacy-safe hash of identifiers (session IDs, user IDs).
    
    Uses SHA256 for one-way hashing. This allows:
    - Session tracking without storing raw IDs
    - Privacy compliance (GDPR, CCPA)
    - Anonymized analytics
    """
    return hashlib.sha256(identifier.encode()).hexdigest()[:16]


def _check_for_pii(text: str) -> bool:
    """
    🔍 Simple PII detection (can be enhanced with NER models).
    
    Checks for common PII patterns:
    - Social Security Numbers
    - Email addresses
    - Phone numbers
    
    Returns True if potential PII detected.
    """
    import re
    
    # SSN pattern: XXX-XX-XXXX
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Phone pattern: various formats
    phone_pattern = r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'
    
    patterns = [ssn_pattern, email_pattern, phone_pattern]
    
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    
    return False


def _sanitize_input(text: str, contains_pii: bool) -> str:
    """
    🧹 Sanitizes user input for logging.
    
    If PII detected:
    - Masks the input for privacy
    - Keeps first/last few characters for debugging
    
    Args:
        text: Original user input
        contains_pii: Whether PII was detected
        
    Returns:
        Sanitized text safe for logging
    """
    if not contains_pii:
        return text
    
    # Mask middle portion if PII detected
    if len(text) <= 20:
        return "[PII_DETECTED]"
    
    # Keep first 10 and last 10 chars, mask middle
    return f"{text[:10]}...[PII_MASKED]...{text[-10:]}"


# ============================================================
# AZURE INTEGRATION (Placeholder for future)
# ============================================================

def _send_to_azure(log_entry: PennyLogEntry) -> None:
    """
    ☁️ Sends log entry to Azure services.
    
    Options:
    1. Azure Application Insights (custom events)
    2. Azure Blob Storage (long-term archival)
    3. Azure Table Storage (queryable logs)
    
    TODO: Implement when Azure integration is ready
    """
    try:
        # Example: Send to Application Insights
        # from applicationinsights import TelemetryClient
        # tc = TelemetryClient(os.getenv("APPINSIGHTS_INSTRUMENTATION_KEY"))
        # tc.track_event(
        #     "PennyInteraction",
        #     properties=log_entry.to_dict()
        # )
        # tc.flush()
        
        logger.debug("Azure logging not yet implemented")
        
    except Exception as e:
        logger.error(f"Failed to send log to Azure: {e}")
        # Don't raise - logging failures should never crash the app


# ============================================================
# LOG ANALYSIS UTILITIES
# ============================================================

def get_logs_for_date(date: str) -> List[Dict[str, Any]]:
    """
    📊 Retrieves all log entries for a specific date.
    
    Args:
        date: Date string in YYYY-MM-DD format
        
    Returns:
        List of log entry dictionaries
        
    Example:
        logs = get_logs_for_date("2025-02-01")
    """
    log_file = LOGS_BASE_DIR / f"{date}.jsonl"
    
    if not log_file.exists():
        logger.warning(f"No logs found for date: {date}")
        return []
    
    logs = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
    except Exception as e:
        logger.error(f"Error reading logs for {date}: {e}")
    
    return logs


def get_interaction_stats(date: str) -> Dict[str, Any]:
    """
    📈 Generates usage statistics for a given date.
    
    Returns metrics like:
    - Total interactions
    - Interactions by type
    - Average response time
    - Success rate
    - Most common intents
    
    Args:
        date: Date string in YYYY-MM-DD format
        
    Returns:
        Statistics dictionary
    """
    logs = get_logs_for_date(date)
    
    if not logs:
        return {"error": "No logs found for date", "date": date}
    
    # Calculate statistics
    total = len(logs)
    successful = sum(1 for log in logs if log.get("success", False))
    
    # Response time statistics
    response_times = [
        log["response_time_ms"] 
        for log in logs 
        if log.get("response_time_ms") is not None
    ]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    # Interaction type breakdown
    interaction_counts = {}
    for log in logs:
        itype = log.get("interaction_type", "unknown")
        interaction_counts[itype] = interaction_counts.get(itype, 0) + 1
    
    # Intent breakdown
    intent_counts = {}
    for log in logs:
        intent = log.get("intent", "unknown")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    
    return {
        "date": date,
        "total_interactions": total,
        "successful_interactions": successful,
        "success_rate": f"{(successful/total*100):.1f}%",
        "avg_response_time_ms": round(avg_response_time, 2),
        "interactions_by_type": interaction_counts,
        "top_intents": dict(sorted(
            intent_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5])
    }


# ============================================================
# LOG CLEANUP (For maintenance)
# ============================================================

def cleanup_old_logs(days_to_keep: int = 90) -> int:
    """
    🧹 Removes log files older than specified days.
    
    Args:
        days_to_keep: Number of days to retain logs
        
    Returns:
        Number of files deleted
        
    Example:
        # Delete logs older than 90 days
        deleted = cleanup_old_logs(90)
    """
    from datetime import timedelta
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    deleted_count = 0
    
    try:
        for log_file in LOGS_BASE_DIR.glob("*.jsonl"):
            try:
                # Parse date from filename (YYYY-MM-DD.jsonl)
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                
                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old log file: {log_file.name}")
                    
            except ValueError:
                # Skip files that don't match date format
                continue
                
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")
    
    logger.info(f"Log cleanup complete: {deleted_count} files deleted")
    return deleted_count


# ============================================================
# PUBLIC API FUNCTIONS (Used by other modules)
# ============================================================

def log_interaction(
    tenant_id: Optional[str] = None,
    interaction_type: Optional[str] = None,
    intent: Optional[str] = None,
    response_time_ms: Optional[float] = None,
    success: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    📝 Simplified logging function used throughout Penny's codebase.
    
    This is the main logging function called by orchestrator, router, agents, and model utils.
    It creates a structured log entry and writes it to the log file.
    
    Args:
        tenant_id: City/location identifier (optional)
        interaction_type: Type of interaction (e.g., "weather", "events", "orchestration") (optional)
        intent: Detected intent (e.g., "weather", "emergency") (optional)
        response_time_ms: Response time in milliseconds (optional)
        success: Whether the operation succeeded (optional)
        metadata: Optional additional metadata dictionary
        **kwargs: Additional fields to include in log entry (e.g., error, details, fallback_used)
        
    Example:
        log_interaction(
            tenant_id="atlanta_ga",
            interaction_type="weather",
            intent="weather",
            response_time_ms=150.5,
            success=True,
            metadata={"temperature": 72, "condition": "sunny"}
        )
        
        # Or with keyword arguments:
        log_interaction(
            intent="translation_initialization",
            success=False,
            error="model_loader unavailable"
        )
    """
    try:
        # Build log entry dictionary from provided parameters
        log_entry_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add standard fields if provided
        if tenant_id is not None:
            log_entry_dict["tenant_id"] = sanitize_for_logging(tenant_id)
        if interaction_type is not None:
            log_entry_dict["interaction_type"] = interaction_type
        if intent is not None:
            log_entry_dict["intent"] = intent
        if response_time_ms is not None:
            log_entry_dict["response_time_ms"] = round(response_time_ms, 2)
        if success is not None:
            log_entry_dict["success"] = success
        
        # Add metadata if provided
        if metadata:
            # Sanitize metadata values
            sanitized_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, str):
                    sanitized_metadata[key] = sanitize_for_logging(value)
                else:
                    sanitized_metadata[key] = value
            log_entry_dict["metadata"] = sanitized_metadata
        
        # Add any additional kwargs (for backward compatibility with model utils)
        for key, value in kwargs.items():
            if key not in log_entry_dict:  # Don't overwrite standard fields
                if isinstance(value, str):
                    log_entry_dict[key] = sanitize_for_logging(value)
                else:
                    log_entry_dict[key] = value
        
        # Write to log file
        log_path = get_daily_log_path()
        _write_log_entry_dict(log_path, log_entry_dict)
        
    except Exception as e:
        # Failsafe: Never let logging failures crash the application
        logger.error(f"Failed to log interaction: {e}", exc_info=True)
        _emergency_log_to_console_dict(log_entry_dict if 'log_entry_dict' in locals() else {})


def sanitize_for_logging(text: str) -> str:
    """
    🧹 Sanitizes text for safe logging (removes PII).
    
    This function is used throughout Penny to ensure sensitive information
    is not logged. It checks for PII and masks it appropriately.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text safe for logging
        
    Example:
        safe_text = sanitize_for_logging("My email is user@example.com")
        # Returns: "My email is [PII_DETECTED]"
    """
    if not text or not isinstance(text, str):
        return str(text) if text else ""
    
    # Check for PII
    contains_pii = _check_for_pii(text)
    
    if contains_pii:
        # Mask PII
        if len(text) <= 20:
            return "[PII_DETECTED]"
        return f"{text[:10]}...[PII_MASKED]...{text[-10:]}"
    
    return text


def _write_log_entry_dict(log_path: Path, log_entry_dict: Dict[str, Any]) -> None:
    """
    📁 Writes log entry dictionary to JSONL file.
    Helper function for simplified logging.
    """
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            json_str = json.dumps(log_entry_dict, ensure_ascii=False)
            f.write(json_str + "\n")
    except Exception as e:
        logger.error(f"Failed to write log entry: {e}")
        _emergency_log_to_console_dict(log_entry_dict)


def _emergency_log_to_console_dict(log_entry_dict: Dict[str, Any]) -> None:
    """
    🚨 Emergency fallback: Print log to console if file writing fails.
    """
    print(f"[EMERGENCY LOG] {json.dumps(log_entry_dict)}")


# ============================================================
# INITIALIZATION
# ============================================================

def initialize_logging_system() -> bool:
    """
    🚀 Initializes the logging system.
    Should be called during app startup.
    
    Returns:
        True if initialization successful
    """
    logger.info("📊 Initializing Penny's logging system...")
    
    try:
        # Ensure log directory exists
        LOGS_BASE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        test_file = LOGS_BASE_DIR / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        
        logger.info(f"✅ Logging system initialized")
        logger.info(f"📁 Log directory: {LOGS_BASE_DIR}")
        logger.info(f"🔄 Daily rotation: Enabled")
        
        # Log Azure status
        if os.getenv("AZURE_LOGS_ENABLED") == "true":
            logger.info("☁️ Azure logging: Enabled")
        else:
            logger.info("💾 Azure logging: Disabled (local only)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize logging system: {e}")
        return False