# models/layoutlm/layoutlm_utils.py

"""
LayoutLM Model Utilities for PENNY Project
Handles document structure extraction and field recognition for civic forms and documents.
Provides async document processing with structured error handling and logging.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from io import BytesIO

# --- Logging Imports ---
from app.logging_utils import log_interaction, sanitize_for_logging

# --- Model Loader Import ---
try:
    from app.model_loader import load_model_pipeline
    MODEL_LOADER_AVAILABLE = True
except ImportError:
    MODEL_LOADER_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning("Could not import load_model_pipeline. LayoutLM service unavailable.")

# Global variable to store the loaded pipeline for re-use
LAYOUTLM_PIPELINE: Optional[Any] = None
AGENT_NAME = "penny-doc-agent"
INITIALIZATION_ATTEMPTED = False


def _initialize_layoutlm_pipeline() -> bool:
    """
    Initializes the LayoutLM pipeline only once.
    
    Returns:
        bool: True if initialization succeeded, False otherwise.
    """
    global LAYOUTLM_PIPELINE, INITIALIZATION_ATTEMPTED
    
    if INITIALIZATION_ATTEMPTED:
        return LAYOUTLM_PIPELINE is not None
    
    INITIALIZATION_ATTEMPTED = True
    
    if not MODEL_LOADER_AVAILABLE:
        log_interaction(
            intent="layoutlm_initialization",
            success=False,
            error="model_loader unavailable"
        )
        return False
    
    try:
        log_interaction(
            intent="layoutlm_initialization",
            success=None,
            details=f"Loading {AGENT_NAME}"
        )
        
        LAYOUTLM_PIPELINE = load_model_pipeline(AGENT_NAME)
        
        if LAYOUTLM_PIPELINE is None:
            log_interaction(
                intent="layoutlm_initialization",
                success=False,
                error="Pipeline returned None"
            )
            return False
        
        log_interaction(
            intent="layoutlm_initialization",
            success=True,
            details=f"Model {AGENT_NAME} loaded successfully"
        )
        return True
        
    except Exception as e:
        log_interaction(
            intent="layoutlm_initialization",
            success=False,
            error=str(e)
        )
        return False


# Attempt initialization at module load
_initialize_layoutlm_pipeline()


def is_layoutlm_available() -> bool:
    """
    Check if LayoutLM service is available.
    
    Returns:
        bool: True if LayoutLM pipeline is loaded and ready.
    """
    return LAYOUTLM_PIPELINE is not None


async def extract_document_data(
    file_bytes: bytes,
    file_name: str,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Processes a document (e.g., PDF, image) using LayoutLM to extract structured data.

    Args:
        file_bytes: The raw bytes of the uploaded file.
        file_name: The original name of the file (e.g., form.pdf).
        tenant_id: Optional tenant identifier for logging.

    Returns:
        A dictionary containing:
            - status (str): "success" or "error"
            - extracted_fields (dict, optional): Extracted key-value pairs
            - available (bool): Whether the service was available
            - message (str, optional): Error message if extraction failed
            - response_time_ms (int, optional): Processing time in milliseconds
    """
    start_time = time.time()
    
    global LAYOUTLM_PIPELINE

    # Check availability
    if not is_layoutlm_available():
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=False,
            error="LayoutLM pipeline not available",
            fallback_used=True
        )
        return {
            "status": "error",
            "available": False,
            "message": "Document processing is temporarily unavailable. Please try uploading your document again in a moment!"
        }

    # Validate inputs
    if not file_bytes or not isinstance(file_bytes, bytes):
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=False,
            error="Invalid file_bytes provided"
        )
        return {
            "status": "error",
            "available": True,
            "message": "I didn't receive valid document data. Could you try uploading your file again?"
        }
    
    if not file_name or not isinstance(file_name, str):
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=False,
            error="Invalid file_name provided"
        )
        return {
            "status": "error",
            "available": True,
            "message": "I need a valid file name to process your document. Please try again!"
        }

    # Check file size (prevent processing extremely large files)
    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > 50:  # 50 MB limit
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=False,
            error=f"File too large: {file_size_mb:.2f}MB",
            file_name=sanitize_for_logging(file_name)
        )
        return {
            "status": "error",
            "available": True,
            "message": f"Your file is too large ({file_size_mb:.1f}MB). Please upload a document smaller than 50MB."
        }

    try:
        # --- Real-world step (PLACEHOLDER) ---
        # In a real implementation, you would:
        # 1. Use a library (e.g., PyMuPDF, pdf2image) to convert PDF bytes to image(s).
        # 2. Use PIL/Pillow to load the image(s) from bytes.
        # 3. Pass the PIL Image object to the LayoutLM pipeline.
        
        # For now, we use a simple mock placeholder for the image object:
        image_mock = {
            "file_name": file_name,
            "byte_size": len(file_bytes)
        }

        loop = asyncio.get_event_loop()
        
        # Run model inference in thread executor
        results = await loop.run_in_executor(
            None,
            lambda: LAYOUTLM_PIPELINE(image_mock)
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Validate results
        if not results or not isinstance(results, list):
            log_interaction(
                intent="layoutlm_extract",
                tenant_id=tenant_id,
                success=False,
                error="Unexpected model output format",
                response_time_ms=response_time_ms,
                file_name=sanitize_for_logging(file_name)
            )
            return {
                "status": "error",
                "available": True,
                "message": "I had trouble understanding the document structure. The file might be corrupted or in an unsupported format."
            }
        
        # Convert model output (list of dicts) into a clean key-value format
        extracted_data = {}
        for item in results:
            if isinstance(item, dict) and 'label' in item and 'text' in item:
                label_key = item['label'].lower().strip()
                text_value = str(item['text']).strip()
                
                # Avoid empty values
                if text_value:
                    extracted_data[label_key] = text_value
        
        # Log slow processing
        if response_time_ms > 10000:  # 10 seconds
            log_interaction(
                intent="layoutlm_extract_slow",
                tenant_id=tenant_id,
                success=True,
                response_time_ms=response_time_ms,
                details="Slow document processing detected",
                file_name=sanitize_for_logging(file_name)
            )
        
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=True,
            response_time_ms=response_time_ms,
            file_name=sanitize_for_logging(file_name),
            fields_extracted=len(extracted_data)
        )
        
        return {
            "status": "success",
            "extracted_fields": extracted_data,
            "available": True,
            "response_time_ms": response_time_ms,
            "fields_count": len(extracted_data)
        }

    except asyncio.CancelledError:
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=False,
            error="Processing cancelled",
            file_name=sanitize_for_logging(file_name)
        )
        raise
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        
        log_interaction(
            intent="layoutlm_extract",
            tenant_id=tenant_id,
            success=False,
            error=str(e),
            response_time_ms=response_time_ms,
            file_name=sanitize_for_logging(file_name),
            fallback_used=True
        )
        
        return {
            "status": "error",
            "available": False,
            "message": f"I encountered an issue while processing your document. Please try again, or contact support if this continues!",
            "error": str(e),
            "response_time_ms": response_time_ms
        }


