# app/model_loader.py
"""
🧠 PENNY Model Loader - Azure-Ready Multi-Model Orchestration

This is Penny's brain loader. She manages multiple specialized models:
- Gemma 7B for conversational reasoning
- NLLB-200 for 27-language translation
- Sentiment analysis for resident wellbeing
- Bias detection for equitable service
- LayoutLM for civic document processing

MISSION: Load AI models efficiently in memory-constrained environments while
maintaining Penny's warm, civic-focused personality across all interactions.

FEATURES:
- Lazy loading (models only load when needed)
- 8-bit quantization for memory efficiency
- GPU/CPU auto-detection
- Model caching and reuse
- Graceful fallbacks for Azure ML deployment
- Memory monitoring and cleanup
"""

import json
import os
import torch
from typing import Dict, Any, Callable, Optional, Union, List
from pathlib import Path
import logging
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    AutoModelForSeq2SeqLM,
    pipeline,
    PreTrainedModel,
    PreTrainedTokenizer
)

# --- LOGGING SETUP ---
logger = logging.getLogger(__name__)

# --- PATH CONFIGURATION (Environment-Aware) ---
# Support both local development and Azure ML deployment
if os.getenv("AZUREML_MODEL_DIR"):
    # Azure ML deployment - models are in AZUREML_MODEL_DIR
    MODEL_ROOT = Path(os.getenv("AZUREML_MODEL_DIR"))
    CONFIG_PATH = MODEL_ROOT / "model_config.json"
    logger.info("☁️ Running in Azure ML environment")
else:
    # Local development - models are in project structure
    PROJECT_ROOT = Path(__file__).parent.parent
    MODEL_ROOT = PROJECT_ROOT / "models"
    CONFIG_PATH = MODEL_ROOT / "model_config.json"
    logger.info("💻 Running in local development environment")

logger.info(f"📂 Model config path: {CONFIG_PATH}")

# ============================================================
# PENNY'S CIVIC IDENTITY & PERSONALITY
# ============================================================

PENNY_SYSTEM_PROMPT = (
    "You are Penny, a smart, civic-focused AI assistant serving local communities. "
    "You help residents navigate city services, government programs, and community resources. "
    "You're warm, professional, accurate, and always stay within your civic mission.\n\n"
    
    "Your expertise includes:\n"
    "- Connecting people with local services (food banks, shelters, libraries)\n"
    "- Translating information into 27 languages\n"
    "- Explaining public programs and eligibility\n"
    "- Guiding residents through civic processes\n"
    "- Providing emergency resources when needed\n\n"
    
    "YOUR PERSONALITY:\n"
    "- Warm and approachable, like a helpful community center staff member\n"
    "- Clear and practical, avoiding jargon\n"
    "- Culturally sensitive and inclusive\n"
    "- Patient with repetition or clarification\n"
    "- Funny when appropriate, but never at anyone's expense\n\n"
    
    "CRITICAL RULES:\n"
    "- When residents greet you by name (e.g., 'Hi Penny'), respond warmly and personally\n"
    "- You are ALWAYS Penny - never ChatGPT, Assistant, Claude, or any other name\n"
    "- If you don't know something, say so clearly and help find the right resource\n"
    "- NEVER make up information about services, eligibility, or contacts\n"
    "- Stay within your civic mission - you don't provide legal, medical, or financial advice\n"
    "- For emergencies, immediately connect to appropriate services (911, crisis lines)\n\n"
)

# --- GLOBAL STATE ---
_MODEL_CACHE: Dict[str, Any] = {}  # Memory-efficient model reuse
_LOAD_TIMES: Dict[str, float] = {}  # Track model loading performance


# ============================================================
# DEVICE MANAGEMENT
# ============================================================

class DeviceType(str, Enum):
    """Supported compute devices."""
    CUDA = "cuda"
    CPU = "cpu"
    MPS = "mps"  # Apple Silicon


