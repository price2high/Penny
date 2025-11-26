"""
Penny Bias Detection Agent - Azure ML Scoring Script
Provides bias detection inference for civic engagement content
Ensures fair and equitable information delivery across Penny's platform
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
MODEL_NAME = "facebook/bart-large-mnli"
MAX_INPUT_LENGTH = 1024
DEFAULT_HYPOTHESIS = "This text contains bias."


def init() -> None:
    """
    Initialize the bias detection model and tokenizer.
    Called once when the scoring service starts.
    
    Raises:
        Exception: If model loading fails
    """
    global tokenizer, model
    
    try:
        start_time = time.time()
        logger.info(f"Loading bias detection model: {MODEL_NAME}")
        
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
        logger.info(f"Bias detection service initialized in {load_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Failed to initialize bias detection model: {str(e)}")
        raise


def run(raw_data: str) -> str:
    """
    Execute bias detection inference on input text.
    
    Args:
        raw_data: JSON string containing 'text' and optional 'hypothesis'
        
    Returns:
        JSON string with bias detection results
        
    Expected input format:
        {
            "text": "Content to analyze for bias",
            "hypothesis": "Optional custom hypothesis (defaults to generic bias check)"
        }
        
    Output format:
        {
            "bias_detected": bool,
            "bias_score": float,
            "confidence": float,
            "label": str,
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
                "bias_detected": False,
                "bias_score": 0.0
            })
        
        # Extract and validate text
        text = body.get("text", "").strip()
        if not text:
            logger.warning("Empty text provided for bias detection")
            return json.dumps({
                "error": "No text provided",
                "bias_detected": False,
                "bias_score": 0.0
            })
        
        # Truncate if too long
        if len(text) > MAX_INPUT_LENGTH:
            logger.warning(f"Input text truncated from {len(text)} to {MAX_INPUT_LENGTH} chars")
            text = text[:MAX_INPUT_LENGTH]
        
        # Get hypothesis (use default if not provided)
        hypothesis = body.get("hypothesis", DEFAULT_HYPOTHESIS).strip()
        if not hypothesis:
            hypothesis = DEFAULT_HYPOTHESIS
        
        # Perform inference
        with torch.no_grad():
            inputs = tokenizer(
                text,
                hypothesis,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_INPUT_LENGTH,
                padding=True
            )
            
            outputs = model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)
            
            # Get prediction
            predicted_class = logits.argmax(-1).item()
            confidence = probabilities[0][predicted_class].item()
            
            # Map MNLI labels: 0=contradiction, 1=neutral, 2=entailment
            # For bias detection: 2=entailment means bias detected
            bias_detected = predicted_class == 2
            
            # Label mapping
            label_map = {
                0: "no_bias_detected",
                1: "uncertain",
                2: "bias_detected"
            }
            label = label_map.get(predicted_class, "unknown")
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Build response
        result = {
            "bias_detected": bias_detected,
            "bias_score": float(predicted_class),
            "confidence": float(confidence),
            "label": label,
            "processing_time_ms": round(processing_time_ms, 2),
            "model": MODEL_NAME
        }
        
        logger.info(
            f"Bias detection completed: label={label}, "
            f"confidence={confidence:.3f}, time={processing_time_ms:.1f}ms"
        )
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error during bias detection inference: {str(e)}")
        processing_time_ms = (time.time() - start_time) * 1000
        
        return json.dumps({
            "error": f"Inference failed: {str(e)}",
            "bias_detected": False,
            "bias_score": 0.0,
            "confidence": 0.0,
            "processing_time_ms": round(processing_time_ms, 2)
        })