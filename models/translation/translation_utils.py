# models/translation/translation_utils.py

"""
Translation Model Utilities for PENNY Project
Handles multilingual translation using NLLB-200 for civic engagement accessibility.
Provides async translation with structured error handling and language code normalization.
"""

import asyncio
import time
import os
import httpx
from typing import Dict, Any, Optional, List

# --- Logging Imports ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- Hugging Face API Configuration ---
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M"
HF_TOKEN = os.getenv("HF_TOKEN")

AGENT_NAME = "penny-translate-agent"
SERVICE_AVAILABLE = True  # Assume available since we're using API

# NLLB-200 Language Code Mapping (Common languages for civic engagement)
LANGUAGE_CODES = {
    # English variants
    "english": "eng_Latn",
    "en": "eng_Latn",
    
    # Spanish variants
    "spanish": "spa_Latn",
    "es": "spa_Latn",
    "español": "spa_Latn",
    
    # French
    "french": "fra_Latn",
    "fr": "fra_Latn",
    "français": "fra_Latn",
    
    # Mandarin Chinese
    "chinese": "zho_Hans",
    "mandarin": "zho_Hans",
    "zh": "zho_Hans",
    
    # Arabic
    "arabic": "arb_Arab",
    "ar": "arb_Arab",
    
    # Hindi
    "hindi": "hin_Deva",
    "hi": "hin_Deva",
    
    # Portuguese
    "portuguese": "por_Latn",
    "pt": "por_Latn",
    
    # Russian
    "russian": "rus_Cyrl",
    "ru": "rus_Cyrl",
    
    # German
    "german": "deu_Latn",
    "de": "deu_Latn",
    
    # Vietnamese
    "vietnamese": "vie_Latn",
    "vi": "vie_Latn",
    
    # Tagalog
    "tagalog": "tgl_Latn",
    "tl": "tgl_Latn",
    
    # Urdu
    "urdu": "urd_Arab",
    "ur": "urd_Arab",
    
    # Swahili
    "swahili": "swh_Latn",
    "sw": "swh_Latn",
}

# Pre-translated civic phrases for common queries
CIVIC_PHRASES = {
    "eng_Latn": {
        "voting_location": "Where is my polling place?",
        "voter_registration": "How do I register to vote?",
        "city_services": "What city services are available?",
        "report_issue": "I want to report a problem.",
        "contact_city": "How do I contact city hall?",
    },
    "spa_Latn": {
        "voting_location": "¿Dónde está mi lugar de votación?",
        "voter_registration": "¿Cómo me registro para votar?",
        "city_services": "¿Qué servicios de la ciudad están disponibles?",
        "report_issue": "Quiero reportar un problema.",
        "contact_city": "¿Cómo contacto al ayuntamiento?",
    }
}


def is_translation_available() -> bool:
    """
    Check if translation service is available.
    
    Returns:
        bool: True if translation API is configured and ready.
    """
    return HF_TOKEN is not None and len(HF_TOKEN) > 0


def normalize_language_code(lang: str) -> str:
    """
    Converts common language names/codes to NLLB-200 format.
    
    Args:
        lang: Language name or code (e.g., "spanish", "es", "español")
        
    Returns:
        NLLB-200 language code (e.g., "spa_Latn")
    """
    if not lang or not isinstance(lang, str):
        return "eng_Latn"  # Default to English
    
    lang_lower = lang.lower().strip()
    
    # Check if it's already in NLLB format (contains underscore)
    if "_" in lang_lower:
        return lang_lower
    
    # Look up in mapping
    return LANGUAGE_CODES.get(lang_lower, lang_lower)


def get_supported_languages() -> List[str]:
    """
    Get list of supported language codes.
    
    Returns:
        List of NLLB-200 language codes supported by PENNY.
    """
    return list(set(LANGUAGE_CODES.values()))


