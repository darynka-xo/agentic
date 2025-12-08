# 🚀 Система Проверки Смет ПИР - Инструкция

## ✅ Статус Системы

Все компоненты запущены и работают:

- **Ollama LLM** - qwen3:30b (18 GB модель)
- **MongoDB** - scp-dev.osqjof9.mongodb.net
- **FastAPI Server** - http://127.0.0.1:8000
- **GPU** - NVIDIA L40S (46 GB VRAM)

## 📋 Управление Системой

```bash
cd /workspace/agentic

# Проверить статус
./status.sh

# Запустить систему
./manage.sh start

# Остановить систему
./manage.sh stop

# Перезапустить
./manage.sh restart

# Посмотреть логи
./manage.sh logs
```

## 🔧 API Endpoints

### POST /predict - Проверка сметы

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "Жилой дом Секция 1 12 этажей м2 4675,08 табл. 1706-0201-01 52690700",
    "row_index": 1,
    "page_number": 1
  }'
```

### Документация API

Откройте в браузере: http://127.0.0.1:8000/docs

## 📁 Структура Проекта

```
/workspace/agentic/
├── server.py              # FastAPI сервер
├── agents.py              # CrewAI агенты
├── config.py              # Конфигурация MongoDB
├── core/
│   ├── calculator.py      # Детерминированные расчеты
│   └── state.py           # Модели данных
├── tools/
│   └── db_search.py       # Инструмент поиска в БД
├── tabula_tables/         # Тестовые данные (300+ файлов)
├── manage.sh              # Скрипт управления системой
├── status.sh              # Проверка статуса
├── .env                   # Переменные окружения
├── ollama.log             # Логи Ollama
└── server.log             # Логи сервера
```

## 🗄️ База Данных MongoDB

**Подключение:** mongodb+srv://admin:***@scp-dev.osqjof9.mongodb.net

**База:** scp_verification_dev

**Коллекции:**
- `sections` - 26 разделов СЦП
- `coefficients` - 339 коэффициентов
- `formulas` - формулы расчета
- `general_provisions` - общие положения

## 🧪 Пакетное Тестирование

```bash
# Запустить тест на 50 файлах
python test_batch.py

# Результаты в:
# - batch_results/results_TIMESTAMP.json
# - batch_results/summary_TIMESTAMP.txt
```

## 📊 Мониторинг

```bash
# GPU мониторинг
watch -n 1 nvidia-smi

# Логи в реальном времени
tail -f server.log
tail -f ollama.log

# Процессы
ps aux | grep -E "(ollama|server.py)"
```

## 🔍 Алгоритм Работы

1. **Preprocessor** - конвертирует tabula JSON → plain text
2. **Structurer Agent** - извлекает данные из текста сметы
3. **Auditor Agent** - ищет данные в MongoDB (DBSearchTool)
4. **Calculator** - применяет формулы C = a + b × V
5. **Verdict** - сравнивает с заявленной стоимостью

## ⚙️ Переменные Окружения

Настройки в `.env`:

```bash
MONGO_URI=mongodb+srv://admin:3ZtOrKrs6YWiHfJq@scp-dev.osqjof9.mongodb.net/?appName=scp-dev
MONGO_DB_NAME=scp_verification_dev
OLLAMA_MODEL=qwen3:30b
OLLAMA_BASE_URL=http://127.0.0.1:11434
PORT=8000
LLM_TIMEOUT=600
```

## 🛠️ Troubleshooting

### Ollama не отвечает
```bash
pkill ollama
ollama serve > ollama.log 2>&1 &
sleep 5
ollama list
```

### Сервер не запускается
```bash
cd /workspace/agentic
source venv/bin/activate
python server.py  # Запустить в foreground для отладки
```

### MongoDB не подключается
```bash
# Проверить подключение
python -c "from config import get_db; db=get_db(); print(db.sections.count_documents({}))"
```

## 📝 Примечания

- **Systemd не доступен** - используются nohup & для фоновых процессов
- **LLM таймаут** - 600 секунд (10 минут) для больших запросов
- **GPU память** - модель qwen3:30b занимает ~18 GB VRAM
- **База данных** - MongoDB Atlas (облачная)

---

**Дата настройки:** 7 декабря 2025  
**GPU:** NVIDIA L40S (46 GB)  
**Модель:** qwen3:30b (18 GB)
