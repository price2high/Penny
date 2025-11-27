# Hugging Face Spaces Deployment Guide

This document outlines the changes made to prepare PENNY for Hugging Face Spaces deployment.

## Changes Made

### 1. Created `app.py` Entry Point
- **File**: `app.py` (root directory)
- **Purpose**: Hugging Face Spaces requires an `app.py` file at the root level
- **Function**: Imports and exposes the FastAPI app from `app/main.py`

### 2. Updated `README.md`
- **Added**: YAML frontmatter for Hugging Face Spaces configuration
- **SDK**: Set to `docker` (uses Dockerfile for deployment)
- **Configuration**:
  ```yaml
  title: PENNY - Civic Engagement AI Assistant
  emoji: 🤖
  colorFrom: blue
  colorTo: purple
  sdk: docker
  sdk_version: latest
  app_file: app.py
  pinned: false
  license: mit
  ```

### 3. Updated `Dockerfile`
- **Added**: Copy instruction for `app.py` file
- **Note**: The Dockerfile already had all necessary components

### 4. Verified `requirements.txt`
- **Status**: Compatible with Hugging Face Spaces
- **Note**: All dependencies are standard Python packages available on PyPI

## Deployment Steps

### Option 1: Using Hugging Face Spaces Web Interface

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Fill in:
   - **Space name**: `penny-civic-assistant` (or your preferred name)
   - **SDK**: Docker
   - **Visibility**: Public or Private
4. Push your code to the Space repository
5. Set environment variables in Space settings:
   - `AZURE_MAPS_KEY`: Your Azure Maps API key
   - `ENVIRONMENT`: `production` (optional)
   - `DEBUG_MODE`: `false` (optional)

### Option 2: Using Git Push

```bash
# Clone your Space repository
git clone https://huggingface.co/spaces/your-username/penny-civic-assistant
cd penny-civic-assistant

# Copy all files from this project
cp -r /path/to/Penny/* .

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

## Environment Variables

Set these in your Hugging Face Space settings (Settings → Variables):

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `AZURE_MAPS_KEY` | Azure Maps API key for weather features | Yes | - |
| `ENVIRONMENT` | Deployment environment | No | `development` |
| `DEBUG_MODE` | Enable debug endpoints | No | `false` |
| `ALLOWED_ORIGINS` | CORS allowed origins | No | `*` |
| `LOG_LEVEL` | Logging level | No | `INFO` |

## Troubleshooting

### Config Error
If you see a config error:
1. Verify `app.py` exists at the root
2. Check that `README.md` has valid YAML frontmatter
3. Ensure `Dockerfile` is present and valid
4. Verify all required files are committed

### Import Errors
If you see import errors:
1. Check that all files in `app/` and `models/` are present
2. Verify `requirements.txt` includes all dependencies
3. Check build logs for missing packages

### Environment Variable Issues
- Weather features will be limited if `AZURE_MAPS_KEY` is not set
- The app will still start but will log warnings
- Set variables in Space settings, not in `.env` file

## Testing Locally

Before deploying, test locally:

```bash
# Build Docker image
docker build -t penny-test .

# Run container
docker run -p 8000:8000 \
  -e AZURE_MAPS_KEY=your_key \
  penny-test

# Test endpoint
curl http://localhost:8000/health
```

## Additional Notes

- The app gracefully handles missing environment variables
- Weather features require `AZURE_MAPS_KEY` but are optional
- All data files in `data/` directory are included in deployment
- Model configuration is in `models/model_config.json`

## Support

For issues with Hugging Face Spaces deployment:
1. Check build logs in the Space interface
2. Review application logs
3. Verify all files are present and correctly formatted