def get_optimal_device() -> str:
    """
    🎮 Determines the best device for model inference.
    
    Priority:
    1. CUDA GPU (NVIDIA)
    2. MPS (Apple Silicon)
    3. CPU (fallback)
    
    Returns:
        Device string ("cuda", "mps", or "cpu")
    """
    if torch.cuda.is_available():
        device = DeviceType.CUDA.value
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"🎮 GPU detected: {gpu_name} ({gpu_memory:.1f}GB)")
        return device
    
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = DeviceType.MPS.value
        logger.info("🍎 Apple Silicon (MPS) detected")
        return device
    
    else:
        device = DeviceType.CPU.value
        logger.info("💻 Using CPU for inference")
        logger.warning("⚠️ GPU not available - inference will be slower")
        return device


def get_memory_stats() -> Dict[str, float]:
    """
    📊 Returns current GPU/CPU memory statistics.
    
    Returns:
        Dict with memory stats in GB
    """
    stats = {}
    
    if torch.cuda.is_available():
        stats["gpu_allocated_gb"] = torch.cuda.memory_allocated() / 1e9
        stats["gpu_reserved_gb"] = torch.cuda.memory_reserved() / 1e9
        stats["gpu_total_gb"] = torch.cuda.get_device_properties(0).total_memory / 1e9
    
    # CPU memory (requires psutil)
    try:
        import psutil
        mem = psutil.virtual_memory()
        stats["cpu_used_gb"] = mem.used / 1e9
        stats["cpu_total_gb"] = mem.total / 1e9
        stats["cpu_percent"] = mem.percent
    except ImportError:
        pass
    
    return stats


# ============================================================
# MODEL CLIENT (Individual Model Handler)
# ============================================================

@dataclass
class ModelMetadata:
    """
    📋 Metadata about a loaded model.
    Tracks performance and resource usage.
    """
    name: str
    task: str
    model_name: str
    device: str
    loaded_at: Optional[datetime] = None
    load_time_seconds: Optional[float] = None
    memory_usage_gb: Optional[float] = None
    inference_count: int = 0
    total_inference_time_ms: float = 0.0
    
    @property
    def avg_inference_time_ms(self) -> float:
        """Calculate average inference time."""
        if self.inference_count == 0:
            return 0.0
        return self.total_inference_time_ms / self.inference_count


