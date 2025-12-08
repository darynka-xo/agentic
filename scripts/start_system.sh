#!/bin/bash

# 1. Start Ollama (if not already running)
if ! pgrep -x "ollama" > /dev/null
then
    echo "Starting Ollama..."
    nohup ollama serve > /workspace/agentic/ollama.log 2>&1 &
    # Give it a few seconds to initialize
    sleep 5
else
    echo "Ollama is already running."
fi

# 2. Start the Python Server
echo "Starting LitServe Agent..."
nohup /workspace/agentic/venv/bin/python /workspace/agentic/server.py > /workspace/agentic/server.log 2>&1 &

echo "System started!"
echo "Logs are at:"
echo "  - /workspace/agentic/ollama.log"
echo "  - /workspace/agentic/server.log"
