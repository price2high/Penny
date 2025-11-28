# models/gemma/gemma_utils.py

"""
Gemma Model Utilities for PENNY Project
Handles text generation using the Gemma-based core language model via Hugging Face Inference API.
Provides async generation with structured error handling and logging.
"""

import os
import asyncio
import time
import httpx
from typing import Dict, Any, Optional

# --- Logging Imports ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- Configuration ---
HF_API_URL = "https://api-inference.huggingface.co/models/google/gemma-7b-it"
DEFAULT_TIMEOUT = 30.0  # Gemma can take longer to respond
MAX_RETRIES = 2
AGENT_NAME = "penny-core-agent"


def is_gemma_available() -> bool:
    """
    Check if Gemma service is available.
    
    Returns:
        bool: True if HF_TOKEN is configured.
    """
    return bool(os.getenv("HF_TOKEN"))


async def generate_response(
    prompt: str,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs text generation using Gemma via Hugging Face Inference API.

    Args:
        prompt: The conversational or instruction prompt.
        max_new_tokens: The maximum number of tokens to generate (default: 256).
        temperature: Controls randomness in generation (default: 0.7).
        tenant_id: Optional tenant identifier for logging.

    Returns:
        A dictionary containing:
            - response (str): The generated text
            - available (bool): Whether the service was available
            - error (str, optional): Error message if generation failed
            - response_time_ms (int, optional): Generation time in milliseconds
    """
    start_time = time.time()
    
    # Check API token availability
    HF_TOKEN = os.getenv("HF_TOKEN")
    if not HF_TOKEN:
        log_interaction(
            intent="gemma_generate",
            tenant_id=tenant_id,
            success=False,
            error="HF_TOKEN not configured",
            fallback_used=True
        )
        return {
            "response": "I'm having trouble accessing my language model right now. Please try again in a moment!",
            "available": False,
            "error": "HF_TOKEN not configured"
        }

    # Validate inputs
    if not prompt or not isinstance(prompt, str):
        log_interaction(
            intent="gemma_generate",
            tenant_id=tenant_id,
            success=False,
            error="Invalid prompt provided"
        )
        return {
            "response": "I didn't receive a valid prompt. Could you try again?",
            "available": True,
            "error": "Invalid input"
        }

    # Configure generation parameters
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "do_sample": True if temperature > 0.0 else False,
            "return_full_text": False
        }
    }
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    # Retry logic for API calls
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(HF_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Parse response
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get("generated_text", "").strip()
                
                # Log slow responses
                if response_time_ms > 5000:
                    log_interaction(
                        intent="gemma_generate_slow",
                        tenant_id=tenant_id,
                        success=True,
                        response_time_ms=response_time_ms,
                        details="Slow generation detected"
                    )
                
                log_interaction(
                    intent="gemma_generate",
                    tenant_id=tenant_id,
                    success=True,
                    response_time_ms=response_time_ms,
                    prompt_preview=sanitize_for_logging(prompt[:100])
                )
                
                return {
                    "response": generated_text,
                    "available": True,
                    "response_time_ms": response_time_ms
                }
            
            # Unexpected output format
            log_interaction(
                intent="gemma_generate",
                tenant_id=tenant_id,
                success=False,
                error="Unexpected API response format",
                response_time_ms=response_time_ms
            )
            
            return {
                "response": "I got an unexpected response from my language model. Let me try to help you another way!",
                "available": True,
                "error": "Unexpected output format"
            }
        
        except httpx.TimeoutException:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)  # Wait before retry
                continue
            
            response_time_ms = int((time.time() - start_time) * 1000)
            log_interaction(
                intent="gemma_generate",
                tenant_id=tenant_id,
                success=False,
                error="API timeout after retries",
                response_time_ms=response_time_ms
            )
            
            return {
                "response": "I'm taking too long to respond. Please try again!",
                "available": False,
                "error": "Timeout",
                "response_time_ms": response_time_ms
            }
        
        except httpx.HTTPStatusError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            log_interaction(
                intent="gemma_generate",
                tenant_id=tenant_id,
                success=False,
                error=f"HTTP {e.response.status_code}",
                response_time_ms=response_time_ms
            )
            
            return {
                "response": "I'm having trouble generating a response right now. Please try again!",
                "available": False,
                "error": f"HTTP {e.response.status_code}",
                "response_time_ms": response_time_ms
            }
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)
                continue
            
            response_time_ms = int((time.time() - start_time) * 1000)
            log_interaction(
                intent="gemma_generate",
                tenant_id=tenant_id,
                success=False,
                error=str(e),
                response_time_ms=response_time_ms,
                fallback_used=True
            )
            
            return {
                "response": "I'm having trouble generating a response right now. Please try again!",
                "available": False,
                "error": str(e),
                "response_time_ms": response_time_ms
            }