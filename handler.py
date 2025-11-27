# handler.py
"""
Hugging Face Inference Endpoint Handler for PENNY
"""
import asyncio
from app.orchestrator import run_orchestrator
from typing import Dict, Any
import json

class EndpointHandler:
    def __init__(self, path=""):
        """Initialize PENNY orchestrator when endpoint starts"""
        print("🤖 Initializing PENNY...")
        print("✅ PENNY ready!")
    
    def __call__(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle inference requests from Hugging Face
        
        Args:
            data: Dictionary with 'inputs', 'tenant_id', 'user_id', 'session_id'
        
        Returns:
            Dictionary with 'reply', 'intent', 'confidence', etc.
        """
        # Extract inputs
        inputs = data.get("inputs", "")
        tenant_id = data.get("tenant_id", "default")
        user_id = data.get("user_id", "anonymous")
        session_id = data.get("session_id", None)
        
        # Build context
        context = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id
        }
        
        # Process through orchestrator (async function)
        try:
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                run_orchestrator(inputs, context)
            )
            loop.close()
            
            # Return in expected format
            return {
                "reply": response.get("reply", "I'm having trouble right now. Please try again! 💛"),
                "intent": response.get("intent", "unknown"),
                "confidence": response.get("confidence", 0.0),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "response_time_ms": response.get("response_time_ms", 0),
                "success": response.get("success", False)
            }
        except Exception as e:
            return {
                "reply": f"I'm having trouble processing that right now. Error: {str(e)}",
                "intent": "error",
                "confidence": 0.0,
                "error": str(e),
                "success": False
            }