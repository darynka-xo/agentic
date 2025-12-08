#!/bin/bash

echo "════════════════════════════════════════════════════════════════"
echo "  СИСТЕМА ПРОВЕРКИ СМЕТ ПИР - СТАТУС"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check Ollama
echo "🟢 OLLAMA LLM SERVER"
if ps aux | grep "ollama serve" | grep -v grep > /dev/null; then
    echo "  ✓ Запущен"
    ollama list 2>/dev/null | grep "qwen3:30b" > /dev/null && echo "  ✓ Модель: qwen3:30b (18 GB)"
    curl -s http://127.0.0.1:11434/ > /dev/null && echo "  ✓ API: http://127.0.0.1:11434"
else
    echo "  ✗ Не запущен"
fi

echo ""
echo "🟢 FASTAPI SERVER"
if ps aux | grep "server.py" | grep -v grep > /dev/null; then
    PID=$(ps aux | grep 'server.py' | grep -v grep | awk '{print $2}')
    echo "  ✓ Запущен (PID: $PID)"
    curl -s http://127.0.0.1:8000/docs > /dev/null && echo "  ✓ API: http://127.0.0.1:8000"
else
    echo "  ✗ Не запущен"
fi

echo ""
echo "🔧 GPU"
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader 2>/dev/null | head -1 | \
    awk -F', ' '{print "  ✓ " $1 "\n  ✓ Использовано: " $2 "\n  ✓ Свободно: " $3}'

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ENDPOINT: POST http://127.0.0.1:8000/predict"
echo "  DOCS:     http://127.0.0.1:8000/docs"
echo "════════════════════════════════════════════════════════════════"
