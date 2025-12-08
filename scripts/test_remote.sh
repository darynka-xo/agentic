#!/bin/bash
# Быстрый тест доступа к API на RunPod

# ЗАМЕНИТЕ НА ВАШ RUNPOD URL!
RUNPOD_URL="YOUR_RUNPOD_URL"

echo "=================================================="
echo "🧪 Тест доступа к API на RunPod"
echo "=================================================="

if [ "$RUNPOD_URL" = "YOUR_RUNPOD_URL" ]; then
    echo ""
    echo "❌ ОШИБКА: Не установлен RUNPOD_URL!"
    echo ""
    echo "Инструкция:"
    echo "  1. Откройте RunPod Web UI"
    echo "  2. Добавьте TCP Port Mapping для порта 8000"
    echo "  3. Скопируйте публичный URL"
    echo "  4. Отредактируйте этот файл и установите RUNPOD_URL"
    echo ""
    echo "Пример:"
    echo '  RUNPOD_URL="https://abc123-8000.proxy.runpod.net"'
    echo ""
    exit 1
fi

echo ""
echo "Сервер: $RUNPOD_URL"
echo ""

# Тест 1: Проверка /docs
echo "1️⃣  Проверка Swagger UI..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$RUNPOD_URL/docs")

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ Swagger UI доступен (HTTP $HTTP_CODE)"
    echo "   🔗 Откройте в браузере: $RUNPOD_URL/docs"
else
    echo "   ❌ Ошибка (HTTP $HTTP_CODE)"
    echo "   Проверьте:"
    echo "     - Сервер запущен на RunPod: ./manage.sh status"
    echo "     - Порт 8000 открыт в TCP Port Mappings"
    echo "     - URL правильный"
    exit 1
fi

# Тест 2: Проверка /predict
echo ""
echo "2️⃣  Проверка endpoint /predict..."

PAYLOAD='{
  "raw_text": "Жилой дом Секция 1 12 этажей м2 4675,08 табл. 1706-0201-01 поз.7 стоимость 52690700 тенге",
  "row_index": 1,
  "page_number": 1
}'

RESPONSE=$(curl -s -X POST "$RUNPOD_URL/predict" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

# Проверяем ответ
if echo "$RESPONSE" | grep -q '"output"'; then
    echo "   ✅ Endpoint /predict работает"
    
    # Извлекаем основные данные
    TABLE_CODE=$(echo "$RESPONSE" | grep -o '"table_code_claimed":"[^"]*"' | cut -d'"' -f4)
    IS_APPROVED=$(echo "$RESPONSE" | grep -o '"is_approved":[^,}]*' | cut -d':' -f2)
    
    echo "   📋 Результат обработки:"
    echo "      Таблица СЦП: $TABLE_CODE"
    echo "      Одобрено: $IS_APPROVED"
else
    echo "   ⚠️  Ошибка в ответе:"
    echo "$RESPONSE" | head -c 500
fi

# Тест 3: Проверка /predict_pdf (если есть тестовый PDF)
echo ""
echo "3️⃣  Проверка endpoint /predict_pdf..."

if [ -f "test.pdf" ]; then
    echo "   Загрузка test.pdf..."
    
    PDF_RESPONSE=$(curl -s -X POST "$RUNPOD_URL/predict_pdf" \
      -F "file=@test.pdf" \
      --max-time 60)
    
    if echo "$PDF_RESPONSE" | grep -q '"tables_processed"'; then
        TABLES=$(echo "$PDF_RESPONSE" | grep -o '"tables_processed":[0-9]*' | cut -d':' -f2)
        echo "   ✅ Endpoint /predict_pdf работает"
        echo "   📊 Обработано таблиц: $TABLES"
    else
        echo "   ⚠️  Ошибка при загрузке PDF"
        echo "$PDF_RESPONSE" | head -c 500
    fi
else
    echo "   ⏭️  Пропущено (файл test.pdf не найден)"
    echo "   Для теста создайте файл test.pdf в текущей директории"
fi

echo ""
echo "=================================================="
echo "✅ Тестирование завершено!"
echo "=================================================="
echo ""
echo "📚 Для подробных примеров см.: RUNPOD_ACCESS.md"
echo "🐍 Для Python тестов: python test_remote_pdf.py your_file.pdf"
echo ""

