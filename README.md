---
title: PENNY - Civic Engagement AI Assistant
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: gradio_app.py
pinned: false
license: mit
---

# 🤖 PENNY - Civic Engagement AI Assistant

**Personal civic Engagement Nurturing Network sYstem**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Azure ML](https://img.shields.io/badge/Azure-ML%20Ready-0078D4.svg)](https://azure.microsoft.com/en-us/services/machine-learning/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 📋 Overview

**PENNY** is a production-grade, AI-powered civic engagement assistant designed to help citizens connect with local government services, community events, and civic resources. Built with Azure ML and FastAPI, Penny provides warm, helpful, and contextually-aware assistance for civic participation.

### ✨ Key Features

- **🏛️ Civic Information**: Local government services, voting info, public meetings
- **📅 Community Events**: Real-time local events discovery and recommendations
- **🌤️ Weather Integration**: Context-aware weather updates with outfit suggestions
- **🌍 Multi-language Support**: Translation services for inclusive access
- **🛡️ Safety & Bias Detection**: Built-in content moderation and bias analysis
- **🔒 Privacy-First**: PII sanitization and secure logging
- **⚡ High Performance**: Async architecture with intelligent caching

---

## 🏗️ Architecture
```
penny-v2/
├── app/                    # Core application logic
│   ├── main.py            # FastAPI entry point
│   ├── orchestrator.py    # Central coordination engine
│   ├── router.py          # API route definitions
│   ├── tool_agent.py      # Civic data & events agent
│   ├── weather_agent.py   # Weather & recommendations
│   ├── intents.py         # Intent classification
│   ├── model_loader.py    # ML model management
│   └── utils/             # Logging, location, safety utilities
├── models/                 # ML model services
│   ├── translation/       # Multi-language translation
│   ├── sentiment/         # Sentiment analysis
│   ├── bias/              # Bias detection
│   └── core/              # LLM response generation
├── data/                   # Static data & resources
│   ├── intents.json       # Intent classification data
│   └── civic_resources/   # Local government info
├── azure/                  # Azure ML deployment configs
└── requirements.txt        # Python dependencies
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Docker (optional, for containerized deployment)
- Azure subscription (for production deployment)

### Local Development Setup

1. **Clone the repository**
```bash
   git clone https://github.com/your-org/penny-v2.git
   cd penny-v2
```

2. **Create virtual environment**
```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
   pip install --upgrade pip
   pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
   # Create .env file with required variables:
   # AZURE_MAPS_KEY=your_azure_maps_key
   # ENVIRONMENT=development
   # DEBUG_MODE=false
```

5. **Run the application**
```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Access the API**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

---

## 🐳 Docker Deployment

### Build the container
```bash
docker build -t penny:latest .
```

### Run locally with Docker
```bash
docker run -p 8000:8000 \
  -e AZURE_OPENAI_KEY=your_key \
  -e WEATHER_API_KEY=your_key \
  penny:latest
```

---

## ☁️ Azure ML Deployment

### 1. Create Azure Resources
```bash
# Create resource group
az group create --name penny-rg --location eastus

# Create Azure ML workspace
az ml workspace create --name penny-workspace -g penny-rg

# Create Azure Container Registry
az acr create --name pennyregistry --resource-group penny-rg --sku Basic
```

### 2. Build and Push Container
```bash
# Login to Azure Container Registry
az acr login --name pennyregistry

# Build and tag image
docker build -t pennyregistry.azurecr.io/penny:v1 .

# Push to registry
docker push pennyregistry.azurecr.io/penny:v1
```

### 3. Deploy to Azure Container Instances
```bash
az container create \
  --resource-group penny-rg \
  --name penny-api \
  --image pennyregistry.azurecr.io/penny:v1 \
  --cpu 2 \
  --memory 4 \
  --registry-login-server pennyregistry.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --dns-name-label penny-civic-ai \
  --ports 8000 \
  --environment-variables \
    ENVIRONMENT=production \
    AZURE_OPENAI_KEY=<your-key>
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ENVIRONMENT` | Deployment environment (`development`, `production`) | No | `development` |
| `AZURE_MAPS_KEY` | Azure Maps API key (for weather) | Yes | - |
| `ENVIRONMENT` | Deployment environment | No | `development` |
| `DEBUG_MODE` | Enable debug endpoints | No | `false` |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | No | `*` |
| `LOG_LEVEL` | Logging level (`INFO`, `DEBUG`, `WARNING`) | No | `INFO` |
| `TENANT_ID` | Default tenant/city identifier | No | `default` |

### Azure Key Vault Integration (Recommended)

For production deployments, store secrets in Azure Key Vault:
```bash
# Create Key Vault
az keyvault create --name penny-keyvault --resource-group penny-rg

# Store secrets
az keyvault secret set --vault-name penny-keyvault --name openai-key --value "your-key"

# Reference in deployment
--environment-variables \
  AZURE_OPENAI_KEY="@Microsoft.KeyVault(SecretUri=https://penny-keyvault.vault.azure.net/secrets/openai-key/)"
```

---

## 📡 API Usage

### Send a message to Penny
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What community events are happening this weekend?",
    "tenant_id": "norfolk",
    "user_id": "user123",
    "session_id": "session456"
  }'
```

### Response format
```json
{
  "response": "Hi! Here are some great community events happening this weekend in Norfolk...",
  "intent": "community_events",
  "tenant_id": "norfolk",
  "session_id": "session456",
  "timestamp": "2025-11-26T10:30:00Z",
  "response_time_ms": 245
}
```

---

## 🧪 Testing

### Run unit tests
```bash
pytest tests/ -v
```

### Run integration tests
```bash
pytest tests/integration/ -v
```

### Check code quality
```bash
# Linting
flake8 app/ models/

# Type checking
mypy app/ models/

# Format check
black --check app/ models/
```

---

## 📊 Monitoring & Logging

Penny uses structured JSON logging for production observability:

- **Application logs**: Stored in `/logs/` directory
- **Azure Application Insights**: Integration available for production
- **Health endpoint**: `/health` provides service status

### Log format
```json
{
  "timestamp": "2025-11-26T10:30:00Z",
  "level": "INFO",
  "intent": "weather_query",
  "tenant_id": "norfolk",
  "session_id": "abc123",
  "response_time_ms": 150,
  "success": true,
  "model_used": "gpt-4"
}
```

---

## 🛡️ Security & Privacy

- **PII Protection**: All logs sanitized before storage
- **Content Moderation**: Built-in bias and safety detection
- **Secrets Management**: Azure Key Vault integration
- **Non-root Container**: Security-hardened Docker image
- **HTTPS Only**: TLS/SSL required for production endpoints

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow code style (Black, Flake8, MyPy)
4. Add tests for new features
5. Ensure all tests pass
6. Submit a pull request

### Code Standards

- **Type hints**: Required for all functions
- **Docstrings**: Google-style format
- **Error handling**: Structured try/except blocks
- **Logging**: Use `log_interaction()` for all operations
- **PII safety**: Always sanitize user data

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [Azure Machine Learning](https://azure.microsoft.com/en-us/services/machine-learning/)
- Civic data from local government open data initiatives

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/penny-v2/issues)
- **Documentation**: [Full docs](https://docs.penny-ai.org)
- **Email**: support@penny-ai.org

---

## 🗺️ Roadmap

- [ ] Multi-tenant dashboard
- [ ] Voice interface integration
- [ ] Advanced sentiment analysis
- [ ] Predictive civic engagement insights
- [ ] Mobile app integration

---

**Made with ❤️ for civic engagement**