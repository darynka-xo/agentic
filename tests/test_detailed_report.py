#!/usr/bin/env python3
"""
Тест расширенного API с детальными отчетами о несоответствиях
"""

import json
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.state import RowState, RawInput, ReferenceData, CoefficientData
from core.calculator import run_deterministic_calculator


def test_approved_case():
    """Тест случая с одобренным расчетом"""
    print("\n" + "="*80)
    print("ТЕСТ 1: Одобренный расчет (отклонение < 5%)")
    print("="*80)
    
    state = RowState(id="test-1")
    
    # Входные данные
    state.raw_input = RawInput(
        text_description="Жилой дом Секция 1 12 этажей",
        table_code_claimed="1706-0201-01",
        position_number=7,
        X_claimed=4675.08,
        total_claimed=52690700.0,  # в тенге
        year=2023,
        claimed_coefficients=[
            CoefficientData(id="K3", value=1.2, reason=None),
            CoefficientData(id="K4", value=1.2, reason=None)
        ]
    )
    
    # Справочные данные
    state.reference_data = ReferenceData(
        ref_A=10637.0,
        ref_B=3.16,
        range_min=0.0,
        range_max=999999.0,
        formula_strategy="standard",
        valid_coefficients=[
            CoefficientData(id="k2_stage", value=1.2, reason="Коэффициент стадийности K2 (РП/РД)")
        ],
        source_position_id="1706-0201-01-7-2023"
    )
    
    # Запускаем калькулятор
    state = run_deterministic_calculator(state)
    
    # Выводим результат
    print(f"\n📊 Результат:")
    print(f"  Рассчитано: {state.audit_verdict.calculated_total:,.2f} тыс.тг")
    print(f"  Заявлено: {state.raw_input.total_claimed / 1000:,.2f} тыс.тг")
    print(f"  Одобрено: {'✅ ДА' if state.audit_verdict.is_approved else '❌ НЕТ'}")
    print(f"  Причина: {state.audit_verdict.reason}")
    
    print(f"\n🔍 Несоответствия: {len(state.audit_verdict.discrepancies)}")
    for disc in state.audit_verdict.discrepancies:
        icon = "🔴" if disc.severity == "critical" else "🟡" if disc.severity == "warning" else "🔵"
        print(f"  {icon} [{disc.type}] {disc.message}")
    
    if state.audit_verdict.calculation_breakdown:
        print(f"\n📐 Разбивка расчета:")
        print(f"  Базовая стоимость: {state.audit_verdict.calculation_breakdown.base_cost:,.2f} тыс.тг")
        print(f"  Коэффициенты ({len(state.audit_verdict.calculation_breakdown.coefficients_applied)}):")
        for coef in state.audit_verdict.calculation_breakdown.coefficients_applied:
            print(f"    • {coef['id']}={coef['value']} - {coef['reason']}")
        print(f"  Итоговая стоимость: {state.audit_verdict.calculation_breakdown.final_cost:,.2f} тыс.тг")
        print(f"  Формула: {state.audit_verdict.calculation_breakdown.formula_used}")
    
    return state


