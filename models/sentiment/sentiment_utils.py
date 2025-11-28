# models/sentiment/sentiment_utils.py

"""
Sentiment Analysis Model Utilities for PENNY Project
Handles text sentiment classification for user input analysis and content moderation.
Provides async sentiment analysis with structured error handling and logging.
"""

import asyncio
import time
import os
import httpx
from typing import Dict, Any, Optional, List

# --- Logging Imports ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- Hugging Face API Configuration ---
HF_API_URL = "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment"
HF_TOKEN = os.getenv("HF_TOKEN")

AGENT_NAME = "penny-sentiment-agent"


def is_sentiment_available() -> bool:
    """
    Check if sentiment analysis service is available.
    
    Returns:
        bool: True if sentiment API is configured and ready.
    """
    return HF_TOKEN is not None and len(HF_TOKEN) > 0


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

    # Check availability
    if not is_sentiment_available():
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Sentiment API not configured (missing HF_TOKEN)",
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
        # Prepare API request
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {"inputs": text}
        
        # Call Hugging Face Inference API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(HF_API_URL, json=payload, headers=headers)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                log_interaction(
                    intent="sentiment_analysis",
                    tenant_id=tenant_id,
                    success=False,
                    error=f"API returned status {response.status_code}",
                    response_time_ms=response_time_ms,
                    text_preview=sanitize_for_logging(text[:100]),
                    fallback_used=True
                )
                return {
                    "label": "ERROR",
                    "score": 0.0,
                    "available": False,
                    "message": f"Sentiment API error: {response.status_code}",
                    "response_time_ms": response_time_ms
                }
            
            results = response.json()
        
        # Validate results
        # API returns: [[{"label": "LABEL_2", "score": 0.95}, ...]]
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
        
        # Get the first (highest scoring) result
        result_list = results[0] if isinstance(results[0], list) else results
        
        if not result_list or len(result_list) == 0:
            log_interaction(
                intent="sentiment_analysis",
                tenant_id=tenant_id,
                success=False,
                error="Empty result list",
                response_time_ms=response_time_ms,
                text_preview=sanitize_for_logging(text[:100])
            )
            return {
                "label": "ERROR",
                "score": 0.0,
                "available": True,
                "message": "Sentiment analysis returned unexpected format."
            }
        
        result = result_list[0]
        
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
        
        # Map RoBERTa labels to readable format
        # LABEL_0 = NEGATIVE, LABEL_1 = NEUTRAL, LABEL_2 = POSITIVE
        label_mapping = {
            "LABEL_0": "NEGATIVE",
            "LABEL_1": "NEUTRAL",
            "LABEL_2": "POSITIVE"
        }
        label = label_mapping.get(result['label'], result['label'])
        
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
            sentiment_label=label,
            sentiment_score=result.get('score'),
            text_length=len(text)
        )
        
        return {
            "label": label,
            "score": float(result['score']),
            "available": True,
            "response_time_ms": response_time_ms
        }

    except httpx.TimeoutException:
        response_time_ms = int((time.time() - start_time) * 1000)
        log_interaction(
            intent="sentiment_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Sentiment analysis request timed out",
            response_time_ms=response_time_ms,
            text_preview=sanitize_for_logging(text[:100]),
            fallback_used=True
        )
        return {
            "label": "ERROR",
            "score": 0.0,
            "available": False,
            "message": "Sentiment analysis request timed out.",
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

    # Check availability
    if not is_sentiment_available():
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Sentiment API not configured (missing HF_TOKEN)",
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
        # Prepare API request with batch input
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {"inputs": valid_texts}
        
        # Call Hugging Face Inference API
        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for batch
            response = await client.post(HF_API_URL, json=payload, headers=headers)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                log_interaction(
                    intent="sentiment_batch_analysis",
                    tenant_id=tenant_id,
                    success=False,
                    error=f"API returned status {response.status_code}",
                    response_time_ms=response_time_ms,
                    batch_size=len(valid_texts)
                )
                return {
                    "results": [],
                    "available": False,
                    "total_analyzed": 0,
                    "message": f"Sentiment API error: {response.status_code}",
                    "response_time_ms": response_time_ms
                }
            
            results = response.json()
        
        # Process results and map labels
        label_mapping = {
            "LABEL_0": "NEGATIVE",
            "LABEL_1": "NEUTRAL",
            "LABEL_2": "POSITIVE"
        }
        
        processed_results = []
        if results and isinstance(results, list):
            for item in results:
                if isinstance(item, list) and len(item) > 0:
                    top_result = item[0]
                    if isinstance(top_result, dict) and 'label' in top_result:
                        processed_results.append({
                            "label": label_mapping.get(top_result['label'], top_result['label']),
                            "score": float(top_result.get('score', 0.0))
                        })
        
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=True,
            response_time_ms=response_time_ms,
            batch_size=len(valid_texts),
            total_analyzed=len(processed_results)
        )
        
        return {
            "results": processed_results,
            "available": True,
            "total_analyzed": len(processed_results),
            "response_time_ms": response_time_ms
        }

    except httpx.TimeoutException:
        response_time_ms = int((time.time() - start_time) * 1000)
        log_interaction(
            intent="sentiment_batch_analysis",
            tenant_id=tenant_id,
            success=False,
            error="Batch sentiment analysis timed out",
            response_time_ms=response_time_ms,
            batch_size=len(valid_texts)
        )
        return {
            "results": [],
            "available": False,
            "total_analyzed": 0,
            "message": "Batch sentiment analysis timed out.",
            "error": "Request timeout",
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