"""
🤖 PENNY - Hugging Face Spaces Entry Point
This file is required by Hugging Face Spaces to launch the FastAPI application.
It imports and exposes the FastAPI app from app.main.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the FastAPI app from app.main
from app.main import app

# Expose the app for Hugging Face Spaces
# HF Spaces will look for a variable named 'app' or will call this file as a module
__all__ = ["app"]

