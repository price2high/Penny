#!/bin/bash
# Script to push with Personal Access Token
# Usage: ./push_with_token.sh YOUR_TOKEN_HERE

if [ -z "$1" ]; then
    echo "Usage: $0 <your-github-token>"
    echo ""
    echo "Steps:"
    echo "1. Create token at: https://github.com/settings/tokens/new"
    echo "2. Select 'repo' scope"
    echo "3. Copy the token"
    echo "4. Run: ./push_with_token.sh YOUR_TOKEN"
    exit 1
fi

TOKEN="$1"
USERNAME=$(git config user.name 2>/dev/null || echo "your-username")

# Temporarily set remote with token
git remote set-url origin "https://${TOKEN}@github.com/Cyber-Shawties-LLC/Penny.git"

# Push
echo "Pushing to GitHub..."
git push origin main

# Restore original remote (without token)
git remote set-url origin "https://github.com/Cyber-Shawties-LLC/Penny.git"

echo ""
echo "✅ Push complete! Token was used temporarily and removed from remote URL."

