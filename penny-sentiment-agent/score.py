"""
Penny Sentiment Agent - Azure ML Scoring Script
Provides sentiment analysis for community feedback and civic engagement monitoring
Analyzes tone and sentiment of citizen input to improve Penny's community understanding
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Global model artifacts
tokenizer: Optional[AutoTokenizer] = None
model: Optional[AutoModelForSequenceClassification] = None

# Model configuration
MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment"
MAX_INPUT_LENGTH = 512
SENTIMENT_LABELS = {
    0: "negative",
    1: "neutral",
    2: "positive"
}


def init() -> None:
    """
    Initialize the sentiment analysis model and tokenizer.
    Called once when the scoring service starts.
    
    Raises:
        Exception: If model loading fails
    """
    global tokenizer, model
    
    try:
        start_time = time.time()
        logger.info(f"Loading sentiment analysis model: {MODEL_NAME}")
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            model_max_length=MAX_INPUT_LENGTH
        )
        logger.info("Tokenizer loaded successfully")
        
        # Load model
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        model.eval()  # Set to evaluation mode
        logger.info("Model loaded successfully")
        
        load_time = time.time() - start_time
        logger.info(f"Sentiment analysis service initialized in {load_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Failed to initialize sentiment analysis model: {str(e)}")
        raise


def run(raw_data: str) -> str:
    """
    Execute sentiment analysis inference on input text.
    
    Args:
        raw_data: JSON string containing text for sentiment analysis
        
    Returns:
        JSON string with sentiment analysis results
        
    Expected input format:
        {
            "text": "Community feedback or user input to analyze"
        }
        
    Output format:
        {
            "sentiment": str,  # "positive", "neutral", or "negative"
            "sentiment_score": int,  # 0=negative, 1=neutral, 2=positive
            "confidence": float,  # Probability of predicted class
            "probabilities": {
                "negative": float,
                "neutral": float,
                "positive": float
            },
            "processing_time_ms": float
        }
    """
    start_time = time.time()
    
    try:
        # Parse input
        try:
            body = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON input: {str(e)}")
            return json.dumps({
                "error": "Invalid JSON format",
                "sentiment": "neutral",
                "sentiment_score": 1,
                "confidence": 0.0
            })
        
        # Extract and validate text
        text = body.get("text", "").strip()
        if not text:
            logger.warning("Empty text provided for sentiment analysis")
            return json.dumps({
                "error": "No text provided",
                "sentiment": "neutral",
                "sentiment_score": 1,
                "confidence": 0.0
            })
        
        # Truncate if too long
        original_length = len(text)
        if len(text) > MAX_INPUT_LENGTH * 4:  # Rough character estimate
            logger.warning(f"Input text truncated from {original_length} to ~{MAX_INPUT_LENGTH * 4} chars")
            text = text[:MAX_INPUT_LENGTH * 4]
        
        # Perform inference
        with torch.no_grad():
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_INPUT_LENGTH,
                padding=True
            )
            
            outputs = model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1).squeeze()
            
            # Get prediction
            predicted_class = logits.argmax(-1).item()
            confidence = probabilities[predicted_class].item()
            
            # Get sentiment label
            sentiment_label = SENTIMENT_LABELS.get(predicted_class, "unknown")
            
            # Extract all probabilities
            prob_dict = {
                "negative": float(probabilities[0].item()),
                "neutral": float(probabilities[1].item()),
                "positive": float(probabilities[2].item())
            }
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Build response
        result = {
            "sentiment": sentiment_label,
            "sentiment_score": predicted_class,
            "confidence": round(float(confidence), 4),
            "probabilities": prob_dict,
            "text_length": original_length,
            "truncated": original_length > len(text),
            "processing_time_ms": round(processing_time_ms, 2),
            "model": MODEL_NAME
        }
        
        logger.info(
            f"Sentiment analysis completed: sentiment={sentiment_label}, "
            f"confidence={confidence:.3f}, time={processing_time_ms:.1f}ms"
        )
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error during sentiment analysis inference: {str(e)}")
        processing_time_ms = (time.time() - start_time) * 1000
        
        return json.dumps({
            "error": f"Inference failed: {str(e)}",
            "sentiment": "neutral",
            "sentiment_score": 1,
            "confidence": 0.0,
            "processing_time_ms": round(processing_time_ms, 2)
        })