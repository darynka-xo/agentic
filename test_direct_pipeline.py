#!/usr/bin/env python3
"""
Прямой тест пайплайна без API - для отладки
"""
import os
import json
import sys

# Настройка окружения
os.environ["MONGO_URI"] = "mongodb+srv://admin:3ZtOrKrs6YWiHfJq@scp-dev.osqjof9.mongodb.net/?appName=scp-dev"
os.environ["MONGO_DB_NAME"] = "scp_verification_dev"
os.environ["OLLAMA_MODEL"] = "ollama/qwen2.5:7b"
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"

from config import get_db
from agents import build_crew
from core.calculator import run_deterministic_calculator

print("="*80)
print("🧪 ПРЯМОЙ ТЕСТ ПАЙПЛАЙНА (БЕЗ API)")
print("="*80)

# Инициализация
print("\n1. Подключение к MongoDB...")
try:
    db = get_db()
    sections_count = db.sections.count_documents({})
    tables_count = db.tables.count_documents({})
    print(f"   ✓ База подключена")
    print(f"   ✓ Sections: {sections_count}, Tables: {tables_count}")
except Exception as e:
    print(f"   ✗ Ошибка подключения: {e}")
    sys.exit(1)

print("\n2. Создание CrewAI...")
try:
    crew = build_crew(db)
    print(f"   ✓ Crew создан")
    print(f"   ✓ Модель: {crew.ollama_model}")
except Exception as e:
    print(f"   ✗ Ошибка создания crew: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Простой тестовый payload
test_payload = {
    "raw_text": "Жилой дом Секция 1 12 этажей м2 4675,08 табл. 1706-0201-01 поз.7 стоимость 52690700 тенге монолитное сейсмичность 7 баллов",
    "row_index": 1,
    "page_number": 1
}

print("\n3. Тестовый payload:")
print(f"   {test_payload['raw_text'][:80]}...")

print("\n4. Запуск Crew (может занять до 2 минут)...")
try:
    state = crew.run(test_payload)
    print(f"   ✓ Crew выполнен успешно!")
    
    print("\n5. Результаты:")
    print("\n   📋 Raw Input (Structurer Agent):")
    if state.raw_input:
        print(f"      Описание: {state.raw_input.text_description}")
        print(f"      Таблица: {state.raw_input.table_code_claimed}")
        print(f"      Позиция: {state.raw_input.position_number}")
        print(f"      Объем X: {state.raw_input.X_claimed}")
        print(f"      Стоимость: {state.raw_input.total_claimed:,.0f}")
        print(f"      Теги: {state.raw_input.extracted_tags}")
    
    print("\n   🔍 Reference Data (Auditor Agent):")
    if state.reference_data:
        print(f"      param_a: {state.reference_data.ref_A}")
        print(f"      param_b: {state.reference_data.ref_B}")
        print(f"      Коэффициенты: {len(state.reference_data.valid_coefficients)}")
        for c in state.reference_data.valid_coefficients:
            print(f"        - {c.value}: {c.reason[:50]}...")
    
    print("\n6. Запуск калькулятора...")
    state = run_deterministic_calculator(state)
    
    print("\n   💰 Audit Verdict (Calculator):")
    print(f"      Расчетная стоимость: {state.audit_verdict.calculated_total:,.2f} тыс. тенге")
    print(f"      Одобрено: {'✅ ДА' if state.audit_verdict.is_approved else '❌ НЕТ'}")
    print(f"      Причина: {state.audit_verdict.reason}")
    
    print("\n" + "="*80)
    print("✅ ТЕСТ ПРОЙДЕН УСПЕШНО!")
    print("="*80)
    
    # Сохраняем результат
    with open('test_direct_result.json', 'w', encoding='utf-8') as f:
        json.dump(state.model_dump(), f, indent=2, ensure_ascii=False)
    print("\nРезультат сохранен в: test_direct_result.json")
    
except Exception as e:
    print(f"\n   ✗ Ошибка выполнения: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

