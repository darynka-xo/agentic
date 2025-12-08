#!/usr/bin/env python3
"""
Тест пайплайна с правильным годом (2023) из сметы
"""
import os
import json

os.environ["MONGO_URI"] = "mongodb+srv://admin:3ZtOrKrs6YWiHfJq@scp-dev.osqjof9.mongodb.net/?appName=scp-dev"
os.environ["MONGO_DB_NAME"] = "scp_verification_dev"
os.environ["OLLAMA_MODEL"] = "ollama/qwen2.5:7b"
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"

from config import get_db
from agents import build_crew
from core.calculator import run_deterministic_calculator

print("="*80)
print("🧪 ТЕСТ С ГОДОМ 2023 (из реальной сметы)")
print("="*80)

# Реальные данные из сметы 05-01 Расчет ПИР_Атамура 2
# В смете указано: "СЦП РК 8.03-01-2023"
# а= 10 637 тыс.тенге, в= 3,16 тыс.тенге
# Коэффициенты: К2=1,2 (РП), К3=1,2 (монолитное), К4=1,2 (сейсмичность), 
#               К5=1,2 (просадочный грунт), К6=1 (все части РП)
# Итого: 52 690 700 тенге

test_payload = {
    "raw_text": """1 Жилой дом Секция 1 12 этажей м2 4 675,08 
    Сборник цен на проектные работы СЦП РК 8.03-01-2023 раздел 6 
    табл. 1706-0201-01 п.7 
    а= 10 637 тыс.тенге в= 3,16 тыс.тенге 
    К2= 1,2 (РП) К3= 1,2 здание монолитное К4= 1,2 Сейсмичность 7 баллов 
    К5= 1,2 Просадочный грунт К6= 1 все части РП 
    52 690 700""",
    "row_index": 1,
    "page_number": 1
}

print(f"\n📋 Входные данные:")
print(f"  Смета: Жилой дом Секция 1 12 этажей")
print(f"  Год СЦП: 2023")
print(f"  Таблица: 1706-0201-01, позиция 7")
print(f"  Объем: 4,675.08 м2")
print(f"  Стоимость: 52,690,700 тенге")
print(f"  Коэффициенты: K2=1.2, K3=1.2, K4=1.2, K5=1.2, K6=1")

print("\n" + "="*80)
print("🚀 Запуск пайплайна...")
print("="*80)

db = get_db()
crew = build_crew(db)

try:
    state = crew.run(test_payload)
    
    print("\n✅ Crew выполнен!")
    
    # Показываем результаты
    print("\n📊 РЕЗУЛЬТАТЫ:")
    print("="*80)
    
    if state.raw_input:
        print("\n1️⃣ ИЗВЛЕЧЕНО (Structurer Agent):")
        print(f"  • Таблица: {state.raw_input.table_code_claimed}")
        print(f"  • Позиция: {state.raw_input.position_number}")
        print(f"  • Год: {state.raw_input.year}")
        print(f"  • Объем: {state.raw_input.X_claimed}")
        print(f"  • Стоимость: {state.raw_input.total_claimed:,.0f} тенге")
    
    if state.reference_data:
        print("\n2️⃣ НАЙДЕНО В БД (Auditor Agent):")
        print(f"  • param_a: {state.reference_data.ref_A} тыс. тенге")
        print(f"  • param_b: {state.reference_data.ref_B} тыс. тенге")
        print(f"  • Position: {state.reference_data.source_position_id}")
    
    # Запускаем калькулятор
    state = run_deterministic_calculator(state)
    
    if state.audit_verdict:
        print("\n3️⃣ РАСЧЕТ (Calculator):")
        calc = state.audit_verdict.calculated_total
        claim = state.raw_input.total_claimed / 1000  # Конвертируем в тыс. тенге
        
        print(f"  • Формула: C = a + b × V")
        print(f"  • Расчет: C = {state.reference_data.ref_A} + {state.reference_data.ref_B} × {state.raw_input.X_claimed}")
        print(f"  • Базовая стоимость: {calc:,.2f} тыс. тенге")
        print(f"  • Заявленная стоимость: {claim:,.2f} тыс. тенге")
        print(f"  • Разница: {abs(calc - claim):,.2f} тыс. тенге")
        print(f"  • Одобрено: {'✅ ДА' if state.audit_verdict.is_approved else '❌ НЕТ'}")
    
    print("\n" + "="*80)
    print("📝 АНАЛИЗ:")
    print("="*80)
    
    # Проверим для 2023 года с коэффициентами
    a_2023 = 10637.0
    b_2023 = 3.16
    volume = state.raw_input.X_claimed
    
    base_2023 = a_2023 + b_2023 * volume
    with_coeffs = base_2023 * 1.2 * 1.2 * 1.2 * 1.2 * 1.0
    
    print(f"\nЕсли использовать год 2023:")
    print(f"  Базовая: {base_2023:,.2f} тыс. тенге")
    print(f"  С коэффициентами (1.2×1.2×1.2×1.2×1.0): {with_coeffs:,.2f} тыс. тенге")
    print(f"  Заявленная: {claim:,.2f} тыс. тенге")
    print(f"  Разница: {abs(with_coeffs - claim):,.2f} тыс. тенге ({abs(with_coeffs - claim)/claim*100:.1f}%)")
    
    if abs(with_coeffs - claim) < claim * 0.01:  # Менее 1%
        print(f"\n  ✅ ТОЧНОЕ СОВПАДЕНИЕ! (разница < 1%)")
    elif abs(with_coeffs - claim) < claim * 0.05:  # Менее 5%
        print(f"\n  ✅ БЛИЗКОЕ СОВПАДЕНИЕ! (разница < 5%)")
    
    # Сохраняем результат
    with open('test_year_2023_result.json', 'w', encoding='utf-8') as f:
        json.dump(state.model_dump(), f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print("✅ ТЕСТ ЗАВЕРШЕН!")
    print("="*80)
    print(f"\nРезультат: test_year_2023_result.json")
    
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()

