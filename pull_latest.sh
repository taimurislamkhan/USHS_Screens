#!/bin/bash

# Git Pull Script - Pull latest updates from remote repository
# This script pulls the latest changes from the current branch

echo "🔄 Pulling latest updates from remote repository..."
echo "Current branch: $(git branch --show-current)"
echo "Repository: $(git config --get remote.origin.url)"
echo ""

# Fetch latest changes from remote
echo "📡 Fetching latest changes..."
git fetch origin

# Pull latest changes
echo "⬇️  Pulling changes..."
git pull origin $(git branch --show-current)

# Check if pull was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pulled latest updates!"
    echo "📊 Current status:"
    git log --oneline -5
else
    echo ""
    echo "❌ Failed to pull updates. Please check for conflicts or network issues."
    echo "📊 Current status:"
    git status
fi
