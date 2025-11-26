# app/main.py
"""
🤖 PENNY - People's Engagement Network Navigator for You
FastAPI Entry Point with Azure-Ready Configuration

This is Penny's front door. She loads her environment, registers all her endpoints,
and makes sure she's ready to help residents find what they need.

MISSION: Connect residents to civic resources through a warm, multilingual interface
that removes barriers and empowers communities.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os
from dotenv import load_dotenv
import pathlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# --- LOGGING CONFIGURATION (Must be set up before other imports) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- CRITICAL: FORCE .ENV LOADING BEFORE ANY OTHER IMPORTS ---
# Determine the absolute path to the project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent

# Load environment variables into the active Python session IMMEDIATELY
# This ensures Azure Maps keys, API tokens, and model paths are available
try:
    load_dotenv(PROJECT_ROOT / ".env")
    
    # Verify critical environment variables are loaded
    REQUIRED_ENV_VARS = ["AZURE_MAPS_KEY"]
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        logger.warning(f"⚠️  WARNING: Missing required environment variables: {missing_vars}")
        logger.warning(f"📁 Looking for .env file at: {PROJECT_ROOT / '.env'}")
    else:
        logger.info("✅ Environment variables loaded successfully")
except Exception as e:
    logger.error(f"❌ Error loading environment variables: {e}")
    logger.error(f"📁 Expected .env location: {PROJECT_ROOT / '.env'}")

# --- NOW SAFE TO IMPORT MODULES THAT DEPEND ON ENV VARS ---
try:
    from app.weather_agent import get_weather_for_location
    from app.router import router as api_router
    from app.location_utils import (
        initialize_location_system,
        get_all_supported_cities,
        validate_city_data_files,
        SupportedCities,
        get_city_coordinates
    )
except ImportError as e:
    logger.error(f"❌ Critical import error: {e}")
    logger.error("⚠️  Penny cannot start without core modules")
    sys.exit(1)

# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(
    title="PENNY - Civic Engagement Assistant",
    description=(
        "💛 Multilingual civic chatbot connecting residents with local services, "
        "government programs, and community resources.\n\n"
        "**Powered by:**\n"
        "- Transformer models for natural language understanding\n"
        "- Azure ML infrastructure for scalable deployment\n"
        "- 27-language translation support\n"
        "- Real-time weather integration\n"
        "- Multi-city civic resource databases\n\n"
        "**Supported Cities:** Atlanta, Birmingham, Chesterfield, El Paso, Providence, Seattle"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Penny Support",
        "email": "support@pennyai.example"
    },
    license_info={
        "name": "Proprietary",
    }
)

# --- CORS MIDDLEWARE (Configure for your deployment) ---
# Production: Update allowed_origins to restrict to specific domains
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- APPLICATION STATE (For health checks and monitoring) ---
app.state.location_system_healthy = False
app.state.startup_time = None
app.state.startup_errors: List[str] = []

# --- GLOBAL EXCEPTION HANDLER ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    🛡️ Catches any unhandled exceptions and returns a user-friendly response.
    Logs full error details for debugging while keeping responses safe for users.
    
    Penny stays helpful even when things go wrong!
    
    Args:
        request: FastAPI request object
        exc: The unhandled exception
        
    Returns:
        JSONResponse with error details (sanitized for production)
    """
    logger.error(
        f"Unhandled exception on {request.url.path} | "
        f"method={request.method} | "
        f"error={exc}",
        exc_info=True
    )
    
    # Check if debug mode is enabled
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An unexpected error occurred. Penny's on it!",
            "message": "Our team has been notified and we're working to fix this.",
            "detail": str(exc) if debug_mode else None,
            "request_path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# --- STARTUP EVENT ---
