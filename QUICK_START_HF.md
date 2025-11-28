# 🚀 Quick Start: Hugging Face Spaces Deployment

Quick reference guide for deploying PENNY to Hugging Face Spaces.

---

## 📝 Quick Checklist

### 1️⃣ Create Space
- Go to: https://huggingface.co/spaces
- Click "Create new Space"
- Set: **SDK = Docker**
- Name: `penny-civic-assistant` (or your choice)

### 2️⃣ Clone Repository
```bash
git clone https://huggingface.co/spaces/your-username/penny-civic-assistant
cd penny-civic-assistant
```

### 3️⃣ Copy Files
From your PENNY project directory:
```bash
cp app.py README.md Dockerfile requirements.txt penny-civic-assistant/
cp -r app/ models/ data/ penny-civic-assistant/
```

**Required Files:**
- ✅ `app.py`
- ✅ `README.md` (with YAML frontmatter)
- ✅ `Dockerfile`
- ✅ `requirements.txt`
- ✅ `app/` (all Python files)
- ✅ `models/` (with `model_config.json`)
- ✅ `data/events/` and `data/resources/`

### 4️⃣ Verify README.md
Check that `README.md` starts with:
```yaml
---
title: PENNY - Civic Engagement AI Assistant
emoji: 🤖
sdk: docker
sdk_version: latest
app_file: app.py
---
```

### 5️⃣ Commit and Push
```bash
cd penny-civic-assistant
git add .
git commit -m "Initial deployment"
git push
```

### 6️⃣ Set Environment Variables
Go to: **Space → Settings → Variables**

**Required:**
- `AZURE_MAPS_KEY` = `your-azure-maps-api-key`

**Optional:**
- `PORT` = `8000`
- `WORKERS` = `1`
- `ENVIRONMENT` = `production`
- `DEBUG_MODE` = `false`

### 7️⃣ Wait for Build
- Check **"Logs"** tab
- Build takes ~5-15 minutes first time
- Watch for errors

### 8️⃣ Test Deployment
After build completes:
- Health: `https://your-username-penny-civic-assistant.hf.space/health`
- Docs: `https://your-username-penny-civic-assistant.hf.space/docs`

---

## 🔑 Getting Azure Maps Key

1. Go to: https://portal.azure.com
2. Create "Azure Maps" resource
3. Get API key from "Authentication" section
4. Use as `AZURE_MAPS_KEY` environment variable

**Free tier:** 5,000 requests/month (perfect for testing!)

---

## 🆘 Common Issues

**Build fails:**
- Check `requirements.txt` has all dependencies
- Verify all files were copied
- Check build logs for specific errors

**Import errors:**
- Verify `__init__.py` files exist in `app/` and `models/`
- Check package structure matches imports

**Weather not working:**
- Add `AZURE_MAPS_KEY` in Space settings
- Wait for rebuild after adding variable

**Port errors:**
- Default port 8000 should work automatically
- HF Spaces handles port mapping

---

## 📚 Full Guide

For detailed instructions, see: **`HF_SPACES_SETUP_GUIDE.md`**

---

## ✅ Success Indicators

- ✅ Build status: Green checkmark
- ✅ `/health` returns JSON
- ✅ `/docs` shows API documentation
- ✅ No errors in logs

---

**That's it! Your Space should be live at:**
```
https://your-username-penny-civic-assistant.hf.space
```

