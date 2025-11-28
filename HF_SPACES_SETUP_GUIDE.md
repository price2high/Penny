# 🤗 Hugging Face Spaces Setup Guide for PENNY

Complete step-by-step guide to deploy PENNY to Hugging Face Spaces.

---

## 📋 Prerequisites

Before you begin, ensure you have:

1. ✅ **Hugging Face Account** - Sign up at [huggingface.co](https://huggingface.co/join)
2. ✅ **Git** - Installed on your local machine
3. ✅ **Azure Maps API Key** (if you want weather features to work)
4. ✅ **HF Token** (optional, for model inference API - can be added later)

---

## 🚀 Step-by-Step Setup

### Step 1: Create a New Space

1. **Go to Hugging Face Spaces**
   - Navigate to: https://huggingface.co/spaces
   - Click **"Create new Space"**

2. **Configure Space Settings**
   ```
   Owner: [your-username or organization]
   Space name: penny-civic-assistant (or your preferred name)
   SDK: Docker
   License: MIT (or your preference)
   Visibility: Public or Private (your choice)
   ```

3. **Click "Create Space"**

---

### Step 2: Clone the Space Repository

After creating the Space, Hugging Face will provide you with repository URLs.

**Option A: HTTPS (Easier)**
```bash
git clone https://huggingface.co/spaces/your-username/penny-civic-assistant
cd penny-civic-assistant
```

**Option B: SSH (If you have SSH keys configured)**
```bash
git clone git@hf.co:your-username/penny-civic-assistant
cd penny-civic-assistant
```

---

### Step 3: Prepare Files for Upload

You can either use the provided script or manually copy files.

**Option A: Using the Prepared Script**
```bash
# From your PENNY project directory
./prepare_hf_upload.sh /path/to/penny-civic-assistant
```

**Option B: Manual Copy**
```bash
# From your PENNY project directory
cp app.py penny-civic-assistant/
cp README.md penny-civic-assistant/
cp Dockerfile penny-civic-assistant/
cp requirements.txt penny-civic-assistant/
cp -r app/ penny-civic-assistant/
cp -r models/ penny-civic-assistant/
cp -r data/ penny-civic-assistant/
```

**Required Files Checklist:**
- ✅ `app.py`
- ✅ `README.md` (with YAML frontmatter)
- ✅ `Dockerfile`
- ✅ `requirements.txt`
- ✅ `app/` directory (all Python files)
- ✅ `models/` directory (with `model_config.json`)
- ✅ `data/events/` directory (city JSON files)
- ✅ `data/resources/` directory (city JSON files)

---

### Step 4: Verify README.md Frontmatter

Make sure your `README.md` has the correct YAML frontmatter at the top:

```yaml
---
title: PENNY - Civic Engagement AI Assistant
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: latest
app_file: app.py
pinned: false
license: mit
---
```

This tells Hugging Face Spaces:
- Use **Docker SDK**
- Entry point is **`app.py`**
- Display settings for the Space

---

### Step 5: Commit and Push Files

```bash
cd penny-civic-assistant

# Add all files
git add .

# Commit
git commit -m "Initial PENNY deployment"

# Push to Hugging Face
git push
```

**Note:** If prompted for credentials:
- **Username**: Your Hugging Face username
- **Password**: Your Hugging Face Access Token (not your account password)
  - Get token at: https://huggingface.co/settings/tokens
  - Create a token with **"Write"** permissions

---

### Step 6: Configure Environment Variables

Environment variables are critical for PENNY to work properly.

1. **Go to your Space Settings**
   - Navigate to your Space on Hugging Face
   - Click **"Settings"** tab (top right)
   - Scroll to **"Variables and secrets"** section

2. **Add Required Variables**

   Click **"New variable"** for each:

   | Variable Name | Value | Required | Description |
   |---------------|-------|----------|-------------|
   | `AZURE_MAPS_KEY` | `your-azure-maps-key` | **Yes** | Azure Maps API key for weather service |
   | `PORT` | `8000` | No | Application port (default: 8000) |
   | `WORKERS` | `1` | No | Uvicorn workers (default: 1) |
   | `ENVIRONMENT` | `production` | No | Environment type |
   | `DEBUG_MODE` | `false` | No | Debug mode (set to `true` for debugging) |
   | `ALLOWED_ORIGINS` | `*` | No | CORS allowed origins |
   | `LOG_LEVEL` | `INFO` | No | Logging level |
   | `HF_TOKEN` | `your-hf-token` | No | Hugging Face API token (optional, for model inference) |

3. **Save Variables**
   - Click **"Save"** after adding each variable
   - Variables will be available after the next build

**⚠️ Important:**
- Do **NOT** commit `.env` files to the repository
- Secrets should only be set via Hugging Face Space variables
- Changes to variables require a rebuild to take effect

---

### Step 7: Monitor Build Process

After pushing code:

1. **Check Build Status**
   - Go to your Space page
   - Click **"Logs"** tab
   - Watch the build process

2. **Build Time**
   - Initial build: ~5-15 minutes (downloads dependencies)
   - Subsequent builds: ~3-10 minutes (with Docker layer caching)

3. **Common Build Stages**
   ```
   Building Docker image...
   Installing dependencies...
   Starting application...
   ```

4. **Check for Errors**
   - ✅ Green checkmark = Build successful
   - ❌ Red X = Build failed (check logs)

---

### Step 8: Verify Deployment

Once the build completes:

1. **Test Health Endpoint**
   ```
   https://your-username-penny-civic-assistant.hf.space/health
   ```
   Should return JSON with status information.

2. **Test Root Endpoint**
   ```
   https://your-username-penny-civic-assistant.hf.space/
   ```
   Should return welcome message.

3. **Test Chat Endpoint**
   ```bash
   curl -X POST "https://your-username-penny-civic-assistant.hf.space/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "input": "What is the weather today?",
       "tenant_id": "atlanta_ga"
     }'
   ```

4. **Check API Documentation**
   ```
   https://your-username-penny-civic-assistant.hf.space/docs
   ```
   FastAPI automatic documentation should be available.

---

## 🔧 Configuration Details

### Dockerfile Configuration

Your Dockerfile is already optimized for HF Spaces:
- ✅ Single worker (resource-friendly)
- ✅ Configurable port and workers
- ✅ No non-root user issues
- ✅ Proper health checks

### Port Configuration

Hugging Face Spaces will automatically:
- Expose your application on port 7860 (external)
- Map it to your container's port (8000 by default)
- Handle all routing automatically

You can override with `PORT` environment variable if needed.

---

## 🔑 Getting Required API Keys

### Azure Maps API Key (Required)

1. **Create Azure Account** (if you don't have one)
   - Go to: https://azure.microsoft.com/free/
   - Sign up for free account

2. **Create Azure Maps Resource**
   - Go to Azure Portal: https://portal.azure.com
   - Search for "Azure Maps"
   - Click "Create"
   - Fill in:
     - **Name**: penny-maps (or your choice)
     - **Subscription**: Your subscription
     - **Resource Group**: Create new or use existing
     - **Pricing tier**: S0 (Standard)
   - Click "Create"

3. **Get API Key**
   - Navigate to your Azure Maps resource
   - Go to **"Authentication"** section
   - Copy **"Primary Key"** or **"Secondary Key"**
   - Use this as `AZURE_MAPS_KEY` environment variable

**Note:** Free tier includes 5,000 requests/month. Perfect for testing!

### Hugging Face Token (Optional)

Only needed if you want to use HF Inference API for models:

1. **Go to Settings**
   - https://huggingface.co/settings/tokens

2. **Create New Token**
   - Click "New token"
   - Name: `penny-deployment`
   - Type: **Read** (for public models) or **Write** (if using private models)
   - Click "Generate"

3. **Copy Token**
   - Copy the token immediately (you won't see it again)
   - Use as `HF_TOKEN` environment variable

---

## 🐛 Troubleshooting

### Build Fails

**Error: "Module not found"**
- ✅ Check `requirements.txt` includes all dependencies
- ✅ Verify all Python files are in correct directories
- ✅ Check `__init__.py` files exist in all packages

**Error: "Port already in use"**
- ✅ Ensure `PORT` environment variable is set correctly
- ✅ Default port 8000 should work automatically

**Error: "Permission denied"**
- ✅ Verify Dockerfile doesn't use non-root user
- ✅ Check file permissions (HF Spaces handles this)

### Runtime Errors

**Error: "AZURE_MAPS_KEY not configured"**
- ✅ Add `AZURE_MAPS_KEY` in Space settings → Variables
- ✅ Wait for rebuild after adding variables
- ✅ Weather features will be limited but app will still run

**Error: "model_config.json not found"**
- ✅ Verify `models/model_config.json` exists
- ✅ Check file was copied correctly
- ✅ Ensure file is in `models/` directory

**Error: "Import errors"**
- ✅ Check all `__init__.py` files are present
- ✅ Verify package structure matches imports
- ✅ Check build logs for specific import errors

### Application Won't Start

1. **Check Logs**
   - Go to Space → "Logs" tab
   - Look for error messages
   - Check startup sequence

2. **Verify Environment Variables**
   - Ensure all required variables are set
   - Check variable names match exactly (case-sensitive)

3. **Test Health Endpoint**
   - Should return 200 OK with status JSON
   - If 503, check application logs

---

## 📊 Resource Considerations

### Free Tier Limits

Hugging Face Spaces free tier includes:
- **CPU**: Limited CPU time
- **Memory**: ~16GB RAM
- **Disk**: ~50GB storage
- **Sleep**: Spaces sleep after inactivity

### Optimization Tips

1. **Single Worker** (already configured)
   - Uses less memory
   - Sufficient for most use cases

2. **Lazy Model Loading** (already implemented)
   - Models only load when needed
   - Saves memory and startup time

3. **API-Based Models** (already configured)
   - Uses Hugging Face Inference API
   - No local model storage needed
   - Faster startup

---

## 🔄 Updating Your Deployment

### Making Changes

1. **Edit Files Locally**
   ```bash
   cd penny-civic-assistant
   # Make your changes
   ```

2. **Commit and Push**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push
   ```

3. **Monitor Build**
   - Builds trigger automatically on push
   - Check "Logs" tab for status

### Updating Environment Variables

1. **Go to Settings → Variables**
2. **Edit or Add Variables**
3. **Save Changes**
4. **Rebuild Required**
   - Click "Settings" → "Rebuild Space"
   - Or push a commit (triggers rebuild)

---

## 📝 Quick Reference

### Space URL Structure
```
https://your-username-penny-civic-assistant.hf.space
```

### Important Endpoints
- **Root**: `/`
- **Health**: `/health`
- **Chat**: `/chat` (POST)
- **API Docs**: `/docs`
- **Cities**: `/cities` (GET)
- **Weather**: `/weather/{tenant_id}` (GET)

### Required Environment Variables
- `AZURE_MAPS_KEY` (required)
- All others are optional

### Git Commands
```bash
# Clone
git clone https://huggingface.co/spaces/username/space-name

# Add files
git add .

# Commit
git commit -m "Message"

# Push
git push
```

---

## ✅ Deployment Checklist

Before deploying, verify:

- [ ] Space created on Hugging Face
- [ ] Repository cloned locally
- [ ] All files copied to Space repository
- [ ] `README.md` has correct YAML frontmatter
- [ ] `models/model_config.json` exists
- [ ] All data files present
- [ ] `AZURE_MAPS_KEY` environment variable set
- [ ] Code committed and pushed
- [ ] Build completes successfully
- [ ] Health endpoint returns 200 OK
- [ ] Chat endpoint tested and working

---

## 🎉 Success Indicators

You'll know deployment is successful when:

1. ✅ **Build Status**: Green checkmark in Logs
2. ✅ **Health Check**: `/health` returns status JSON
3. ✅ **API Docs**: `/docs` shows FastAPI documentation
4. ✅ **Chat Works**: Can send messages and get responses
5. ✅ **No Errors**: Logs show no critical errors

---

## 📚 Additional Resources

- **Hugging Face Spaces Docs**: https://huggingface.co/docs/hub/spaces
- **Docker Spaces Guide**: https://huggingface.co/docs/hub/spaces-sdks-docker
- **PENNY Deployment Docs**: See `HUGGINGFACE_DEPLOYMENT.md`
- **File Checklist**: See `HF_SPACES_FILES.md`

---

## 🆘 Need Help?

If you encounter issues:

1. Check **"Logs"** tab in your Space
2. Review **"HF_DEPLOYMENT_READINESS.md"** for verification
3. Check **"DEPLOYMENT_BLOCKERS_FIXED.md"** for common fixes
4. Review error messages in build logs
5. Verify environment variables are set correctly

---

**Good luck with your deployment! 🚀**

