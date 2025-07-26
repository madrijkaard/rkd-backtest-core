#!/bin/bash
set -e

# Check if the script is sourced
(return 0 2>/dev/null) || {
    echo "⚠️  This script must be executed using 'source venv.sh' to work correctly."
    exit 1
}

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    py -m venv venv
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install dependencies from requirements.txt line by line
if [ -f "requirements.txt" ]; then
    echo "📄 requirements.txt found. Installing dependencies..."
    pip install --upgrade pip

    mapfile -t packages < requirements.txt
    total=${#packages[@]}
    count=0

    for pkg in "${packages[@]}"; do
        count=$((count + 1))
        percent=$((count * 100 / total))
        filled=$((percent / 5))  # 20-block progress bar
        empty=$((20 - filled))
        bar=$(printf "%0.s█" $(seq 1 $filled))
        bar+=$(printf "%0.s " $(seq 1 $empty))
        echo -ne "\r🔄 [$bar] $count/$total: $pkg"
        pip install "$pkg" 2>/dev/null | grep -v "Requirement already satisfied" || true
    done

    echo -e "\n✅ Dependency installation complete!"
else
    echo "⚠️  No requirements.txt found. Skipping dependency installation."
fi

# Run the main script
echo "🚀 Running executor.py..."
python executor.py
