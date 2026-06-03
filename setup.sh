#!/bin/bash
# AI-AutoBlog Hugo - Quick Setup Script
# Run this after cloning the repository

set -e

echo "========================================"
echo "  AI-AutoBlog Hugo - Setup Script"
echo "========================================"
echo ""

# Check Hugo is installed
if ! command -v hugo &> /dev/null; then
    echo "ERROR: Hugo is not installed."
    echo "Install it from: https://gohugo.io/installation/"
    echo ""
    echo "Quick install (macOS): brew install hugo"
    echo "Quick install (Linux): sudo apt install hugo"
    echo "Quick install (Windows): choco install hugo-extended"
    exit 1
fi

echo "Hugo version: $(hugo version)"

# Clone PaperMod theme if not exists
if [ ! -d "themes/PaperMod" ]; then
    echo ""
    echo "Cloning PaperMod theme..."
    git submodule add --depth=1 https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod
    echo "PaperMod theme installed."
else
    echo "PaperMod theme already exists."
fi

# Validate config.yaml
echo ""
echo "Validating config.yaml..."
if python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" 2>/dev/null; then
    echo "config.yaml is valid."
elif command -v yq &> /dev/null; then
    yq eval '.' config.yaml > /dev/null && echo "config.yaml is valid."
else
    echo "WARNING: Could not validate config.yaml (no yaml parser available)"
fi

# Check if OPENAI_API_KEY is set (optional)
if [ -n "$OPENAI_API_KEY" ]; then
    echo "OPENAI_API_KEY is set."
else
    echo "WARNING: OPENAI_API_KEY not set. Set it in GitHub Secrets."
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml with your Alibaba URLs and keywords"
echo "2. Push to GitHub"
echo "3. Add OPENAI_API_KEY to GitHub Secrets"
echo "4. Enable GitHub Actions workflow"
echo "5. Enable GitHub Pages"
echo ""
echo "To test locally:"
echo "  python3 scripts/generate-post.py   # Generate a post"
echo "  hugo server -D                    # Preview site"
