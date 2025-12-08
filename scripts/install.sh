#!/bin/bash

# Install script for Agentic System
# Installs Java, Ollama, and system dependencies

set -e  # Exit on error

echo "=========================================="
echo "  Agentic System Installation Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if running as root (not recommended)
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run this script as root"
    exit 1
fi

# Update package list
print_info "Updating package list..."
sudo apt update

# Install Java (OpenJDK 11 or newer for Tabula)
print_info "Installing Java..."
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}')
    print_success "Java is already installed (version $JAVA_VERSION)"
else
    sudo apt install -y openjdk-11-jdk openjdk-11-jre
    print_success "Java installed successfully"
fi

# Verify Java installation
java -version
print_success "Java verification complete"

# Install Python dependencies
print_info "Installing Python 3 and pip..."
sudo apt install -y python3 python3-pip python3-venv

# Install system dependencies for Python packages
print_info "Installing system dependencies..."
sudo apt install -y \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    git \
    curl \
    wget

print_success "System dependencies installed"

# Install Ollama
print_info "Installing Ollama..."
if command -v ollama &> /dev/null; then
    print_success "Ollama is already installed"
else
    curl -fsSL https://ollama.com/install.sh | sh
    print_success "Ollama installed successfully"
fi

# Start Ollama service
print_info "Starting Ollama service..."
sudo systemctl enable ollama
sudo systemctl start ollama
print_success "Ollama service started"

# Wait for Ollama to be ready
print_info "Waiting for Ollama to be ready..."
sleep 3

# Pull the required model
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
print_info "Pulling Ollama model: $OLLAMA_MODEL..."
ollama pull "$OLLAMA_MODEL"
print_success "Model $OLLAMA_MODEL pulled successfully"

# Create virtual environment if it doesn't exist
print_info "Setting up Python virtual environment..."
cd "$(dirname "$0")/.."  # Go to project root
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment and install Python packages
print_info "Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
print_success "Python packages installed"

echo ""
echo "=========================================="
print_success "Installation completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Configure MongoDB connection in config.py"
echo "3. Start the system: ./scripts/start_system.sh"
echo ""
print_info "Ollama is running on http://localhost:11434"
print_info "Model loaded: $OLLAMA_MODEL"
echo ""