class ModelClient:
    """
    🤖 Manages a single HuggingFace model with optimized loading and inference.
    
    Features:
    - Lazy loading (load on first use)
    - Memory optimization (8-bit quantization)
    - Performance tracking
    - Graceful error handling
    - Automatic device placement
    """
    
    def __init__(
        self, 
        name: str, 
        model_name: str, 
        task: str, 
        device: str = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize model client (doesn't load the model yet).
        
        Args:
            name: Model identifier (e.g., "penny-core-agent")
            model_name: HuggingFace model ID
            task: Task type (text-generation, translation, etc.)
            device: Target device (auto-detected if None)
            config: Additional model configuration
        """
        self.name = name
        self.model_name = model_name
        self.task = task
        self.device = device or get_optimal_device()
        self.config = config or {}
        self.pipeline = None
        self._load_attempted = False
        self.metadata = ModelMetadata(
            name=name,
            task=task,
            model_name=model_name,
            device=self.device
        )
        
        logger.info(f"📦 Initialized ModelClient: {name}")
        logger.debug(f"   Model: {model_name}")
        logger.debug(f"   Task: {task}")
        logger.debug(f"   Device: {self.device}")
    
    def load_pipeline(self) -> bool:
        """
        🔄 Loads the HuggingFace pipeline with Azure-optimized settings.
        
        Features:
        - 8-bit quantization for large models (saves ~50% memory)
        - Automatic device placement
        - Memory monitoring
        - Cache checking
        
        Returns:
            True if successful, False otherwise
        """
        if self.pipeline is not None:
            logger.debug(f"✅ {self.name} already loaded")
            return True
        
        if self._load_attempted:
            logger.warning(f"⚠️ Previous load attempt failed for {self.name}")
            return False
        
        global _MODEL_CACHE, _LOAD_TIMES
        
        # Check cache first
        if self.name in _MODEL_CACHE:
            logger.info(f"♻️ Using cached pipeline for {self.name}")
            self.pipeline = _MODEL_CACHE[self.name]
            return True
        
        logger.info(f"🔄 Loading {self.name} from HuggingFace...")
        self._load_attempted = True
        
        start_time = datetime.now()
        
        try:
            # === TEXT GENERATION (Gemma 7B, GPT-2, etc.) ===
            if self.task == "text-generation":
                logger.info("   Using 8-bit quantization for memory efficiency...")
                
                # Check if model supports 8-bit loading
                use_8bit = self.device == DeviceType.CUDA.value
                
                if use_8bit:
                    self.pipeline = pipeline(
                        "text-generation",
                        model=self.model_name,
                        tokenizer=self.model_name,
                        device_map="auto",
                        load_in_8bit=True,  # Reduces ~14GB to ~7GB
                        trust_remote_code=True,
                        torch_dtype=torch.float16
                    )
                else:
                    # CPU fallback
                    self.pipeline = pipeline(
                        "text-generation",
                        model=self.model_name,
                        tokenizer=self.model_name,
                        device=-1,  # CPU
                        trust_remote_code=True,
                        torch_dtype=torch.float32
                    )
            
            # === TRANSLATION (NLLB-200, M2M-100, etc.) ===
            elif self.task == "translation":
                self.pipeline = pipeline(
                    "translation",
                    model=self.model_name,
                    device=0 if self.device == DeviceType.CUDA.value else -1,
                    src_lang=self.config.get("default_src_lang", "eng_Latn"),
                    tgt_lang=self.config.get("default_tgt_lang", "spa_Latn")
                )
            
            # === SENTIMENT ANALYSIS ===
            elif self.task == "sentiment-analysis":
                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                    device=0 if self.device == DeviceType.CUDA.value else -1,
                    truncation=True,
                    max_length=512
                )
            
            # === BIAS DETECTION (Zero-Shot Classification) ===
            elif self.task == "bias-detection":
                self.pipeline = pipeline(
                    "zero-shot-classification",
                    model=self.model_name,
                    device=0 if self.device == DeviceType.CUDA.value else -1
                )
            
            # === TEXT CLASSIFICATION (Generic) ===
            elif self.task == "text-classification":
                self.pipeline = pipeline(
                    "text-classification",
                    model=self.model_name,
                    device=0 if self.device == DeviceType.CUDA.value else -1,
                    truncation=True
                )
            
            # === PDF/DOCUMENT EXTRACTION (LayoutLMv3) ===
            elif self.task == "pdf-extraction":
                logger.warning("⚠️ PDF extraction requires additional OCR setup")
                logger.info("   Consider using Azure Form Recognizer as alternative")
                # Placeholder - requires pytesseract/OCR infrastructure
                self.pipeline = None
                return False
            
            else:
                raise ValueError(f"Unknown task type: {self.task}")
            
            # === SUCCESS HANDLING ===
            if self.pipeline is not None:
                # Calculate load time
                load_time = (datetime.now() - start_time).total_seconds()
                self.metadata.loaded_at = datetime.now()
                self.metadata.load_time_seconds = load_time
                
                # Cache the pipeline
                _MODEL_CACHE[self.name] = self.pipeline
                _LOAD_TIMES[self.name] = load_time
                
                # Log memory usage
                mem_stats = get_memory_stats()
                self.metadata.memory_usage_gb = mem_stats.get("gpu_allocated_gb", 0)
                
                logger.info(f"✅ {self.name} loaded successfully!")
                logger.info(f"   Load time: {load_time:.2f}s")
                
                if "gpu_allocated_gb" in mem_stats:
                    logger.info(
                        f"   GPU Memory: {mem_stats['gpu_allocated_gb']:.2f}GB / "
                        f"{mem_stats['gpu_total_gb']:.2f}GB"
                    )
                
                return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load {self.name}: {e}", exc_info=True)
            self.pipeline = None
            return False
    
    def predict(
        self, 
        input_data: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        🎯 Runs inference with the loaded model pipeline.
        
        Features:
        - Automatic pipeline loading
        - Error handling with fallback responses
        - Performance tracking
        - Penny's personality injection (for text-generation)
        
        Args:
            input_data: Text or structured input for the model
            **kwargs: Task-specific parameters
            
        Returns:
            Model output dict with results or error information
        """
        # Track inference start time
        start_time = datetime.now()
        
        # Ensure pipeline is loaded
        if self.pipeline is None:
            success = self.load_pipeline()
            if not success:
                return {
                    "error": f"{self.name} pipeline unavailable",
                    "detail": "Model failed to load. Check logs for details.",
                    "model": self.name
                }
        
        try:
            # === TEXT GENERATION ===
            if self.task == "text-generation":
                # Inject Penny's civic identity
                if not kwargs.get("skip_system_prompt", False):
                    full_prompt = PENNY_SYSTEM_PROMPT + input_data
                else:
                    full_prompt = input_data
                
                # Extract generation parameters with safe defaults
                max_new_tokens = kwargs.get("max_new_tokens", 256)
                temperature = kwargs.get("temperature", 0.7)
                top_p = kwargs.get("top_p", 0.9)
                do_sample = kwargs.get("do_sample", temperature > 0.0)
                
                result = self.pipeline(
                    full_prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=do_sample,
                    return_full_text=False,
                    pad_token_id=self.pipeline.tokenizer.eos_token_id,
                    truncation=True
                )
                
                output = {
                    "generated_text": result[0]["generated_text"],
                    "model": self.name,
                    "success": True
                }
            
            # === TRANSLATION ===
            elif self.task == "translation":
                src_lang = kwargs.get("source_lang", "eng_Latn")
                tgt_lang = kwargs.get("target_lang", "spa_Latn")
                
                result = self.pipeline(
                    input_data,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    max_length=512
                )
                
                output = {
                    "translation": result[0]["translation_text"],
                    "source_lang": src_lang,
                    "target_lang": tgt_lang,
                    "model": self.name,
                    "success": True
                }
            
            # === SENTIMENT ANALYSIS ===
            elif self.task == "sentiment-analysis":
                result = self.pipeline(input_data)
                
                output = {
                    "sentiment": result[0]["label"],
                    "confidence": result[0]["score"],
                    "model": self.name,
                    "success": True
                }
            
            # === BIAS DETECTION ===
            elif self.task == "bias-detection":
                candidate_labels = kwargs.get("candidate_labels", [
                    "neutral and objective",
                    "contains political bias",
                    "uses emotional language",
                    "culturally insensitive"
                ])
                
                result = self.pipeline(
                    input_data,
                    candidate_labels=candidate_labels,
                    multi_label=True
                )
                
                output = {
                    "labels": result["labels"],
                    "scores": result["scores"],
                    "model": self.name,
                    "success": True
                }
            
            # === TEXT CLASSIFICATION ===
            elif self.task == "text-classification":
                result = self.pipeline(input_data)
                
                output = {
                    "label": result[0]["label"],
                    "confidence": result[0]["score"],
                    "model": self.name,
                    "success": True
                }
            
            else:
                output = {
                    "error": f"Task '{self.task}' not implemented",
                    "model": self.name,
                    "success": False
                }
            
            # Track performance
            inference_time = (datetime.now() - start_time).total_seconds() * 1000
            self.metadata.inference_count += 1
            self.metadata.total_inference_time_ms += inference_time
            output["inference_time_ms"] = round(inference_time, 2)
            
            return output
        
        except Exception as e:
            logger.error(f"❌ Inference error in {self.name}: {e}", exc_info=True)
            return {
                "error": "Inference failed",
                "detail": str(e),
                "model": self.name,
                "success": False
            }
    
    def unload(self) -> None:
        """
        🗑️ Unloads the model to free memory.
        Critical for Azure environments with limited resources.
        """
        if self.pipeline is not None:
            logger.info(f"🗑️ Unloading {self.name}...")
            
            # Delete pipeline
            del self.pipeline
            self.pipeline = None
            
            # Remove from cache
            if self.name in _MODEL_CACHE:
                del _MODEL_CACHE[self.name]
            
            # Force GPU memory release
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(f"✅ {self.name} unloaded successfully")
            
            # Log memory stats after unload
            mem_stats = get_memory_stats()
            if "gpu_allocated_gb" in mem_stats:
                logger.info(f"   GPU Memory: {mem_stats['gpu_allocated_gb']:.2f}GB remaining")
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        📊 Returns model metadata and performance stats.
        """
        return {
            "name": self.metadata.name,
            "task": self.metadata.task,
            "model_name": self.metadata.model_name,
            "device": self.metadata.device,
            "loaded": self.pipeline is not None,
            "loaded_at": self.metadata.loaded_at.isoformat() if self.metadata.loaded_at else None,
            "load_time_seconds": self.metadata.load_time_seconds,
            "memory_usage_gb": self.metadata.memory_usage_gb,
            "inference_count": self.metadata.inference_count,
            "avg_inference_time_ms": round(self.metadata.avg_inference_time_ms, 2)
        }


# ============================================================
# MODEL LOADER (Singleton Manager)
# ============================================================

class ModelLoader:
    """
    🎛️ Singleton manager for all Penny's specialized models.
    
    Features:
    - Centralized model configuration
    - Lazy loading (models only load when needed)
    - Memory management
    - Health monitoring
    - Unified access interface
    """
    
    _instance: Optional['ModelLoader'] = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern - only one ModelLoader instance."""
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ModelLoader (only runs once due to singleton).
        
        Args:
            config_path: Path to model_config.json (optional)
        """
        if not hasattr(self, '_models_loaded'):
            self.models: Dict[str, ModelClient] = {}
            self._models_loaded = True
            self._initialization_time = datetime.now()
            
            # Use provided path or default
            config_file = Path(config_path) if config_path else CONFIG_PATH
            
            try:
                logger.info(f"📖 Loading model configuration from {config_file}")
                
                if not config_file.exists():
                    logger.warning(f"⚠️ Configuration file not found: {config_file}")
                    logger.info("   Create model_config.json with your model definitions")
                    return
                
                with open(config_file, "r") as f:
                    config = json.load(f)

                # Initialize ModelClients (doesn't load models yet)
                for model_id, model_info in config.items():
                    self.models[model_id] = ModelClient(
                        name=model_id,
                        model_name=model_info["model_name"],
                        task=model_info["task"],
                        config=model_info.get("config", {})
                    )
                
                logger.info(f"✅ ModelLoader initialized with {len(self.models)} models:")
                for model_id in self.models.keys():
                    logger.info(f"   - {model_id}")

            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON in model_config.json: {e}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize ModelLoader: {e}", exc_info=True)

    def get(self, model_id: str) -> Optional[ModelClient]:
        """
        🎯 Retrieves a configured ModelClient by ID.
        
        Args:
            model_id: Model identifier from config
            
        Returns:
            ModelClient instance or None if not found
        """
        return self.models.get(model_id)

    def list_models(self) -> List[str]:
        """📋 Returns list of all available model IDs."""
        return list(self.models.keys())
    
    def get_loaded_models(self) -> List[str]:
        """📋 Returns list of currently loaded model IDs."""
        return [
            model_id 
            for model_id, client in self.models.items()
            if client.pipeline is not None
        ]
    
    def unload_all(self) -> None:
        """
        🗑️ Unloads all models to free memory.
        Useful for Azure environments when switching workloads.
        """
        logger.info("🗑️ Unloading all models...")
        for model_client in self.models.values():
            model_client.unload()
        logger.info("✅ All models unloaded")
    
    def get_status(self) -> Dict[str, Any]:
        """
        📊 Returns comprehensive status of all models.
        Useful for health checks and monitoring.
        """
        status = {
            "initialization_time": self._initialization_time.isoformat(),
            "total_models": len(self.models),
            "loaded_models": len(self.get_loaded_models()),
            "device": get_optimal_device(),
            "memory": get_memory_stats(),
            "models": {}
        }
        
        for model_id, client in self.models.items():
            status["models"][model_id] = client.get_metadata()
        
        return status


# ============================================================
# PUBLIC INTERFACE (Used by all *_utils.py modules)
# ============================================================

def load_model_pipeline(agent_name: str) -> Callable[..., Dict[str, Any]]:
    """
    🚀 Loads a model client and returns its inference function.
    
    This is the main function used by other modules (translation_utils.py,
    sentiment_utils.py, etc.) to access Penny's models.
    
    Args:
        agent_name: Model ID from model_config.json
        
    Returns:
        Callable inference function
        
    Raises:
        ValueError: If agent_name not found in configuration
        
    Example:
        >>> translator = load_model_pipeline("penny-translate-agent")
        >>> result = translator("Hello world", target_lang="spa_Latn")
    """
    loader = ModelLoader()
    client = loader.get(agent_name)
    
    if client is None:
        available = loader.list_models()
        raise ValueError(
            f"Agent ID '{agent_name}' not found in model configuration. "
            f"Available models: {available}"
        )
    
    # Load the pipeline (lazy loading)
    client.load_pipeline()
    
    # Return a callable wrapper
    def inference_wrapper(input_data, **kwargs):
        return client.predict(input_data, **kwargs)
    
    return inference_wrapper


# === CONVENIENCE FUNCTIONS ===

def get_model_status() -> Dict[str, Any]:
    """
    📊 Returns status of all configured models.
    Useful for health checks and monitoring endpoints.
    """
    loader = ModelLoader()
    return loader.get_status()


def preload_models(model_ids: Optional[List[str]] = None) -> None:
    """
    🚀 Preloads specified models during startup.
    
    Args:
        model_ids: List of model IDs to preload (None = all models)
    """
    loader = ModelLoader()
    
    if model_ids is None:
        model_ids = loader.list_models()
    
    logger.info(f"🚀 Preloading {len(model_ids)} models...")
    
    for model_id in model_ids:
        client = loader.get(model_id)
        if client:
            logger.info(f"   Loading {model_id}...")
            client.load_pipeline()
    
    logger.info("✅ Model preloading complete")


def initialize_model_system() -> bool:
    """
    🏁 Initializes the model system.
    Should be called during app startup.
    
    Returns:
        True if initialization successful
    """
    logger.info("🧠 Initializing Penny's model system...")
    
    try:
        # Initialize singleton
        loader = ModelLoader()
        
        # Log device info
        device = get_optimal_device()
        mem_stats = get_memory_stats()
        
        logger.info(f"✅ Model system initialized")
        logger.info(f"🎮 Compute device: {device}")
        
        if "gpu_total_gb" in mem_stats:
            logger.info(
                f"💾 GPU Memory: {mem_stats['gpu_total_gb']:.1f}GB total"
            )
        
        logger.info(f"📦 {len(loader.models)} models configured")
        
        # Optional: Preload critical models
        # Uncomment to preload models at startup
        # preload_models(["penny-core-agent"])
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize model system: {e}", exc_info=True)
        return False


# ============================================================
# CLI TESTING & DEBUGGING
# ============================================================

if __name__ == "__main__":
    """
    🧪 Test script for model loading and inference.
    Run with: python -m app.model_loader
    """
    print("=" * 60)
    print("🧪 Testing Penny's Model System")
    print("=" * 60)
    
    # Initialize
    loader = ModelLoader()
    print(f"\n📋 Available models: {loader.list_models()}")
    
    # Get status
    status = get_model_status()
    print(f"\n📊 System status:")
    print(json.dumps(status, indent=2, default=str))
    
    # Test model loading (if models configured)
    if loader.models:
        test_model_id = list(loader.models.keys())[0]
        print(f"\n🧪 Testing model: {test_model_id}")
        
        client = loader.get(test_model_id)
        if client:
            print(f"   Loading pipeline...")
            success = client.load_pipeline()
            
            if success:
                print(f"   ✅ Model loaded successfully!")
                print(f"   Metadata: {json.dumps(client.get_metadata(), indent=2, default=str)}")
            else:
                print(f"   ❌ Model loading failed")