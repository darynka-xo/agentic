#!/usr/bin/env python3
"""
Тест пайплайна с разными годами СЦП
"""
import os
from dotenv import load_dotenv

# Загружаем credentials из .env файла
load_dotenv()

if not os.getenv("MONGO_URI"):
    print("❌ ОШИБКА: MONGO_URI не найден в .env файле!")
    print("Скопируйте .env.example в .env и укажите ваши credentials")
    exit(1)

from config import get_db
from tools.db_search import DBSearchTool

db = get_db()
tool = DBSearchTool(db)

# Параметры для теста
table_code = "1706-0201-01"
position = 7
volume = 4675.08

print("="*80)
print("📅 ТЕСТ: Проверка данных СЦП по годам")
print("="*80)
print(f"\nТаблица: {table_code}, Позиция: {position}, Объем: {volume} м2")
print("\n" + "="*80)

# Тест для каждого года
for year in [2019, 2020, 2021, 2022, 2023, 2024, 2025]:
    print(f"\n📅 ГОД {year}:")
    print("-" * 80)
    
    try:
        result = tool._run(
            table_code_claimed=table_code,
            position_number=position,
            x_claimed=volume,
            year=year,
            extracted_tags=[]
        )
        
        param_a = result['ref_A']
        param_b = result['ref_B']
        
        # Расчет базовой стоимости
        base_cost = param_a + param_b * volume
        
        print(f"  ✓ Найдено: a={param_a}, b={param_b}")
        print(f"  💰 Базовая стоимость: {base_cost:,.2f} тыс. тенге")
        print(f"  📊 Формула: C = {param_a} + {param_b} × {volume}")
        
    except Exception as e:
        print(f"  ✗ Ошибка: {str(e)}")

print("\n" + "="*80)
print("📊 ВЫВОД:")
print("="*80)
print("Параметры a и b меняются каждый год!")
print("Важно использовать правильный год из сметы для точной проверки.")
print("="*80)
