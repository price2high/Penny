# Files Required for Hugging Face Spaces Deployment

This document lists exactly which files you need to upload to your Hugging Face Space.

## ✅ Required Files (Must Include)

### Root Level Files
```
app.py                          # Entry point for HF Spaces
README.md                       # With YAML frontmatter
Dockerfile                      # Container configuration
requirements.txt                # Python dependencies
```

### Application Code
```
app/
├── main.py                     # FastAPI application
├── orchestrator.py             # Request orchestration
├── router.py                   # API routes
├── tool_agent.py               # Civic data agent
├── weather_agent.py           # Weather service
├── event_weather.py            # Weather + events integration
├── intents.py                  # Intent classification
├── location_utils.py          # Location/city management
├── logging_utils.py            # Logging system
└── model_loader.py             # ML model management
```

### Model Utilities
```
models/
├── __init__.py                 # Models package initialization
├── model_config.json           # Model configuration (REQUIRED)
├── translation/
│   ├── __init__.py
│   └── translation_utils.py
├── sentiment/
│   ├── __init__.py
│   └── sentiment_utils.py
├── bias/
│   ├── __init__.py
│   └── bias_utils.py
├── gemma/
│   ├── __init__.py
│   └── gemma_utils.py
└── layoutlm/
    ├── __init__.py
    └── layoutlm_utils.py
```

### Data Files (City Information)
```
data/
├── events/
│   ├── atlanta_ga.json
│   ├── birmingham_al.json
│   ├── chesterfield_va.json
│   ├── el_paso_tx.json
│   ├── providence_ri.json
│   └── seattle_wa.json
└── resources/
    ├── atlanta_ga.json
    ├── birmingham_al.json
    ├── chesterfield_va.json
    ├── el_paso_tx.json
    ├── providence_ri.json
    └── seattle_wa.json
```

## ❌ Files to EXCLUDE (Do Not Upload)

### Azure-Specific Files
```
azure/                          # Azure ML deployment configs
penny-bias-agent/               # Azure ML agent configs
penny-core-agent/               # Azure ML agent configs
penny-doc-agent/                # Azure ML agent configs
penny-sentiment-agent/          # Azure ML agent configs
penny-translate-agent/          # Azure ML agent configs
```

### Development/Test Files
```
requirements-dev.txt            # Development dependencies
data/test_inputs.json           # Test data
.gitignore                      # Git configuration (optional)
```

### Secrets & Environment
```
.env                            # NEVER upload secrets
.env.*                          # Environment files
*.key                           # Key files
*.pem                           # Certificate files
```

### Optional Data (Can Exclude)
```
data/civic_pdfs/                # PDF files (if not used)
data/embeddings/                # Embedding files (if not used)
```

## 📋 Quick Upload Checklist

Use this checklist when uploading to Hugging Face Spaces:

- [ ] `app.py` (root level)
- [ ] `README.md` (with YAML frontmatter)
- [ ] `Dockerfile`
- [ ] `requirements.txt`
- [ ] `app/` directory (all Python files)
- [ ] `models/` directory (all Python files + `model_config.json`)
- [ ] `data/events/` directory (all JSON files)
- [ ] `data/resources/` directory (all JSON files)

## 🚀 Upload Methods

### Method 1: Git Push (Recommended)
```bash
# Clone your HF Space repository
git clone https://huggingface.co/spaces/your-username/your-space-name
cd your-space-name

# Copy required files
cp /path/to/Penny/app.py .
cp /path/to/Penny/README.md .
cp /path/to/Penny/Dockerfile .
cp /path/to/Penny/requirements.txt .
cp -r /path/to/Penny/app .
cp -r /path/to/Penny/models .
cp -r /path/to/Penny/data/events .
cp -r /path/to/Penny/data/resources .

# Create data directory structure
mkdir -p data/events data/resources
mv events/* data/events/
mv resources/* data/resources/
rmdir events resources

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

### Method 2: Web Interface
1. Go to your Space on Hugging Face
2. Click "Files and versions" tab
3. Upload files one by one or drag-and-drop folders
4. Ensure directory structure matches exactly

### Method 3: Using HF CLI
```bash
# Install HF CLI
pip install huggingface_hub

# Login
huggingface-cli login

# Upload files
cd /path/to/Penny
huggingface-cli upload your-username/your-space-name \
  app.py \
  README.md \
  Dockerfile \
  requirements.txt \
  app/ \
  models/ \
  data/events/ \
  data/resources/
```

## 📁 Final Directory Structure

Your Hugging Face Space should have this structure:

```
your-space/
├── app.py
├── README.md
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py (create if missing)
│   ├── main.py
│   ├── orchestrator.py
│   ├── router.py
│   ├── tool_agent.py
│   ├── weather_agent.py
│   ├── event_weather.py
│   ├── intents.py
│   ├── location_utils.py
│   ├── logging_utils.py
│   └── model_loader.py
├── models/
│   ├── model_config.json
│   ├── translation/
│   │   └── translation_utils.py
│   ├── sentiment/
│   │   └── sentiment_utils.py
│   ├── bias/
│   │   └── bias_utils.py
│   ├── gemma/
│   │   └── gemma_utils.py
│   └── layoutlm/
│       └── layoutlm_utils.py
└── data/
    ├── events/
    │   ├── atlanta_ga.json
    │   ├── birmingham_al.json
    │   ├── chesterfield_va.json
    │   ├── el_paso_tx.json
    │   ├── providence_ri.json
    │   └── seattle_wa.json
    └── resources/
        ├── atlanta_ga.json
        ├── birmingham_al.json
        ├── chesterfield_va.json
        ├── el_paso_tx.json
        ├── providence_ri.json
        └── seattle_wa.json
```

## ⚠️ Important Notes

1. **`models/model_config.json` is REQUIRED** - The app will fail to start without it
2. **Data files are REQUIRED** - The location system needs city data to function
3. **Do NOT upload `.env` files** - Use HF Spaces environment variables instead
4. **`__init__.py` files are included** - All necessary package initialization files are present in `app/` and `models/` directories

## 🔍 Verification

After uploading, verify your Space has:
- ✅ All files listed above
- ✅ Correct directory structure
- ✅ `model_config.json` exists in `models/`
- ✅ All city JSON files exist in `data/events/` and `data/resources/`
- ✅ No `.env` or secret files
- ✅ No Azure-specific directories

## 🐛 Troubleshooting

If deployment fails:
1. Check that `models/model_config.json` exists
2. Verify all data files are present
3. Ensure `app.py` is at root level
4. Check build logs for missing file errors

