# models/bias/bias_utils.py

"""
Bias Detection Utilities for Penny

Provides zero-shot classification for detecting potential bias in text responses.
Uses a classification model to identify neutral content vs. biased language patterns.
"""

import asyncio
import os
import httpx
from typing import Dict, Any, Optional, List
import logging

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Hugging Face API Configuration ---
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
HF_TOKEN = os.getenv("HF_TOKEN")

AGENT_NAME = "penny-bias-checker"

# Define the labels for Zero-Shot Classification.
CANDIDATE_LABELS = [
    "neutral and objective",
    "contains political bias",
    "uses emotional language",
    "is factually biased",
]


def _is_bias_available() -> bool:
    """
    Check if bias detection service is available.
    
    Returns:
        bool: True if HF_TOKEN is configured
    """
    return HF_TOKEN is not None and len(HF_TOKEN) > 0


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
    
    # Check API availability
    if not _is_bias_available():
        logger.warning(f"{AGENT_NAME}: API not configured (missing HF_TOKEN)")
        return {
            "analysis": [],
            "available": False,
            "message": "Bias detection service is currently unavailable"
        }
    
    try:
        # Prepare API request for zero-shot classification
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {
            "inputs": text,
            "parameters": {
                "candidate_labels": CANDIDATE_LABELS,
                "multi_label": True
            }
        }
        
        # Call Hugging Face Inference API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(HF_API_URL, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Bias detection API returned status {response.status_code}")
                return {
                    "analysis": [],
                    "available": False,
                    "message": f"Bias detection API error: {response.status_code}"
                }
            
            results = response.json()
        
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
    
    except httpx.TimeoutException:
        logger.error("Bias detection request timed out")
        return {
            "analysis": [],
            "available": False,
            "message": "Bias detection request timed out"
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
        "available": _is_bias_available(),
        "api_configured": HF_TOKEN is not None
    }