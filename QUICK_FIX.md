# Quick Fix - LLM возвращает None/empty

## Что изменилось (3 минуты назад)

### 1. Упрощён prompt в `_make_structurer_task()` ✅
- Добавлен **пример** input/output 
- Более чёткие инструкции
- Убрана длинная схема

**Было:**
```
"Always respond with valid JSON that matches this schema: {...giant schema...}. No prose."
```

**Стало:**
```
Extract these fields:
1. text_description: ...
2. table_code_claimed: ...

Example input: '...'
Example output: {...}

Return ONLY valid JSON.
```

### 2. Улучшен agent ✅
- Более чёткая роль: "JSON Extractor"
- Verbose=True для отладки
- allow_delegation=False

### 3. Оптимизирован LLM ✅
- max_tokens: 2048 (быстрее)
- temperature: 0.0 (детерминизм)

---

## Перезапустить и протестировать

```bash
# Перезапустить сервер
pkill -f "python.*server.py"
python server.py

# Тест одного файла
curl -X POST http://localhost:8000/predict \
     -H "Content-Type: application/json" \
     -d @tabula_tables/05-01\ Расчет\ ПИР_Атамура\ 2_tabula_t1.json

# Или batch тест
python test_batch.py
```

---

## Если всё равно ошибка

### Вариант 1: Попробовать меньшую модель
```bash
export OLLAMA_MODEL="ollama/qwen2.5:7b"
# Перезапустить сервер
```

### Вариант 2: Проверить Ollama напрямую
```bash
ollama run qwen3:30b
```
Введите:
```
Extract JSON from: "1 Жилой дом табл. 1706-0201-01 52690700"
{"text_description": "Жилой дом", "table_code_claimed": "1706-0201-01", "X_claimed": 0, "total_claimed": 52690700, "extracted_tags": []}
```

Если модель не может это сделать → проблема в модели, не в коде.

### Вариант 3: Включить detailed logging
```bash
export CREWAI_TRACING_ENABLED=true
# Перезапустить сервер
```

---

## Файлы изменены
- ✅ `agents.py` - упрощён prompt + agent
- ✅ `preprocessor.py` - конвертирует tabula → text (раньше)
- ✅ `tools/db_search.py` - MongoDB queries (раньше)
- ✅ `config.py` - DB name (раньше)

---

Попробуйте перезапустить сервер и протестировать! 🚀

Если работает - отлично! Если нет - модель qwen3:30b может не справляться с JSON extraction. Попробуйте qwen2.5:7b или llama3.

