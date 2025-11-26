# models/sentiment/sentiment_utils.py

"""
Sentiment Analysis Model Utilities for PENNY Project
Handles text sentiment classification for user input analysis and content moderation.
Provides async sentiment analysis with structured error handling and logging.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List

# --- Logging Imports ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- Model Loader Import ---
try:
    from app.model_loader import load_model_pipeline
    MODEL_LOADER_AVAILABLE = True
except ImportError:
    MODEL_LOADER_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning("Could not import load_model_pipeline. Sentiment service unavailable.")

# Global variable to store the loaded pipeline for re-use
SENTIMENT_PIPELINE: Optional[Any] = None
AGENT_NAME = "penny-sentiment-agent"
INITIALIZATION_ATTEMPTED = False


def _initialize_sentiment_pipeline() -> bool:
    """
    Initializes the sentiment pipeline only once.
    
    Returns:
        bool: True if initialization succeeded, False otherwise.
    """
    global SENTIMENT_PIPELINE, INITIALIZATION_ATTEMPTED
    
    if INITIALIZATION_ATTEMPTED:
        return SENTIMENT_PIPELINE is not None
    
    INITIALIZATION_ATTEMPTED = True
    
    if not MODEL_LOADER_AVAILABLE:
        log_interaction(
            intent="sentiment_initialization",
            success=False,
            error="model_loader unavailable"
        )
        return False
    
    try:
        log_interaction(
            intent="sentiment_initialization",
            success=None,
            details=f"Loading {AGENT_NAME}"
        )
        
        SENTIMENT_PIPELINE = load_model_pipeline(AGENT_NAME)
        
        if SENTIMENT_PIPELINE is None:
            log_interaction(
                intent="sentiment_initialization",
                success=False,
                error="Pipeline returned None"
            )
            return False
        
        log_interaction(
            intent="sentiment_initialization",
            success=True,
            details=f"Model {AGENT_NAME} loaded successfully"
        )
        return True
        
    except Exception as e:
        log_interaction(
            intent="sentiment_initialization",
            success=False,
            error=str(e)
        )
        return False


# Attempt initialization at module load
_initialize_sentiment_pipeline()


def is_sentiment_available() -> bool:
    """
    Check if sentiment analysis service is available.
    
    Returns:
        bool: True if sentiment pipeline is loaded and ready.
    """
    return SENTIMENT_PIPELINE is not None


async def get_sentiment_analysis(
    text: str,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs sentiment analysis on the input text using the loaded pipeline.

    Args:
        text: The string of text to analyze.
        tenant_id: Optional tenant identifier for logging.

    Returns:
        A dictionary containing:
            - label (str): Sentiment label (e.g., "POSITIVE", "NEGATIVE", "NEUTRAL")
            - score (float): Confidence score for the sentiment prediction
            - available (bool): Whether the service was available
            - message (str, optional): Error message if analysis failed
            - response_time_ms (int, optional): Analysis time in milliseconds
    """
    start_time = time.time()
    
    global SENTIMENT_PIPELINE

    # Check availability
    if not is_sentiment_available():
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Sentiment pipeline not available",
            fallback_used=True
        )
        return {
            "label": "UNKNOWN",
            "score": 0.0,
            "available": False,
            "message": "Sentiment analysis is temporarily unavailable."
        }

    # Validate input
    if not text or not isinstance(text, str):
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Invalid text input"
        )
        return {
            "label": "ERROR",
            "score": 0.0,
            "available": True,
            "message": "Invalid text input provided."
        }
    
    # Check text length (prevent processing extremely long texts)
    if len(text) > 10000:  # 10k character limit
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error=f"Text too long: {len(text)} characters",
            text_preview=sanitize_for_logging(text[:100])
        )
        return {
            "label": "ERROR",
            "score": 0.0,
            "available": True,
            "message": "Text is too long for sentiment analysis (max 10,000 characters)."
        }

    try:
        loop = asyncio.get_event_loop()
        
        # Run model inference in thread executor
        # Hugging Face pipelines accept lists and return lists
        results = await loop.run_in_executor(
            None,
            lambda: SENTIMENT_PIPELINE([text])
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Validate results
        if not results or not isinstance(results, list) or len(results) == 0:
            log_interaction(
                intent="sentiment_analysis",
                tenant_id=tenant_id,
                success=False,
                error="Empty or invalid model output",
                response_time_ms=response_time_ms,
                text_preview=sanitize_for_logging(text[:100])
            )
            return {
                "label": "ERROR",
                "score": 0.0,
                "available": True,
                "message": "Sentiment analysis returned unexpected format."
            }
        
        result = results[0]
        
        # Validate result structure
        if not isinstance(result, dict) or 'label' not in result or 'score' not in result:
            log_interaction(
                intent="sentiment_analysis",
                tenant_id=tenant_id,
                success=False,
                error="Invalid result structure",
                response_time_ms=response_time_ms,
                text_preview=sanitize_for_logging(text[:100])
            )
            return {
                "label": "ERROR",
                "score": 0.0,
                "available": True,
                "message": "Sentiment analysis returned unexpected format."
            }
        
        # Log slow analysis
        if response_time_ms > 3000:  # 3 seconds
            log_interaction(
                intent="sentiment_analysis_slow",
                tenant_id=tenant_id,
                success=True,
                response_time_ms=response_time_ms,
                details="Slow sentiment analysis detected",
                text_length=len(text)
            )
        
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=True,
            response_time_ms=response_time_ms,
            sentiment_label=result.get('label'),
            sentiment_score=result.get('score'),
            text_length=len(text)
        )
        
        return {
            "label": result['label'],
            "score": float(result['score']),
            "available": True,
            "response_time_ms": response_time_ms
        }

    except asyncio.CancelledError:
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Analysis cancelled"
        )
        raise
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error=str(e),
            response_time_ms=response_time_ms,
            text_preview=sanitize_for_logging(text[:100]),
            fallback_used=True
        )
        
        return {
            "label": "ERROR",
            "score": 0.0,
            "available": False,
            "message": "An error occurred during sentiment analysis.",
            "error": str(e),
            "response_time_ms": response_time_ms
        }


