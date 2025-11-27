#!/bin/bash
# Script to prepare files for Hugging Face Spaces upload
# Usage: ./prepare_hf_upload.sh /path/to/hf-space-directory

if [ -z "$1" ]; then
    echo "Usage: $0 <target-directory>"
    echo "Example: $0 ~/hf-spaces/penny-civic-assistant"
    exit 1
fi

TARGET_DIR="$1"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Preparing PENNY files for Hugging Face Spaces..."
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"
echo ""

# Create target directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Copy root level files
echo "📄 Copying root files..."
cp "$SOURCE_DIR/app.py" "$TARGET_DIR/"
cp "$SOURCE_DIR/README.md" "$TARGET_DIR/"
cp "$SOURCE_DIR/Dockerfile" "$TARGET_DIR/"
cp "$SOURCE_DIR/requirements.txt" "$TARGET_DIR/"

# Copy app directory
echo "📁 Copying app/ directory..."
cp -r "$SOURCE_DIR/app" "$TARGET_DIR/"

# Create __init__.py files if they don't exist
touch "$TARGET_DIR/app/__init__.py"

# Copy models directory
echo "🤖 Copying models/ directory..."
cp -r "$SOURCE_DIR/models" "$TARGET_DIR/"
touch "$TARGET_DIR/models/__init__.py"

# Copy data files (only events and resources)
echo "📊 Copying data files..."
mkdir -p "$TARGET_DIR/data/events"
mkdir -p "$TARGET_DIR/data/resources"
cp "$SOURCE_DIR/data/events"/*.json "$TARGET_DIR/data/events/" 2>/dev/null
cp "$SOURCE_DIR/data/resources"/*.json "$TARGET_DIR/data/resources/" 2>/dev/null

echo ""
echo "✅ Files prepared successfully!"
echo ""
echo "📋 Summary:"
echo "  - Root files: app.py, README.md, Dockerfile, requirements.txt"
echo "  - Application: app/ directory"
echo "  - Models: models/ directory"
echo "  - Data: data/events/ and data/resources/"
echo ""
echo "Next steps:"
echo "  1. cd $TARGET_DIR"
echo "  2. Review the files"
echo "  3. git add ."
echo "  4. git commit -m 'Initial deployment'"
echo "  5. git push"
echo ""

