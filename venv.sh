#!/bin/bash
set -e

# Verifica se foi executado com 'source'
(return 0 2>/dev/null) || {
    echo "⚠️  Este script deve ser executado com 'source venv.sh' para funcionar corretamente."
    exit 1
}

# Cria o ambiente virtual se ainda não existir
if [ ! -d "venv" ]; then
    echo "📦 Criando o ambiente virtual..."
    py -m venv venv
fi

# Ativa o ambiente virtual
echo "🐍 Ativando o ambiente virtual..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Instala dependências se requirements.txt existir
if [ -f "requirements.txt" ]; then
    echo "📄 requirements.txt encontrado. Instalando dependências..."
    pip install --upgrade pip
    pip install --upgrade -r requirements.txt
else
    echo "⚠️  Nenhum arquivo requirements.txt encontrado. Ignorando instalação de dependências."
fi

python executor.py