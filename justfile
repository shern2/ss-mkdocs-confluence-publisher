# ==========================================
# 🚀 Publishing
# ==========================================

# Publish to PyPI (e.g., just publish v0.0.2)
[group('Publishing')]
publish version:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Load .env"
    set -a && source .env && set +a

    echo "📦 Publishing {{version}} to PyPI..."
    uv version {{version}}
    rm -rf dist/*
    uv build
    uv publish
