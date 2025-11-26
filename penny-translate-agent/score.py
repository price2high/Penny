"""
Penny Translation Agent - Azure ML Scoring Script
Provides multilingual translation for accessible civic information
Supports 200+ languages via NLLB-200 for equitable community engagement
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Global model artifacts
tokenizer: Optional[AutoTokenizer] = None
model: Optional[AutoModelForSeq2SeqLM] = None

# Model configuration
MODEL_NAME = "facebook/nllb-200-distilled-600M"
MAX_INPUT_LENGTH = 512
MAX_OUTPUT_LENGTH = 512
DEFAULT_TARGET_LANG = "eng_Latn"  # English (Latin script)
DEFAULT_SOURCE_LANG = "eng_Latn"


def init() -> None:
    """
    Initialize the multilingual translation model and tokenizer.
    Called once when the scoring service starts.
    
    Raises:
        Exception: If model loading fails
    """
    global tokenizer, model
    
    try:
        start_time = time.time()
        logger.info(f"Loading translation model: {MODEL_NAME}")
        
        # Load tokenizer with source language
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            src_lang=DEFAULT_SOURCE_LANG,
            model_max_length=MAX_INPUT_LENGTH
        )
        logger.info("Tokenizer loaded successfully")
        
        # Load seq2seq model
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        model.eval()  # Set to evaluation mode
        logger.info("Model loaded successfully")
        
        load_time = time.time() - start_time
        logger.info(f"Translation service initialized in {load_time:.2f}s")
        logger.info(f"Supports 200+ languages via NLLB-200")
        
    except Exception as e:
        logger.error(f"Failed to initialize translation model: {str(e)}")
        raise


def run(raw_data: str) -> str:
    """
    Execute multilingual translation inference on input text.
    
    Args:
        raw_data: JSON string containing text and language parameters
        
    Returns:
        JSON string with translation results
        
    Expected input format:
        {
            "text": "Text to translate",
            "source_lang": "eng_Latn",  # Optional, defaults to eng_Latn
            "target_lang": "spa_Latn",  # Optional, defaults to eng_Latn
            "max_length": 512           # Optional, defaults to 512
        }
        
    Output format:
        {
            "translation": str,
            "source_lang": str,
            "target_lang": str,
            "source_length": int,
            "translation_length": int,
            "processing_time_ms": float,
            "success": bool
        }
        
    Common NLLB language codes:
        - eng_Latn (English), spa_Latn (Spanish), fra_Latn (French)
        - deu_Latn (German), ita_Latn (Italian), por_Latn (Portuguese)
        - zho_Hans (Chinese Simplified), ara_Arab (Arabic), hin_Deva (Hindi)
        - jpn_Jpan (Japanese), kor_Hang (Korean), rus_Cyrl (Russian)
        - vie_Latn (Vietnamese), tha_Thai (Thai), pol_Latn (Polish)
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
                "translation": "",
                "success": False
            })
        
        # Extract and validate text
        text = body.get("text", "").strip()
        if not text:
            logger.warning("Empty text provided for translation")
            return json.dumps({
                "error": "No text provided",
                "translation": "",
                "success": False
            })
        
        # Get language parameters
        source_lang = body.get("source_lang", DEFAULT_SOURCE_LANG).strip()
        target_lang = body.get("target_lang", DEFAULT_TARGET_LANG).strip()
        max_length = body.get("max_length", MAX_OUTPUT_LENGTH)
        
        # Validate language codes (basic check for NLLB format)
        if not source_lang or "_" not in source_lang:
            logger.warning(f"Invalid source language code: {source_lang}, using default")
            source_lang = DEFAULT_SOURCE_LANG
        
        if not target_lang or "_" not in target_lang:
            logger.warning(f"Invalid target language code: {target_lang}, using default")
            target_lang = DEFAULT_TARGET_LANG
        
        # Truncate if too long
        original_length = len(text)
        if len(text) > MAX_INPUT_LENGTH * 4:  # Rough character estimate
            logger.warning(f"Input text truncated from {original_length} to ~{MAX_INPUT_LENGTH * 4} chars")
            text = text[:MAX_INPUT_LENGTH * 4]
        
        # Set source language for tokenizer
        tokenizer.src_lang = source_lang
        
        # Perform translation
        with torch.no_grad():
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_INPUT_LENGTH,
                padding=True
            )
            
            # Get target language token ID
            try:
                forced_bos_token_id = tokenizer.convert_tokens_to_ids(target_lang)
            except Exception as e:
                logger.error(f"Failed to convert target language '{target_lang}': {str(e)}")
                return json.dumps({
                    "error": f"Invalid target language: {target_lang}",
                    "translation": "",
                    "success": False
                })
            
            # Generate translation
            translated_tokens = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_length=max_length,
                num_beams=5,  # Beam search for better quality
                early_stopping=True
            )
            
            # Decode translation
            translation = tokenizer.decode(
                translated_tokens[0],
                skip_special_tokens=True
            )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Build response
        result = {
            "success": True,
            "translation": translation,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_length": original_length,
            "translation_length": len(translation),
            "truncated": original_length > len(text),
            "processing_time_ms": round(processing_time_ms, 2),
            "model": MODEL_NAME
        }
        
        logger.info(
            f"Translation completed: {source_lang} -> {target_lang}, "
            f"length={original_length}, time={processing_time_ms:.1f}ms"
        )
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"Error during translation inference: {str(e)}")
        processing_time_ms = (time.time() - start_time) * 1000
        
        return json.dumps({
            "error": f"Translation failed: {str(e)}",
            "translation": "",
            "success": False,
            "processing_time_ms": round(processing_time_ms, 2)
        })