async def translate_text(
    text: str,
    source_language: str = "eng_Latn",
    target_language: str = "spa_Latn",
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Translates text from source language to target language using NLLB-200.

    Args:
        text: The text to translate.
        source_language: Source language code (e.g., "eng_Latn", "spanish", "es")
        target_language: Target language code (e.g., "spa_Latn", "french", "fr")
        tenant_id: Optional tenant identifier for logging.

    Returns:
        A dictionary containing:
            - translated_text (str): The translated text
            - source_lang (str): Normalized source language code
            - target_lang (str): Normalized target language code
            - original_text (str): The input text
            - available (bool): Whether the service was available
            - error (str, optional): Error message if translation failed
            - response_time_ms (int, optional): Translation time in milliseconds
    """
    start_time = time.time()

    # Check availability
    if not is_translation_available():
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=False,
            error="Translation API not configured (missing HF_TOKEN)",
            fallback_used=True
        )
        return {
            "translated_text": text,  # Return original text as fallback
            "source_lang": source_language,
            "target_lang": target_language,
            "original_text": text,
            "available": False,
            "error": "Translation service is temporarily unavailable."
        }

    # Validate input
    if not text or not isinstance(text, str):
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=False,
            error="Invalid text input"
        )
        return {
            "translated_text": "",
            "source_lang": source_language,
            "target_lang": target_language,
            "original_text": text if isinstance(text, str) else "",
            "available": True,
            "error": "Invalid text input provided."
        }
    
    # Check text length (prevent processing extremely long texts)
    if len(text) > 5000:  # 5k character limit for translation
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=False,
            error=f"Text too long: {len(text)} characters",
            text_preview=sanitize_for_logging(text[:100])
        )
        return {
            "translated_text": text,
            "source_lang": source_language,
            "target_lang": target_language,
            "original_text": text,
            "available": True,
            "error": "Text is too long for translation (max 5,000 characters)."
        }

    # Normalize language codes
    src_lang = normalize_language_code(source_language)
    tgt_lang = normalize_language_code(target_language)
    
    # Skip translation if source and target are the same
    if src_lang == tgt_lang:
        log_interaction(
            intent="translation_skipped",
            tenant_id=tenant_id,
            success=True,
            details="Source and target languages are identical"
        )
        return {
            "translated_text": text,
            "source_lang": src_lang,
            "target_lang": tgt_lang,
            "original_text": text,
            "available": True,
            "skipped": True
        }

    try:
        # Prepare API request
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {
            "inputs": text,
            "parameters": {
                "src_lang": src_lang,
                "tgt_lang": tgt_lang
            }
        }
        
        # Call Hugging Face Inference API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(HF_API_URL, json=payload, headers=headers)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                log_interaction(
                    intent="translation",
                    tenant_id=tenant_id,
                    success=False,
                    error=f"API returned status {response.status_code}",
                    response_time_ms=response_time_ms,
                    source_lang=src_lang,
                    target_lang=tgt_lang,
                    fallback_used=True
                )
                return {
                    "translated_text": text,  # Fallback to original
                    "source_lang": src_lang,
                    "target_lang": tgt_lang,
                    "original_text": text,
                    "available": False,
                    "error": f"Translation API error: {response.status_code}",
                    "response_time_ms": response_time_ms
                }
            
            results = response.json()
        
        # Validate results
        if not results or not isinstance(results, list) or len(results) == 0:
            log_interaction(
                intent="translation",
                tenant_id=tenant_id,
                success=False,
                error="Empty or invalid model output",
                response_time_ms=response_time_ms,
                source_lang=src_lang,
                target_lang=tgt_lang
            )
            return {
                "translated_text": text,  # Fallback to original
                "source_lang": src_lang,
                "target_lang": tgt_lang,
                "original_text": text,
                "available": True,
                "error": "Translation returned unexpected format."
            }
        
        # NLLB returns format: [{'translation_text': '...'}]
        translated = results[0].get('translation_text', '').strip()
        
        if not translated:
            log_interaction(
                intent="translation",
                tenant_id=tenant_id,
                success=False,
                error="Empty translation result",
                response_time_ms=response_time_ms,
                source_lang=src_lang,
                target_lang=tgt_lang
            )
            return {
                "translated_text": text,  # Fallback to original
                "source_lang": src_lang,
                "target_lang": tgt_lang,
                "original_text": text,
                "available": True,
                "error": "Translation produced empty result."
            }
        
        # Log slow translations
        if response_time_ms > 5000:  # 5 seconds
            log_interaction(
                intent="translation_slow",
                tenant_id=tenant_id,
                success=True,
                response_time_ms=response_time_ms,
                details="Slow translation detected",
                source_lang=src_lang,
                target_lang=tgt_lang,
                text_length=len(text)
            )
        
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=True,
            response_time_ms=response_time_ms,
            source_lang=src_lang,
            target_lang=tgt_lang,
            text_length=len(text)
        )
        
        return {
            "translated_text": translated,
            "source_lang": src_lang,
            "target_lang": tgt_lang,
            "original_text": text,
            "available": True,
            "response_time_ms": response_time_ms
        }

    except httpx.TimeoutException:
        response_time_ms = int((time.time() - start_time) * 1000)
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=False,
            error="Translation request timed out",
            response_time_ms=response_time_ms,
            source_lang=src_lang,
            target_lang=tgt_lang,
            fallback_used=True
        )
        return {
            "translated_text": text,  # Fallback to original
            "source_lang": src_lang,
            "target_lang": tgt_lang,
            "original_text": text,
            "available": False,
            "error": "Translation request timed out.",
            "response_time_ms": response_time_ms
        }

    except asyncio.CancelledError:
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=False,
            error="Translation cancelled",
            source_lang=src_lang,
            target_lang=tgt_lang
        )
        raise
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        
        log_interaction(
            intent="translation",
            tenant_id=tenant_id,
            success=False,
            error=str(e),
            response_time_ms=response_time_ms,
            source_lang=src_lang,
            target_lang=tgt_lang,
            text_preview=sanitize_for_logging(text[:100]),
            fallback_used=True
        )
        
        return {
            "translated_text": text,  # Fallback to original
            "source_lang": src_lang,
            "target_lang": tgt_lang,
            "original_text": text,
            "available": False,
            "error": str(e),
            "response_time_ms": response_time_ms
        }


async def detect_and_translate(
    text: str,
    target_language: str = "eng_Latn",
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Attempts to detect the source language and translate to target.
    
    Note: This is a simplified heuristic-based detection. For production,
    consider integrating a dedicated language detection model.
    
    Args:
        text: The text to translate
        target_language: Target language code
        tenant_id: Optional tenant identifier for logging
        
    Returns:
        Translation result dictionary
    """
    if not text or not isinstance(text, str):
        return {
            "translated_text": "",
            "detected_lang": "unknown",
            "target_lang": target_language,
            "original_text": text if isinstance(text, str) else "",
            "available": True,
            "error": "Invalid text input."
        }
    
    # Simple heuristic: check for common non-English characters
    detected_lang = "eng_Latn"  # Default assumption
    
    # Check for Spanish characters
    if any(char in text for char in ['¿', '¡', 'ñ', 'á', 'é', 'í', 'ó', 'ú']):
        detected_lang = "spa_Latn"
    # Check for Chinese characters
    elif any('\u4e00' <= char <= '\u9fff' for char in text):
        detected_lang = "zho_Hans"
    # Check for Arabic script
    elif any('\u0600' <= char <= '\u06ff' for char in text):
        detected_lang = "arb_Arab"
    # Check for Cyrillic (Russian)
    elif any('\u0400' <= char <= '\u04ff' for char in text):
        detected_lang = "rus_Cyrl"
    # Check for Devanagari (Hindi)
    elif any('\u0900' <= char <= '\u097f' for char in text):
        detected_lang = "hin_Deva"
    
    log_interaction(
        intent="language_detection",
        tenant_id=tenant_id,
        success=True,
        detected_lang=detected_lang,
        text_preview=sanitize_for_logging(text[:50])
    )
    
    result = await translate_text(text, detected_lang, target_language, tenant_id)
    result["detected_lang"] = detected_lang
    
    return result


async def batch_translate(
    texts: List[str],
    source_language: str = "eng_Latn",
    target_language: str = "spa_Latn",
    tenant_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Translate multiple texts at once.
    
    Args:
        texts: List of strings to translate
        source_language: Source language code
        target_language: Target language code
        tenant_id: Optional tenant identifier for logging
        
    Returns:
        List of translation result dictionaries
    """
    if not texts or not isinstance(texts, list):
        log_interaction(
            intent="batch_translation",
            tenant_id=tenant_id,
            success=False,
            error="Invalid texts input"
        )
        return []
    
    # Filter valid texts and limit batch size
    valid_texts = [t for t in texts if isinstance(t, str) and t.strip()]
    if len(valid_texts) > 50:  # Batch size limit
        valid_texts = valid_texts[:50]
        log_interaction(
            intent="batch_translation",
            tenant_id=tenant_id,
            success=None,
            details=f"Batch size limited to 50 texts"
        )
    
    if not valid_texts:
        log_interaction(
            intent="batch_translation",
            tenant_id=tenant_id,
            success=False,
            error="No valid texts in batch"
        )
        return []
    
    start_time = time.time()
    results = []
    
    for text in valid_texts:
        result = await translate_text(text, source_language, target_language, tenant_id)
        results.append(result)
    
    response_time_ms = int((time.time() - start_time) * 1000)
    
    log_interaction(
        intent="batch_translation",
        tenant_id=tenant_id,
        success=True,
        response_time_ms=response_time_ms,
        batch_size=len(valid_texts),
        source_lang=normalize_language_code(source_language),
        target_lang=normalize_language_code(target_language)
    )
    
    return results


def get_civic_phrase(
    phrase_key: str,
    language: str = "eng_Latn"
) -> str:
    """
    Get a pre-translated civic phrase for common queries.
    
    Args:
        phrase_key: Key for the civic phrase (e.g., "voting_location")
        language: Target language code
        
    Returns:
        Translated phrase or empty string if not found
    """
    if not phrase_key or not isinstance(phrase_key, str):
        return ""
    
    lang_code = normalize_language_code(language)
    phrase = CIVIC_PHRASES.get(lang_code, {}).get(phrase_key, "")
    
    if phrase:
        log_interaction(
            intent="civic_phrase_lookup",
            success=True,
            phrase_key=phrase_key,
            language=lang_code
        )
    
    return phrase