async def analyze_sentiment_batch(
    texts: List[str],
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs sentiment analysis on a batch of texts for efficiency.
    
    Args:
        texts: List of text strings to analyze.
        tenant_id: Optional tenant identifier for logging.
    
    Returns:
        A dictionary containing:
            - results (list): List of sentiment analysis results for each text
            - available (bool): Whether the service was available
            - total_analyzed (int): Number of texts successfully analyzed
            - response_time_ms (int, optional): Total batch analysis time
    """
    start_time = time.time()
    
    global SENTIMENT_PIPELINE

    # Check availability
    if not is_sentiment_available():
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Sentiment pipeline not available",
            batch_size=len(texts) if texts else 0
        )
        return {
            "results": [],
            "available": False,
            "total_analyzed": 0,
            "message": "Sentiment analysis is temporarily unavailable."
        }

    # Validate input
    if not texts or not isinstance(texts, list):
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Invalid texts input"
        )
        return {
            "results": [],
            "available": True,
            "total_analyzed": 0,
            "message": "Invalid batch input provided."
        }
    
    # Filter valid texts and limit batch size
    valid_texts = [t for t in texts if isinstance(t, str) and t.strip()]
    if len(valid_texts) > 100:  # Batch size limit
        valid_texts = valid_texts[:100]
    
    if not valid_texts:
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=False,
            error="No valid texts in batch"
        )
        return {
            "results": [],
            "available": True,
            "total_analyzed": 0,
            "message": "No valid texts provided for analysis."
        }

    try:
        loop = asyncio.get_event_loop()
        
        # Run batch inference in thread executor
        results = await loop.run_in_executor(
            None,
            lambda: SENTIMENT_PIPELINE(valid_texts)
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=True,
            response_time_ms=response_time_ms,
            batch_size=len(valid_texts),
            total_analyzed=len(results) if results else 0
        )
        
        return {
            "results": results if results else [],
            "available": True,
            "total_analyzed": len(results) if results else 0,
            "response_time_ms": response_time_ms
        }

    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=False,
            error=str(e),
            response_time_ms=response_time_ms,
            batch_size=len(valid_texts)
        )
        
        return {
            "results": [],
            "available": False,
            "total_analyzed": 0,
            "message": "An error occurred during batch sentiment analysis.",
            "error": str(e),
            "response_time_ms": response_time_ms
        }