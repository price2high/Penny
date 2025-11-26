# models/bias/bias_utils.py

"""
Bias Detection Utilities for Penny

Provides zero-shot classification for detecting potential bias in text responses.
Uses a classification model to identify neutral content vs. biased language patterns.
"""

import asyncio
from typing import Dict, Any, Optional, List
import logging

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Model Loader Import ---
try:
    from app.model_loader import load_model_pipeline
    MODEL_LOADER_AVAILABLE = True
except ImportError:
    MODEL_LOADER_AVAILABLE = False
    logger.warning("Could not import load_model_pipeline. Bias detection will operate in fallback mode.")

# Global variable to store the loaded pipeline for re-use
BIAS_PIPELINE: Optional[Any] = None
AGENT_NAME = "penny-bias-checker"

# Define the labels for Zero-Shot Classification.
CANDIDATE_LABELS = [
    "neutral and objective",
    "contains political bias",
    "uses emotional language",
    "is factually biased",
]


def _initialize_bias_pipeline() -> bool:
    """
    Initializes the bias detection pipeline only once.
    
    Returns:
        bool: True if pipeline loaded successfully, False otherwise
    """
    global BIAS_PIPELINE
    
    if BIAS_PIPELINE is not None:
        return True
    
    if not MODEL_LOADER_AVAILABLE:
        logger.warning(f"{AGENT_NAME}: Model loader not available, pipeline initialization skipped")
        return False
    
    try:
        logger.info(f"Loading {AGENT_NAME}...")
        BIAS_PIPELINE = load_model_pipeline(AGENT_NAME)
        logger.info(f"Model {AGENT_NAME} loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load {AGENT_NAME}: {e}", exc_info=True)
        BIAS_PIPELINE = None
        return False


# Attempt to initialize pipeline at module load
_initialize_bias_pipeline()


async def check_bias(text: str) -> Dict[str, Any]:
    """
    Runs zero-shot classification to check for bias in the input text.
    
    Uses a pre-loaded classification model to analyze text for:
    - Neutral and objective language
    - Political bias
    - Emotional language
    - Factual bias
    
    Args:
        text: The string of text to analyze for bias
        
    Returns:
        Dictionary containing:
            - analysis: List of labels with confidence scores, sorted by score
            - available: Whether the bias detection service is operational
            - message: Optional error or status message
            
    Example:
        >>> result = await check_bias("This is neutral text.")
        >>> result['analysis'][0]['label']
        'neutral and objective'
    """
    global BIAS_PIPELINE
    
    # Input validation
    if not text or not isinstance(text, str):
        logger.warning("check_bias called with invalid text input")
        return {
            "analysis": [],
            "available": False,
            "message": "Invalid input: text must be a non-empty string"
        }
    
    # Strip text to avoid processing whitespace
    text = text.strip()
    if not text:
        logger.warning("check_bias called with empty text after stripping")
        return {
            "analysis": [],
            "available": False,
            "message": "Invalid input: text is empty"
        }
    
    # Ensure pipeline is initialized
    if BIAS_PIPELINE is None:
        logger.warning(f"{AGENT_NAME} pipeline not available, attempting re-initialization")
        if not _initialize_bias_pipeline():
            return {
                "analysis": [],
                "available": False,
                "message": "Bias detection service is currently unavailable"
            }
    
    try:
        loop = asyncio.get_event_loop()
        
        # Run inference in thread pool to avoid blocking
        results = await loop.run_in_executor(
            None,
            lambda: BIAS_PIPELINE(
                text,
                CANDIDATE_LABELS,
                multi_label=True
            )
        )
        
        # Validate results structure
        if not results or not isinstance(results, dict):
            logger.error(f"Bias detection returned unexpected format: {type(results)}")
            return {
                "analysis": [],
                "available": True,
                "message": "Inference returned unexpected format"
            }
        
        labels = results.get('labels', [])
        scores = results.get('scores', [])
        
        if not labels or not scores:
            logger.warning("Bias detection returned empty labels or scores")
            return {
                "analysis": [],
                "available": True,
                "message": "No classification results returned"
            }
        
        # Build analysis results
        analysis = [
            {"label": label, "score": float(score)}
            for label, score in zip(labels, scores)
        ]
        
        # Sort by confidence score (descending)
        analysis.sort(key=lambda x: x['score'], reverse=True)
        
        logger.debug(f"Bias check completed successfully, top result: {analysis[0]['label']} ({analysis[0]['score']:.3f})")
        
        return {
            "analysis": analysis,
            "available": True
        }
    
    except asyncio.CancelledError:
        logger.warning("Bias detection task was cancelled")
        raise
    
    except Exception as e:
        logger.error(f"Error during bias detection inference: {e}", exc_info=True)
        return {
            "analysis": [],
            "available": False,
            "message": f"Bias detection error: {str(e)}"
        }


def get_bias_pipeline_status() -> Dict[str, Any]:
    """
    Returns the current status of the bias detection pipeline.
    
    Returns:
        Dictionary with pipeline availability status
    """
    return {
        "agent_name": AGENT_NAME,
        "available": BIAS_PIPELINE is not None,
        "model_loader_available": MODEL_LOADER_AVAILABLE
    }