@app.on_event("startup")
async def startup_event() -> None:
    """
    🚀 Runs when Penny wakes up.
    
    Responsibilities:
    1. Validate environment configuration
    2. Initialize location/city systems
    3. Verify data files exist
    4. Log system status
    """
    try:
        app.state.startup_time = datetime.utcnow()
        app.state.startup_errors = []
        
        logger.info("=" * 60)
        logger.info("🤖 PENNY STARTUP INITIALIZED")
        logger.info("=" * 60)
        
        # --- Environment Info ---
        logger.info(f"📂 Project Root: {PROJECT_ROOT}")
        logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
        logger.info(f"🐍 Python Version: {sys.version.split()[0]}")
        
        # --- Azure Configuration Check ---
        azure_maps_key = os.getenv("AZURE_MAPS_KEY")
        if azure_maps_key:
            logger.info("🗺️  Azure Maps: ✅ Configured")
        else:
            error_msg = "Azure Maps key missing - weather features will be limited"
            logger.warning(f"🗺️  Azure Maps: ⚠️  {error_msg}")
            app.state.startup_errors.append(error_msg)
        
        # --- Initialize Location System ---
        logger.info("🗺️  Initializing location system...")
        try:
            location_system_ready = initialize_location_system()
            app.state.location_system_healthy = location_system_ready
            
            if location_system_ready:
                logger.info("✅ Location system initialized successfully")
                
                # Log supported cities
                cities = SupportedCities.get_all_cities()
                logger.info(f"📍 Supported cities: {len(cities)}")
                for city in cities:
                    logger.info(f"   - {city.full_name} ({city.tenant_id})")
                
                # Validate data files
                validation = validate_city_data_files()
                missing_data = [
                    tid for tid, status in validation.items()
                    if not status["events"] or not status["resources"]
                ]
                if missing_data:
                    error_msg = f"Incomplete data for cities: {missing_data}"
                    logger.warning(f"⚠️  {error_msg}")
                    app.state.startup_errors.append(error_msg)
            else:
                error_msg = "Location system initialization failed"
                logger.error(f"❌ {error_msg}")
                app.state.startup_errors.append(error_msg)
                
        except Exception as e:
            error_msg = f"Error initializing location system: {e}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            app.state.location_system_healthy = False
            app.state.startup_errors.append(error_msg)
        
        # --- Startup Summary ---
        logger.info("=" * 60)
        if app.state.startup_errors:
            logger.warning(f"⚠️  PENNY STARTED WITH {len(app.state.startup_errors)} WARNING(S)")
            for error in app.state.startup_errors:
                logger.warning(f"   - {error}")
        else:
            logger.info("🎉 PENNY IS READY TO HELP RESIDENTS!")
        logger.info("📖 API Documentation: http://localhost:8000/docs")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Critical startup error: {e}", exc_info=True)
        app.state.startup_errors.append(f"Critical startup failure: {e}")