async def validate_document_fields(
    extracted_fields: Dict[str, str],
    required_fields: List[str],
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates that required fields were successfully extracted from a document.
    
    Args:
        extracted_fields: Dictionary of extracted field names and values.
        required_fields: List of field names that must be present.
        tenant_id: Optional tenant identifier for logging.
    
    Returns:
        A dictionary containing:
            - valid (bool): Whether all required fields are present
            - missing_fields (list): List of missing required fields
            - present_fields (list): List of found required fields
    """
    if not isinstance(extracted_fields, dict):
        log_interaction(
            intent="layoutlm_validate",
            tenant_id=tenant_id,
            success=False,
            error="Invalid extracted_fields type"
        )
        return {
            "valid": False,
            "missing_fields": required_fields,
            "present_fields": []
        }
    
    if not isinstance(required_fields, list):
        log_interaction(
            intent="layoutlm_validate",
            tenant_id=tenant_id,
            success=False,
            error="Invalid required_fields type"
        )
        return {
            "valid": False,
            "missing_fields": [],
            "present_fields": []
        }
    
    # Normalize field names for case-insensitive comparison
    extracted_keys = {k.lower().strip() for k in extracted_fields.keys()}
    required_keys = {f.lower().strip() for f in required_fields}
    
    present_fields = [f for f in required_fields if f.lower().strip() in extracted_keys]
    missing_fields = [f for f in required_fields if f.lower().strip() not in extracted_keys]
    
    is_valid = len(missing_fields) == 0
    
    log_interaction(
        intent="layoutlm_validate",
        tenant_id=tenant_id,
        success=is_valid,
        details=f"Validated {len(present_fields)}/{len(required_fields)} required fields"
    )
    
    return {
        "valid": is_valid,
        "missing_fields": missing_fields,
        "present_fields": present_fields
    }