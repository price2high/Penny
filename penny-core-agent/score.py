"""
Penny Core Agent - Azure ML Scoring Script
Provides conversational AI responses for civic engagement
Uses Gemma-7B for natural language generation with Penny's civic personality
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Global model artifacts
tokenizer: Optional[AutoTokenizer] = None
model: Optional[AutoModelForCausalLM] = None

# Model configuration
MODEL_NAME = "google/gemma-7b-it"
MAX_NEW_TOKENS = 256
DEFAULT_TEMPERATURE = 0.7

# Penny's system prompt (civic-focused personality)
PENNY_SYSTEM_PROMPT = (
    "You are Penny, a warm, helpful civic engagement assistant. "
    "You help residents connect with local government services, community events, "
    "and civic resources. Be friendly, clear, and supportive."
)


def init() -> None:
    """
    Initialize the Gemma language model and tokenizer.
    Called once when the scoring service starts.
    
    Raises:
        Exception: If model loading fails
    """
    global tokenizer, model
    
    try:
        start_time = time.time()
        logger.info(f"Loading core language model: {MODEL_NAME}")
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        logger.info("Tokenizer loaded successfully")
        
        # Load model
        model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
        model.eval()  # Set to evaluation mode
        logger.info("Model loaded successfully")
        
        load_time = time.time() - start_time
        logger.info(f"Core agent initialized in {load_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Failed to initialize core model: {str(e)}")
        raise


def run(raw_data: str) -> str:
    """
    Execute text generation inference on input prompt.
    
    Args:
        raw_data: JSON string containing prompt and generation parameters
        
    Returns:
        JSON string with generated response
        
    Expected input format:
        {
            "prompt": "User's question or conversation",
            "max_new_tokens": 256,  # Optional
            "temperature": 0.7      # Optional
        }
        
    Output format:
        {
            "response": str,
            "model": str,
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
                "response": "",
                "success": False
            })
        
        # Extract prompt
        prompt = body.get("prompt", "").strip()
        if not prompt:
            logger.warning("Empty prompt provided")
            return json.dumps({
                "error": "No prompt provided",
                "response": "",
                "success": False
            })
        
        # Get generation parameters
        max_new_tokens = body.get("max_new_tokens", MAX_NEW_TOKENS)
        temperature = body.get("temperature", DEFAULT_TEMPERATURE)
        
        # Prepend system prompt
        full_prompt = PENNY_SYSTEM_PROMPT + "\n\n" + prompt
        
        # Perform inference
        with torch.no_grad():
            inputs = tokenizer(
                full_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0.0,
                pad_token_id=tokenizer.eos_token_id
            )
            
            # Decode response
            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove the prompt from the response
            if full_prompt in generated_text:
                response = generated_text.replace(full_prompt, "").strip()
            else:
                response = generated_text.strip()
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Build response
        result = {
            "response": response,
            "model": MODEL_NAME,
            "processing_time_ms": round(processing_time_ms, 2),
            "success": True
        }
        
        logger.info(f"Generation completed: time={processing_time_ms:.1f}ms, tokens={max_new_tokens}")
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error during text generation: {str(e)}")
        processing_time_ms = (time.time() - start_time) * 1000
        
        return json.dumps({
            "error": f"Generation failed: {str(e)}",
            "response": "",
            "success": False,
            "processing_time_ms": round(processing_time_ms, 2)
        })

