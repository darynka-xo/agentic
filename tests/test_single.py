#!/usr/bin/env python3
"""
Тест полного пайплайна на одном документе
"""
import json
import requests
import sys
from pathlib import Path

# Загружаем тестовый файл
test_file = Path("tabula_tables/05-01 Расчет ПИР_Атамура 2_tabula_t1.json")

print("="*80)
print("🧪 ТЕСТ ПОЛНОГО ПАЙПЛАЙНА")
print("="*80)
print(f"\nФайл: {test_file}")

with open(test_file, 'r', encoding='utf-8') as f:
    payload = json.load(f)

print(f"Таблица №{payload.get('table_index')}")
print(f"Строк данных: {len(payload.get('rows', []))}")

# Декодируем первую позицию для отображения
if payload.get('rows') and len(payload['rows']) > 2:
    row = payload['rows'][2]  # Первая рабочая строка
    print(f"\nПример строки:")
    print(f"  {row[0]}: {row[1][:60]}...")

print("\n" + "="*80)
print("📤 ОТПРАВКА ЗАПРОСА НА API")
print("="*80)

# Отправляем запрос
server_url = "http://127.0.0.1:8000/predict"
print(f"URL: {server_url}")
print("Ожидание ответа (может занять до 2 минут)...")

try:
    response = requests.post(
        server_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=180
    )
    
    print(f"\n✓ Статус: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n" + "="*80)
        print("✅ УСПЕШНЫЙ ОТВЕТ")
        print("="*80)
        
        # Парсим результат
        output = result.get('output', {})
        
        # Raw Input
        raw_input = output.get('raw_input', {})
        if raw_input:
            print("\n📋 ИЗВЛЕЧЕННЫЕ ДАННЫЕ (Structurer Agent):")
            print(f"  • Описание: {raw_input.get('text_description', 'N/A')}")
            print(f"  • Таблица: {raw_input.get('table_code_claimed', 'N/A')}")
            print(f"  • Позиция: {raw_input.get('position_number', 'N/A')}")
            print(f"  • Объем X: {raw_input.get('X_claimed', 'N/A')}")
            print(f"  • Стоимость: {raw_input.get('total_claimed', 'N/A'):,.0f} тенге")
            print(f"  • Теги: {raw_input.get('extracted_tags', [])}")
        
        # Reference Data
        ref_data = output.get('reference_data', {})
        if ref_data:
            print("\n🔍 ДАННЫЕ ИЗ БД (Auditor Agent):")
            print(f"  • param_a: {ref_data.get('ref_A', 'N/A')}")
            print(f"  • param_b: {ref_data.get('ref_B', 'N/A')}")
            print(f"  • Стратегия: {ref_data.get('formula_strategy', 'N/A')}")
            print(f"  • Позиция ID: {ref_data.get('source_position_id', 'N/A')}")
            
            coeffs = ref_data.get('valid_coefficients', [])
            if coeffs:
                print(f"  • Коэффициенты: {len(coeffs)} шт.")
                for c in coeffs:
                    print(f"    - {c.get('value')}: {c.get('reason', 'N/A')[:50]}...")
        
        # Audit Verdict
        verdict = output.get('audit_verdict', {})
        if verdict:
            print("\n💰 РЕЗУЛЬТАТ ПРОВЕРКИ (Calculator):")
            print(f"  • Расчетная стоимость: {verdict.get('calculated_total', 'N/A'):,.2f} тыс. тенге")
            print(f"  • Одобрено: {'✅ ДА' if verdict.get('is_approved') else '❌ НЕТ'}")
            print(f"  • Причина: {verdict.get('reason', 'N/A')}")
        
        print("\n" + "="*80)
        print("✅ ТЕСТ ПРОЙДЕН УСПЕШНО!")
        print("="*80)
        
        # Сохраняем полный ответ
        with open('test_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nПолный ответ сохранен в: test_result.json")
        
    else:
        print("\n" + "="*80)
        print("❌ ОШИБКА")
        print("="*80)
        try:
            error = response.json()
            print(f"Детали: {json.dumps(error, indent=2, ensure_ascii=False)}")
        except:
            print(f"Ответ: {response.text}")
        sys.exit(1)

except requests.exceptions.Timeout:
    print("\n❌ ТАЙМАУТ: Запрос занял более 3 минут")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ ОШИБКА: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