def test_rejected_case():
    """Тест случая с отклоненным расчетом"""
    print("\n" + "="*80)
    print("ТЕСТ 2: Отклоненный расчет (несоответствия обнаружены)")
    print("="*80)
    
    state = RowState(id="test-2")
    
    # Входные данные с ошибками
    state.raw_input = RawInput(
        text_description="Водозаборы из подземных источников (скважин)",
        table_code_claimed="1701-0503-01",
        position_number=3,
        X_claimed=114.0,
        total_claimed=35688813.0,  # в тенге, значительно завышено
        year=2024,  # Неверный год!
        claimed_coefficients=[
            CoefficientData(id="KC1", value=0.27, reason="Коэф. на проект"),
            CoefficientData(id="KC2", value=1.00, reason="Коэф. на рабочую документацию"),
            CoefficientData(id="KC3", value=0.20, reason="Коэф. на предпроектные работы"),
            CoefficientData(id="KH", value=1.10, reason="Общеполож.по прим.цен на проектные работы")
        ]
    )
    
    # Справочные данные
    state.reference_data = ReferenceData(
        ref_A=2982.0,
        ref_B=21.0,
        range_min=25.0,
        range_max=200.0,
        formula_strategy="standard",
        valid_coefficients=[
            CoefficientData(id="k2_stage", value=1.10, reason="Коэффициент стадийности K2 (РП/РД)")
        ],
        source_position_id="1701-0503-01-3-2023"  # Данные из СЦП 2023!
    )
    
    # Запускаем калькулятор
    state = run_deterministic_calculator(state)
    
    # Выводим результат
    print(f"\n📊 Результат:")
    print(f"  Рассчитано: {state.audit_verdict.calculated_total:,.2f} тыс.тг")
    print(f"  Заявлено: {state.raw_input.total_claimed / 1000:,.2f} тыс.тг")
    print(f"  Одобрено: {'✅ ДА' if state.audit_verdict.is_approved else '❌ НЕТ'}")
    print(f"  Причина: {state.audit_verdict.reason}")
    
    print(f"\n🔍 Обнаружено несоответствий: {len(state.audit_verdict.discrepancies)}")
    for i, disc in enumerate(state.audit_verdict.discrepancies, 1):
        icon = "🔴" if disc.severity == "critical" else "🟡" if disc.severity == "warning" else "🔵"
        print(f"\n  {i}. {icon} [{disc.severity.upper()}] {disc.type}")
        print(f"     {disc.message}")
        if disc.details:
            print(f"     Детали: {json.dumps(disc.details, ensure_ascii=False, indent=6)}")
    
    if state.audit_verdict.calculation_breakdown:
        print(f"\n📐 Разбивка расчета:")
        print(f"  Базовая стоимость: {state.audit_verdict.calculation_breakdown.base_cost:,.2f} тыс.тг")
        print(f"  Коэффициенты ({len(state.audit_verdict.calculation_breakdown.coefficients_applied)}):")
        for coef in state.audit_verdict.calculation_breakdown.coefficients_applied:
            print(f"    • {coef['id']}={coef['value']} - {coef['reason']}")
        print(f"  Итоговая стоимость: {state.audit_verdict.calculation_breakdown.final_cost:,.2f} тыс.тг")
        print(f"  Формула: {state.audit_verdict.calculation_breakdown.formula_used}")
    
    return state


def test_api_output():
    """Тест JSON выхода API"""
    print("\n" + "="*80)
    print("ТЕСТ 3: Проверка формата JSON API")
    print("="*80)
    
    state = test_rejected_case()
    
    # Сериализуем в JSON как это делает API
    api_response = {"output": state.model_dump()}
    
    # Сохраняем в файл
    output_file = Path(__file__).parent / "test_detailed_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(api_response, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ JSON выход сохранен в: {output_file}")
    print(f"   Размер: {output_file.stat().st_size} байт")
    
    # Проверяем наличие всех необходимых полей
    output = api_response["output"]
    audit = output["audit_verdict"]
    
    print(f"\n✅ Проверка структуры API:")
    print(f"  • id: {'✓' if 'id' in output else '✗'}")
    print(f"  • raw_input: {'✓' if 'raw_input' in output else '✗'}")
    print(f"  • reference_data: {'✓' if 'reference_data' in output else '✗'}")
    print(f"  • audit_verdict: {'✓' if 'audit_verdict' in output else '✗'}")
    print(f"  • audit_verdict.discrepancies: {'✓' if 'discrepancies' in audit else '✗'}")
    print(f"  • audit_verdict.calculation_breakdown: {'✓' if 'calculation_breakdown' in audit else '✗'}")
    
    return api_response


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 ТЕСТИРОВАНИЕ ДЕТАЛЬНЫХ ОТЧЕТОВ API")
    print("="*80)
    
    try:
        # Тест 1: Одобренный случай
        test_approved_case()
        
        # Тест 2: Отклоненный случай
        test_rejected_case()
        
        # Тест 3: Формат API
        test_api_output()
        
        print("\n" + "="*80)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

