# 📄 Руководство по PDF Endpoint

## ✅ Новый Функционал

Система теперь автоматически принимает PDF файлы и извлекает таблицы!

**Endpoint:** `POST /predict_pdf`

---

## 🚀 Использование

### 1. Через curl:

```bash
curl -X POST http://127.0.0.1:8000/predict_pdf \
  -F "file=@your_smeta.pdf" \
  -o result.json
```

### 2. Через Python:

```python
import requests

# Загрузить PDF
with open('smeta.pdf', 'rb') as f:
    files = {'file': ('smeta.pdf', f, 'application/pdf')}
    response = requests.post(
        'http://127.0.0.1:8000/predict_pdf',
        files=files
    )

result = response.json()
print(f"Таблиц обработано: {result['tables_processed']}")

# Проверяем результаты
for table_result in result['results']:
    if table_result['status'] == 'success':
        output = table_result['output']
        verdict = output['audit_verdict']
        print(f"Таблица {table_result['table_index']}: {verdict['reason']}")
```

### 3. Тестовый скрипт:

```bash
python test_pdf_upload.py path/to/your/smeta.pdf
```

---

## 📊 Формат Ответа

```json
{
  "filename": "smeta.pdf",
  "tables_processed": 3,
  "results": [
    {
      "table_index": 1,
      "status": "success",
      "output": {
        "id": "...",
        "raw_input": {
          "text_description": "Жилой дом...",
          "table_code_claimed": "1706-0201-01",
          "position_number": 7,
          "X_claimed": 4675.08,
          "total_claimed": 52690700,
          "year": 2023,
          "claimed_coefficients": [
            {"id": "K3", "value": 1.2},
            {"id": "K4", "value": 1.2}
          ]
        },
        "reference_data": {
          "ref_A": 10637.0,
          "ref_B": 3.16,
          "valid_coefficients": [
            {"id": "k2_stage", "value": 1.2}
          ]
        },
        "audit_verdict": {
          "calculated_total": 52690.70,
          "is_approved": true,
          "reason": "Match within 0.00% tolerance"
        }
      }
    },
    {
      "table_index": 2,
      "status": "success",
      "output": {...}
    }
  ]
}
```

---

## 🔧 Как Это Работает

### Шаг 1: Загрузка PDF
```
Клиент → POST /predict_pdf (multipart/form-data)
         file: binary PDF content
```

### Шаг 2: Извлечение Таблиц
```
PDF → tabula-py → pandas DataFrame → JSON format
Таблицы с границами (lattice=True)
Каждая таблица = отдельный payload
```

### Шаг 3: Обработка Каждой Таблицы
```
Для каждой таблицы:
  1. Preprocessor → raw_text
  2. Structurer Agent → извлечение данных
  3. Auditor Agent → поиск в MongoDB
  4. Calculator → проверка стоимости
```

### Шаг 4: Возврат Результатов
```
Все таблицы обработаны → JSON с результатами
```

---

## 📝 Примеры Использования

### Пример 1: Простая загрузка

```bash
curl -X POST http://127.0.0.1:8000/predict_pdf \
  -F "file=@05-01_Расчет_ПИР_Атамура_2.pdf"
```

### Пример 2: С сохранением результата

```bash
curl -X POST http://127.0.0.1:8000/predict_pdf \
  -F "file=@smeta.pdf" \
  -o smeta_results.json

# Красивый вывод
cat smeta_results.json | python -m json.tool
```

### Пример 3: Python скрипт

```python
import requests
import json

def check_smeta_pdf(pdf_path):
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path, f, 'application/pdf')}
        response = requests.post(
            'http://127.0.0.1:8000/predict_pdf',
            files=files,
            timeout=180
        )
    
    if response.status_code == 200:
        result = response.json()
        
        # Анализ результатов
        for table in result['results']:
            if table['status'] == 'success':
                verdict = table['output']['audit_verdict']
                
                if verdict['is_approved']:
                    print(f"✅ Таблица {table['table_index']}: ОДОБРЕНО")
                else:
                    print(f"❌ Таблица {table['table_index']}: {verdict['reason']}")
        
        return result
    else:
        print(f"Ошибка: {response.status_code}")
        return None

# Использование
result = check_smeta_pdf('my_smeta.pdf')
```

---

## ⚠️ Требования

1. **PDF должен быть цифровым** (не сканированный)
   - OCR не требуется
   - Текст должен быть выделяемым

2. **Таблицы должны иметь границы**
   - tabula лучше работает с линованными таблицами
   - Параметр `lattice=True`

3. **Размер файла**
   - Рекомендуется до 10 MB
   - Большие файлы обрабатываются дольше

---

## 📊 Преимущества

✅ **Автоматизация**
  - Загружаете PDF → получаете результаты
  - Не нужно вручную конвертировать в JSON

✅ **Множественные таблицы**
  - Обрабатывает ВСЕ таблицы в PDF
  - Каждая таблица проверяется отдельно

✅ **Полная проверка**
  - Извлечение данных (LLM)
  - Поиск в MongoDB (по году 2019-2025)
  - Применение коэффициентов
  - Проверка стоимости

---

## 🔧 Troubleshooting

### Ошибка: "Only PDF files are supported"
Убедитесь что файл имеет расширение .pdf

### Ошибка: "PDF processing failed"
Проверьте что:
- Java установлен (`java -version`)
- PDF не поврежден
- PDF содержит таблицы с данными

### Медленная обработка
- Каждая таблица ~ 7-15 секунд
- PDF с 5 таблицами = ~1 минута
- Используйте timeout=180 для больших файлов

---

## 📚 API Документация

После запуска сервера откройте:

http://127.0.0.1:8000/docs

Там вы увидите:
- `/predict` - для готовых JSON (старый endpoint)
- `/predict_pdf` - для загрузки PDF (новый endpoint) ⭐

---

## 🎯 Итог

Теперь вы можете:
1. ✅ Загружать PDF напрямую
2. ✅ Автоматически извлекать таблицы
3. ✅ Получать проверку всех позиций
4. ✅ Без ручной конвертации!

**Система готова к приему PDF файлов!** 🚀