# --- SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    👋 Cleanup tasks when Penny shuts down.
    """
    try:
        logger.info("=" * 60)
        logger.info("👋 PENNY SHUTTING DOWN")
        logger.info("=" * 60)
        
        # Calculate uptime
        if app.state.startup_time:
            uptime = datetime.utcnow() - app.state.startup_time
            logger.info(f"⏱️  Total uptime: {uptime}")
        
        # TODO: Add cleanup tasks here
        # - Close database connections
        # - Save state if needed
        # - Release model resources
        
        logger.info("✅ Shutdown complete. Goodbye for now!")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

# --- ROUTER INCLUSION ---
# All API endpoints defined in router.py are registered here
try:
    app.include_router(api_router)
    logger.info("✅ API router registered successfully")
except Exception as e:
    logger.error(f"❌ Failed to register API router: {e}", exc_info=True)

# ============================================================
# CORE HEALTH & STATUS ENDPOINTS
# ============================================================

@app.get("/", tags=["Health"])
async def root() -> Dict[str, Any]:
    """
    🏠 Root endpoint - confirms Penny is alive and running.
    
    This is the first thing users/load balancers will hit.
    Penny always responds with warmth, even to bots! 💛
    
    Returns:
        Basic status and feature information
    """
    try:
        return {
            "message": "💛 Hi! I'm Penny, your civic engagement assistant.",
            "status": "operational",
            "tagline": "Connecting residents to community resources since 2024",
            "docs": "/docs",
            "api_version": "1.0.0",
            "supported_cities": len(SupportedCities.get_all_cities()),
            "features": [
                "27-language translation",
                "Real-time weather",
                "Community events",
                "Local resource finder",
                "Document processing"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}", exc_info=True)
        return {
            "message": "💛 Hi! I'm Penny, your civic engagement assistant.",
            "status": "degraded",
            "error": "Some features may be unavailable"
        }

@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """
    🏥 Comprehensive health check for Azure load balancers and monitoring.
    
    Returns detailed status of all critical components:
    - Environment configuration
    - Location system
    - Data availability
    - API components
    
    Returns:
        JSONResponse with health status (200 = healthy, 503 = degraded)
    """
    try:
        # Calculate uptime
        uptime = None
        if app.state.startup_time:
            uptime_delta = datetime.utcnow() - app.state.startup_time
            uptime = str(uptime_delta).split('.')[0]  # Remove microseconds
        
        # Validate data files
        validation = validate_city_data_files()
        cities_with_full_data = sum(
            1 for v in validation.values()
            if v.get("events", False) and v.get("resources", False)
        )
        total_cities = len(SupportedCities.get_all_cities())
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": uptime,
            "environment": {
                "azure_maps_configured": bool(os.getenv("AZURE_MAPS_KEY")),
                "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true",
                "environment_type": os.getenv("ENVIRONMENT", "development")
            },
            "location_system": {
                "status": "operational" if app.state.location_system_healthy else "degraded",
                "supported_cities": total_cities,
                "cities_with_full_data": cities_with_full_data
            },
            "api_components": {
                "router": "operational",
                "weather_agent": "operational" if os.getenv("AZURE_MAPS_KEY") else "degraded",
                "translation": "operational",
                "document_processing": "operational"
            },
            "startup_errors": app.state.startup_errors if app.state.startup_errors else None,
            "api_version": "1.0.0"
        }
        
        # Determine overall health status
        critical_checks = [
            app.state.location_system_healthy,
            bool(os.getenv("AZURE_MAPS_KEY"))
        ]
        
        all_healthy = all(critical_checks)
        
        if not all_healthy:
            health_status["status"] = "degraded"
            logger.warning(f"Health check: System degraded - {health_status}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_status
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Health check failed",
                "detail": str(e) if os.getenv("DEBUG_MODE", "false").lower() == "true" else None
            }
        )

@app.get("/cities", tags=["Location"])
async def list_supported_cities() -> JSONResponse:
    """
    📍 Lists all cities Penny currently supports.
    
    Returns:
        List of city information including tenant_id and display name.
        Useful for frontend dropdowns and API clients.
    
    Example Response:
        {
            "total": 6,
            "cities": [
                {
                    "tenant_id": "atlanta_ga",
                    "name": "Atlanta, GA",
                    "state": "GA",
                    "data_status": {"events": true, "resources": true}
                }
            ]
        }
    """
    try:
        cities = get_all_supported_cities()
        
        # Add validation status for each city
        validation = validate_city_data_files()
        for city in cities:
            tenant_id = city["tenant_id"]
            city["data_status"] = validation.get(tenant_id, {
                "events": False,
                "resources": False
            })
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "total": len(cities),
                "cities": cities,
                "message": "These are the cities where Penny can help you find resources!",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error listing cities: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Unable to retrieve city list",
                "message": "I'm having trouble loading the city list right now. Please try again in a moment!",
                "detail": str(e) if os.getenv("DEBUG_MODE", "false").lower() == "true" else None,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# ============================================================
# WEATHER ENDPOINTS
# ============================================================

@app.get("/weather_direct", tags=["Weather"])
async def weather_direct_endpoint(lat: float, lon: float) -> JSONResponse:
    """
    🌤️ Direct weather lookup by coordinates.
    
    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
    
    Returns:
        Current weather conditions for the specified location
    
    Example:
        GET /weather_direct?lat=36.8508&lon=-76.2859  (Norfolk, VA)
    """
    # Validate coordinates
    if not (-90 <= lat <= 90):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid latitude",
                "message": "Latitude must be between -90 and 90",
                "provided_value": lat
            }
        )
    if not (-180 <= lon <= 180):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid longitude",
                "message": "Longitude must be between -180 and 180",
                "provided_value": lon
            }
        )
    
    try:
        weather = await get_weather_for_location(lat=lat, lon=lon)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "latitude": lat,
                "longitude": lon,
                "weather": weather,
                "source": "Azure Maps Weather API",
                "message": "Current weather conditions at your location",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Weather lookup failed for ({lat}, {lon}): {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Weather service temporarily unavailable",
                "message": "We're having trouble reaching the weather service. Please try again in a moment.",
                "latitude": lat,
                "longitude": lon,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/weather/{tenant_id}", tags=["Weather"])
async def weather_by_city(tenant_id: str) -> JSONResponse:
    """
    🌤️ Get weather for a supported city by tenant ID.
    
    Args:
        tenant_id: City identifier (e.g., 'atlanta_ga', 'seattle_wa')
    
    Returns:
        Current weather conditions for the specified city
    
    Example:
        GET /weather/atlanta_ga
    """
    try:
        # Get city info
        city_info = SupportedCities.get_city_by_tenant_id(tenant_id)
        if not city_info:
            supported = [c["tenant_id"] for c in get_all_supported_cities()]
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"City not found: {tenant_id}",
                    "message": f"I don't have data for '{tenant_id}' yet. Try one of the supported cities!",
                    "supported_cities": supported,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Get coordinates
        coords = get_city_coordinates(tenant_id)
        if not coords:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "City coordinates not available",
                    "city": city_info.full_name,
                    "tenant_id": tenant_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        lat, lon = coords["lat"], coords["lon"]
        
        weather = await get_weather_for_location(lat=lat, lon=lon)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "city": city_info.full_name,
                "tenant_id": tenant_id,
                "coordinates": {"latitude": lat, "longitude": lon},
                "weather": weather,
                "source": "Azure Maps Weather API",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Weather lookup failed for {tenant_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Weather service temporarily unavailable",
                "message": "We're having trouble getting the weather right now. Please try again in a moment!",
                "tenant_id": tenant_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# ============================================================
# DEBUG ENDPOINTS (Only available in debug mode)
# ============================================================

@app.get("/debug/validation", tags=["Debug"], include_in_schema=False)
async def debug_validation() -> JSONResponse:
    """
    🧪 Debug endpoint: Shows data file validation status.
    Only available when DEBUG_MODE=true
    """
    if os.getenv("DEBUG_MODE", "false").lower() != "true":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Debug endpoints are disabled in production"}
        )
    
    try:
        validation = validate_city_data_files()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "validation": validation,
                "summary": {
                    "total_cities": len(validation),
                    "cities_with_events": sum(1 for v in validation.values() if v.get("events", False)),
                    "cities_with_resources": sum(1 for v in validation.values() if v.get("resources", False))
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Debug validation failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )

@app.get("/debug/env", tags=["Debug"], include_in_schema=False)
async def debug_environment() -> JSONResponse:
    """
    🧪 Debug endpoint: Shows environment configuration.
    Sensitive values are masked. Only available when DEBUG_MODE=true
    """
    if os.getenv("DEBUG_MODE", "false").lower() != "true":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Debug endpoints are disabled in production"}
        )
    
    def mask_sensitive(key: str, value: str) -> str:
        """Masks sensitive environment variables."""
        sensitive_keys = ["key", "secret", "password", "token"]
        if any(s in key.lower() for s in sensitive_keys):
            return f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
        return value
    
    try:
        env_vars = {
            key: mask_sensitive(key, value)
            for key, value in os.environ.items()
            if key.startswith(("AZURE_", "PENNY_", "DEBUG_", "ENVIRONMENT"))
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "environment_variables": env_vars,
                "project_root": str(PROJECT_ROOT),
                "location_system_healthy": app.state.location_system_healthy,
                "startup_errors": app.state.startup_errors,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Debug environment check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )