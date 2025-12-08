#!/bin/bash

set -e

case "$1" in
    start)
        echo "Запуск системы проверки смет ПИР..."
        
        # Start Ollama if not running
        if ! ps aux | grep "ollama serve" | grep -v grep > /dev/null; then
            echo "  Запуск Ollama..."
            nohup ollama serve >> ollama.log 2>&1 &
            sleep 5
        else
            echo "  Ollama уже запущен"
        fi
        
        # Start server if not running
        if ! ps aux | grep "server.py" | grep -v grep > /dev/null; then
            echo "  Запуск FastAPI сервера..."
            
            # Загружаем переменные из .env файла если он существует
            if [ -f .env ]; then
                echo "  Загрузка .env..."
                export $(cat .env | grep -v '^#' | xargs)
            else
                echo "  ⚠️  ВНИМАНИЕ: .env файл не найден!"
                echo "  Скопируйте .env.example в .env и укажите ваши credentials"
                exit 1
            fi
            
            nohup venv/bin/python server.py > server.log 2>&1 &
            sleep 3
        else
            echo "  Сервер уже запущен"
        fi
        
        echo ""
        echo "✓ Система запущена!"
        echo ""
        ./status.sh
        ;;
        
    stop)
        echo "Остановка системы..."
        pkill -f "python.*server.py" 2>/dev/null && echo "  ✓ Сервер остановлен" || echo "  Сервер не был запущен"
        pkill -f "ollama serve" 2>/dev/null && echo "  ✓ Ollama остановлен" || echo "  Ollama не был запущен"
        echo ""
        echo "✓ Система остановлена"
        ;;
        
    restart)
        echo "Перезапуск системы..."
        $0 stop
        sleep 2
        $0 start
        ;;
        
    status)
        ./status.sh
        ;;
        
    logs)
        echo "=== OLLAMA LOGS (last 20 lines) ==="
        tail -20 ollama.log
        echo ""
        echo "=== SERVER LOGS (last 20 lines) ==="
        tail -20 server.log
        ;;
        
    *)
        echo "Использование: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "  start   - Запустить систему"
        echo "  stop    - Остановить систему"
        echo "  restart - Перезапустить систему"
        echo "  status  - Показать статус"
        echo "  logs    - Показать логи"
        exit 1
        ;;
esac
