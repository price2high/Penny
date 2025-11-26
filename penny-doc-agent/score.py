"""
Penny Document Agent - Azure ML Scoring Script
Provides PDF extraction and document understanding for civic documents
Extracts structured information from government forms, meeting minutes, and civic materials
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from transformers import AutoTokenizer, AutoModelForTokenClassification, AutoProcessor
import torch

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Global model artifacts
tokenizer: Optional[AutoTokenizer] = None
model: Optional[AutoModelForTokenClassification] = None
processor: Optional[AutoProcessor] = None

# Model configuration
MODEL_NAME = "microsoft/layoutlmv3-base"
MAX_INPUT_LENGTH = 512
MAX_TOKENS_TO_RETURN = 100


def init() -> None:
    """
    Initialize the document understanding model and tokenizer.
    Called once when the scoring service starts.
    
    Raises:
        Exception: If model loading fails
    """
    global tokenizer, model, processor
    
    try:
        start_time = time.time()
        logger.info(f"Loading document extraction model: {MODEL_NAME}")
        
        # Load processor (includes tokenizer)
        processor = AutoProcessor.from_pretrained(
            MODEL_NAME,
            apply_ocr=False  # Expect pre-extracted text
        )
        
        # Load tokenizer separately for text-only processing
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            model_max_length=MAX_INPUT_LENGTH
        )
        logger.info("Tokenizer and processor loaded successfully")
        
        # Load model for token classification
        model = AutoModelForTokenClassification.from_pretrained(MODEL_NAME)
        model.eval()  # Set to evaluation mode
        logger.info("Model loaded successfully")
        
        load_time = time.time() - start_time
        logger.info(f"Document extraction service initialized in {load_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Failed to initialize document extraction model: {str(e)}")
        raise


def run(raw_data: str) -> str:
    """
    Execute document extraction inference on input text.
    
    Args:
        raw_data: JSON string containing document text and optional metadata
        
    Returns:
        JSON string with extracted document structure
        
    Expected input format:
        {
            "text": "Document text to analyze",
            "return_tokens": true,  # Optional: return token classifications
            "max_tokens": 100       # Optional: limit tokens returned
        }
        
    Output format:
        {
            "extracted_text": str,
            "token_count": int,
            "tokens": List[int],  # Optional: token classifications
            "entities": List[Dict],  # Detected entities if applicable
            "processing_time_ms": float,
            "success": bool
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
                "success": False,
                "extracted_text": "",
                "token_count": 0
            })
        
        # Extract and validate text
        text = body.get("text", "").strip()
        if not text:
            logger.warning("Empty text provided for document extraction")
            return json.dumps({
                "error": "No text provided",
                "success": False,
                "extracted_text": "",
                "token_count": 0
            })
        
        # Get options
        return_tokens = body.get("return_tokens", False)
        max_tokens = body.get("max_tokens", MAX_TOKENS_TO_RETURN)
        
        # Truncate if too long
        original_length = len(text)
        if len(text) > MAX_INPUT_LENGTH * 4:  # Rough char estimate
            logger.warning(f"Input text truncated from ~{original_length} chars")
            text = text[:MAX_INPUT_LENGTH * 4]
        
        # Perform tokenization and inference
        with torch.no_grad():
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_INPUT_LENGTH,
                padding=True
            )
            
            # Get model outputs
            outputs = model(**inputs)
            logits = outputs.logits
            
            # Get predicted token classes
            predictions = logits.argmax(-1).squeeze().tolist()
            
            # Handle single token case (scalar instead of list)
            if isinstance(predictions, int):
                predictions = [predictions]
            
            # Limit tokens returned if requested
            if return_tokens and len(predictions) > max_tokens:
                predictions = predictions[:max_tokens]
                logger.info(f"Token predictions truncated to {max_tokens}")
        
        # Decode tokens back to text for verification
        token_ids = inputs["input_ids"].squeeze().tolist()
        if isinstance(token_ids, int):
            token_ids = [token_ids]
            
        extracted_text = tokenizer.decode(token_ids, skip_special_tokens=True)
        
        # Count actual tokens
        token_count = len(token_ids)
        
        # Build response
        result = {
            "success": True,
            "extracted_text": extracted_text,
            "token_count": token_count,
            "original_length": original_length,
            "truncated": original_length > len(text),
            "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            "model": MODEL_NAME
        }
        
        # Add token classifications if requested
        if return_tokens:
            result["tokens"] = predictions
            result["tokens_returned"] = len(predictions)
        
        logger.info(
            f"Document extraction completed: tokens={token_count}, "
            f"time={(time.time() - start_time) * 1000:.1f}ms"
        )
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error during document extraction inference: {str(e)}")
        processing_time_ms = (time.time() - start_time) * 1000
        
        return json.dumps({
            "error": f"Inference failed: {str(e)}",
            "success": False,
            "extracted_text": "",
            "token_count": 0,
            "processing_time_ms": round(processing_time_ms, 2)
        })