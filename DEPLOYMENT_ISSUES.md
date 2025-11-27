# Deployment Issues Found & Fixes

## 🚨 Critical Issues

### 1. **Router Prefix Mismatch** ⚠️
- **Issue**: Router has prefix `/api`, so endpoint is `/api/chat`
- **Frontend expects**: `/chat` 
- **Fix**: Either remove prefix or add `/chat` endpoint at root level

### 2. **Gradio App Import Errors** ❌
- **Issue**: `gradio_app.py` imports functions that don't exist:
  - `route_query` - doesn't exist
  - `geocode_address`, `get_user_location` - need to check
  - `setup_logger` - doesn't exist
  - `get_weather_info`, `search_events` - need to check event_weather.py
  - `search_officials`, `search_resources` - need to check tool_agent.py
  - `initialize_models` - doesn't exist
  - `classify_intent` - should be `classify_intent_detailed`

### 3. **Handler.py Class Reference** ❌
- **Issue**: References `PennyOrchestrator` class which doesn't exist
- **Should use**: `run_orchestrator` function instead

### 4. **Missing __init__.py Files** ⚠️
- **Issue**: May need `__init__.py` in app/ for proper imports

## ✅ What Works

- FastAPI app structure is correct
- Router endpoint `/api/chat` exists and works
- Orchestrator function `run_orchestrator` exists
- Model loader is properly structured
- Data files are in place

## 🔧 Required Fixes

1. Fix router to expose `/chat` endpoint (or update frontend config)
2. Fix gradio_app.py imports
3. Fix handler.py to use correct orchestrator function
4. Test all imports

