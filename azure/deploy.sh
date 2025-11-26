#!/bin/bash
# Azure ML Deployment Script for PENNY Project
# Deploys Penny to Azure ML endpoints

set -e  # Exit on error

echo "🚀 Starting PENNY Azure ML Deployment"

# Configuration
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-penny-rg}"
WORKSPACE_NAME="${AZURE_WORKSPACE:-penny-workspace}"
ENDPOINT_NAME="${ENDPOINT_NAME:-penny-main-endpoint}"

# Check Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login check
echo "🔐 Checking Azure authentication..."
az account show > /dev/null 2>&1 || {
    echo "⚠️  Not logged in. Please run: az login"
    exit 1
}

# Create resource group if it doesn't exist
echo "📦 Creating resource group: $RESOURCE_GROUP"
az group create --name "$RESOURCE_GROUP" --location eastus 2>/dev/null || echo "Resource group already exists"

# Create workspace if it doesn't exist
echo "🏢 Creating Azure ML workspace: $WORKSPACE_NAME"
az ml workspace create --name "$WORKSPACE_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null || echo "Workspace already exists"

# Build and register model
echo "📦 Building and registering model..."
az ml model create \
    --name "penny-main-model" \
    --path "." \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$WORKSPACE_NAME"

# Deploy endpoint
echo "🚀 Deploying endpoint: $ENDPOINT_NAME"
az ml online-endpoint create \
    --name "$ENDPOINT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$WORKSPACE_NAME" \
    --file azure/endpoint.yml || echo "Endpoint may already exist"

# Create deployment
echo "📋 Creating deployment..."
az ml online-deployment create \
    --name "penny-main-deployment" \
    --endpoint-name "$ENDPOINT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$WORKSPACE_NAME" \
    --file azure/deployment.yml

# Allocate traffic
echo "🔄 Allocating traffic..."
az ml online-deployment update \
    --name "penny-main-deployment" \
    --endpoint-name "$ENDPOINT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$WORKSPACE_NAME" \
    --traffic-allocation 100

echo "✅ Deployment complete!"
echo "📊 Endpoint URL: https://$ENDPOINT_NAME.eastus.inference.ml.azure.com"

