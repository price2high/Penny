# models/gemma/gemma_utils.py

"""
Gemma Model Utilities for PENNY Project
Handles text generation using the Gemma-based core language model pipeline.
Provides async generation with structured error handling and logging.
"""

import asyncio
import time
from typing import Dict, Any, Optional

# --- Logging Imports ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- Model Loader Import ---
try:
    from app.model_loader import load_model_pipeline
    MODEL_LOADER_AVAILABLE = True
except ImportError:
    MODEL_LOADER_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning("Could not import load_model_pipeline. Gemma service unavailable.")

# Global variable to store the loaded pipeline for re-use
GEMMA_PIPELINE: Optional[Any] = None
AGENT_NAME = "penny-core-agent"
INITIALIZATION_ATTEMPTED = False


def _initialize_gemma_pipeline() -> bool:
    """
    Initializes the Gemma pipeline only once.
    
    Returns:
        bool: True if initialization succeeded, False otherwise.
    """
    global GEMMA_PIPELINE, INITIALIZATION_ATTEMPTED
    
    if INITIALIZATION_ATTEMPTED:
        return GEMMA_PIPELINE is not None
    
    INITIALIZATION_ATTEMPTED = True
    
    if not MODEL_LOADER_AVAILABLE:
        log_interaction(
            intent="gemma_initialization",
            success=False,
            error="model_loader unavailable"
        )
        return False
    
    try:
        log_interaction(
            intent="gemma_initialization",
            success=None,
            details=f"Loading {AGENT_NAME}"
        )
        
        GEMMA_PIPELINE = load_model_pipeline(AGENT_NAME)
        
        if GEMMA_PIPELINE is None:
            log_interaction(
                intent="gemma_initialization",
                success=False,
                error="Pipeline returned None"
            )
            return False
        
        log_interaction(
            intent="gemma_initialization",
            success=True,
            details=f"Model {AGENT_NAME} loaded successfully"
        )
        return True
        
    except Exception as e:
        log_interaction(
            intent="gemma_initialization",
            success=False,
            error=str(e)
        )
        return False


# Attempt initialization at module load
_initialize_gemma_pipeline()


def is_gemma_available() -> bool:
    """
    Check if Gemma service is available.
    
    Returns:
        bool: True if Gemma pipeline is loaded and ready.
    """
    return GEMMA_PIPELINE is not None


async def generate_response(
    prompt: str,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs text generation using the loaded Gemma pipeline.

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
    
    global GEMMA_PIPELINE

    # Check availability
    if not is_gemma_available():
        log_interaction(
            intent="gemma_generate",
            tenant_id=tenant_id,
            success=False,
            error="Gemma pipeline not available",
            fallback_used=True
        )
        return {
            "response": "I'm having trouble accessing my language model right now. Please try again in a moment!",
            "available": False,
            "error": "Pipeline not initialized"
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
    gen_kwargs = {
        "max_new_tokens": max_new_tokens,
        "temperature": temperature,
        "do_sample": True if temperature > 0.0 else False,
        "return_full_text": False
    }

    try:
        loop = asyncio.get_event_loop()
        
        # Run model inference in thread executor
        results = await loop.run_in_executor(
            None,
            lambda: GEMMA_PIPELINE(prompt, **gen_kwargs)
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Parse results
        if results and isinstance(results, list) and len(results) > 0:
            if isinstance(results[0], dict) and 'generated_text' in results[0]:
                generated_text = results[0]['generated_text'].strip()
                
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
            error="Unexpected model output format",
            response_time_ms=response_time_ms
        )
        
        return {
            "response": "I got an unexpected response from my language model. Let me try to help you another way!",
            "available": True,
            "error": "Unexpected output format"
        }

    except asyncio.CancelledError:
        log_interaction(
            intent="gemma_generate",
            tenant_id=tenant_id,
            success=False,
            error="Generation cancelled"
        )
        raise
        
    except Exception as e:
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