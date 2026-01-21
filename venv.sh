#!/bin/bash

# -------------------------------------------------------------------
# Fail fast, but allow us to inspect Python errors
# -------------------------------------------------------------------
set -e

# -------------------------------------------------------------------
# This script MUST be sourced
# -------------------------------------------------------------------
(return 0 2>/dev/null) || {
    echo "⚠️ This script must be executed with:"
    echo "    source venv.sh [-u]"
    return 1
}

# -------------------------------------------------------------------
# Flags
# -------------------------------------------------------------------
UPDATE_REQS=false
for arg in "$@"; do
    if [[ "$arg" == "-u" ]]; then
        UPDATE_REQS=true
        break
    fi
done

# -------------------------------------------------------------------
# Create virtual environment if it doesn't exist
# -------------------------------------------------------------------
if [[ ! -d "venv" ]]; then
    echo "📦 Creating virtual environment..."
    if command -v py >/dev/null 2>&1; then
        py -m venv venv
    else
        python -m venv venv
    fi
fi

# -------------------------------------------------------------------
# Activate virtual environment
# -------------------------------------------------------------------
echo -e "\n🐍 Activating virtual environment..."

if [[ "$OSTYPE" == msys* || "$OSTYPE" == cygwin* || "$OSTYPE" == win32* ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# -------------------------------------------------------------------
# Upgrade pip (safe on Windows)
# -------------------------------------------------------------------
echo -e "\n🔄 Upgrading pip..."
python -m pip install --upgrade pip

# -------------------------------------------------------------------
# Install dependencies (optional)
# -------------------------------------------------------------------
if $UPDATE_REQS; then
    if [[ -f "requirements.txt" ]]; then
        echo "📄 Installing dependencies from requirements.txt..."
        python -m pip install -r requirements.txt
        echo "✅ Dependencies installed!"
    else
        echo "⚠️ requirements.txt not found. Skipping dependency installation."
    fi
else
    echo -e "\n⏭️  Skipping dependency installation."
    echo "   Use: source venv.sh -u"
fi

# -------------------------------------------------------------------
# Run backtest executor
# -------------------------------------------------------------------
echo -e "\n🚀 Running executor.py..."

if ! python executor.py; then
    echo ""
    echo "❌ executor.py crashed!"
    echo "👉 Press ENTER to close..."
    read
fi
