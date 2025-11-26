"""
Azure ML Scoring Script for PENNY Main Application
Entry point for Azure ML endpoint deployment
"""

import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Import Penny's main application
try:
    from app.main import app
    from app.orchestrator import run_orchestrator
    APP_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import Penny application: {e}")
    APP_AVAILABLE = False


def init() -> None:
    """
    Initialize the Penny application.
    Called once when the scoring service starts.
    """
    if not APP_AVAILABLE:
        raise RuntimeError("Penny application not available - check imports")
    
    logger.info("Penny application initialized successfully")
    logger.info("Ready to process civic engagement requests")


def run(raw_data: str) -> str:
    """
    Execute Penny's orchestration pipeline on input request.
    
    Args:
        raw_data: JSON string containing request payload
        
    Returns:
        JSON string with Penny's response
        
    Expected input format:
        {
            "message": "User's question or request",
            "tenant_id": "atlanta_ga",  # Optional
            "lat": 33.7490,  # Optional
            "lon": -84.3880,  # Optional
            "role": "resident"  # Optional
        }
        
    Output format:
        {
            "intent": str,
            "reply": str,
            "success": bool,
            "tenant_id": str,
            "model_id": str,
            "response_time_ms": float,
            "confidence": float
        }
    """
    import asyncio
    
    try:
        # Parse input
        try:
            body = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON input: {str(e)}")
            return json.dumps({
                "error": "Invalid JSON format",
                "success": False,
                "reply": "I received invalid data. Please check your request format."
            })
        
        # Extract message (required)
        message = body.get("message", "").strip()
        if not message:
            logger.warning("Empty message provided")
            return json.dumps({
                "error": "No message provided",
                "success": False,
                "reply": "I didn't receive a message. What can I help you with?"
            })
        
        # Build context
        context = {
            "tenant_id": body.get("tenant_id"),
            "lat": body.get("lat"),
            "lon": body.get("lon"),
            "role": body.get("role", "resident")
        }
        
        # Run orchestrator
        result = asyncio.run(run_orchestrator(message, context))
        
        logger.info(f"Request processed: intent={result.get('intent')}, success={result.get('success')}")
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error during request processing: {str(e)}", exc_info=True)
        return json.dumps({
            "error": f"Processing failed: {str(e)}",
            "success": False,
            "reply": "I'm having trouble processing that right now. Please try again! 💛"
        })

