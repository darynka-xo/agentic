from __future__ import annotations

from math import prod
from typing import Optional, List, Dict

from core.state import ReferenceData, RowState, Discrepancy, CalculationBreakdown


def _compute_base(reference: ReferenceData, x_given: float) -> float:
    a = reference.ref_A
    b = reference.ref_B
    strategy = reference.formula_strategy

    if strategy == "standard":
        return a + b * x_given

    if strategy == "extrapolation_above":
        return a + b * (0.4 * reference.range_max + 0.6 * x_given)

    if strategy == "extrapolation_below":
        return a + b * (0.6 * reference.range_min + 0.4 * x_given)

    raise ValueError(f"Unknown formula strategy '{strategy}'.")


def _coeff_product(reference: ReferenceData, raw_input=None) -> float:
    """
    Применяет ВСЕ коэффициенты:
    1. Из БД (reference.valid_coefficients) - k2, условия и т.д.
    2. Из текста сметы (raw_input.claimed_coefficients) - K3-K7
    
    Валидация: коэффициенты должны быть в пределах 0.1 - 10.0
    """
    all_coefficients = []
    
    # Коэффициенты из БД
    if reference.valid_coefficients:
        for coef in reference.valid_coefficients:
            # Проверяем что value не None и в разумных пределах
            if coef.value is not None and 0.1 <= coef.value <= 10.0:
                all_coefficients.append(coef)
    
    # Коэффициенты из текста сметы (K3-K7)
    # НЕ берем K1, K2 - они уже в БД!
    if raw_input and hasattr(raw_input, 'claimed_coefficients') and raw_input.claimed_coefficients:
        for coef in raw_input.claimed_coefficients:
            # Пропускаем None values
            if coef.value is None:
                continue
                
            # Пропускаем K1, K2 (они уже в БД)
            if coef.id and coef.id.upper() in ['K1', 'K2', 'К1', 'К2']:
                continue
            
            # Валидация: разумные пределы
            if 0.1 <= coef.value <= 10.0:
                all_coefficients.append(coef)
    
    if not all_coefficients:
        return 1.0
    
    return prod(coef.value for coef in all_coefficients)


def _detect_discrepancies(
    state: RowState,
    base: float,
    calculated_total: float,
    claimed_in_thousands: float,
    all_coefficients: List,
    delta_percent: float
) -> List[Discrepancy]:
    """
    Определяет детальные несоответствия в расчетах
    """
    discrepancies = []
    
    # 1. Проверка года СЦП
    claimed_year = state.raw_input.year
    # Определяем актуальный год из source_position_id если есть
    if state.reference_data.source_position_id:
        # Например: "1706-0201-01-7-2023" -> год 2023
        parts = state.reference_data.source_position_id.split('-')
        if len(parts) >= 5 and parts[-1].isdigit() and len(parts[-1]) == 4:
            db_year = int(parts[-1])
            if claimed_year != db_year:
                discrepancies.append(Discrepancy(
                    type="year_mismatch",
                    severity="critical",
                    message=f"Использован Сборник цен на проектные работы (СЦП) за неверный период. Указан {claimed_year} год, но должен быть {db_year} год.",
                    details={
                        "claimed_year": claimed_year,
                        "correct_year": db_year,
                        "source_table": state.raw_input.table_code_claimed
                    }
                ))
    
    # 2. Проверка постоянных величин (A и B)
    if delta_percent > 5.0:
        ref_a = state.reference_data.ref_A
        ref_b = state.reference_data.ref_B
        
        # Если есть значительное отклонение, возможно использованы неверные константы
        discrepancies.append(Discrepancy(
            type="constant_mismatch",
            severity="critical",
            message=f"Применены неверные постоянные величины стоимости разработки рабочей документации. A={ref_a:.2f}, B={ref_b:.2f}",
            details={
                "ref_A": ref_a,
                "ref_B": ref_b,
                "table_code": state.raw_input.table_code_claimed,
                "position": state.raw_input.position_number
            }
        ))
    
    # 3. Проверка коэффициентов
    db_coeffs = [c for c in state.reference_data.valid_coefficients if c.value is not None]
    claimed_coeffs = [c for c in state.raw_input.claimed_coefficients if c.value is not None and c.id and c.id.upper() not in ['K1', 'K2', 'К1', 'К2']]
    
    if len(claimed_coeffs) > 0:
        # Проверяем каждый заявленный коэффициент
        for coef in claimed_coeffs:
            if coef.value and (coef.value < 0.5 or coef.value > 3.0):
                discrepancies.append(Discrepancy(
                    type="coefficient_unusual",
                    severity="warning",
                    message=f"Применен необычный коэффициент {coef.id}={coef.value}. Стандартные значения находятся в диапазоне 0.5-3.0.",
                    details={
                        "coefficient_id": coef.id,
                        "value": coef.value,
                        "reason": coef.reason
                    }
                ))
    
    # 4. Проверка диапазона X
    x_given = state.raw_input.X_claimed
    range_min = state.reference_data.range_min
    range_max = state.reference_data.range_max
    
    if x_given < range_min or x_given > range_max:
        discrepancies.append(Discrepancy(
            type="value_out_of_range",
            severity="warning",
            message=f"Количественный показатель X={x_given:.2f} выходит за пределы нормативного диапазона [{range_min:.2f}, {range_max:.2f}].",
            details={
                "X_claimed": x_given,
                "range_min": range_min,
                "range_max": range_max,
                "extrapolation_used": state.reference_data.formula_strategy
            }
        ))
    
    # 5. Значительное отклонение в расчетах
    if delta_percent > 5.0:
        delta = abs(calculated_total - claimed_in_thousands)
        discrepancies.append(Discrepancy(
            type="calculation_deviation",
            severity="critical",
            message=f"Обнаружено значительное отклонение в расчетах: {delta:.2f} тыс.тг ({delta_percent:.2f}%). Допустимое отклонение: ≤5%.",
            details={
                "calculated": calculated_total,
                "claimed": claimed_in_thousands,
                "deviation_amount": delta,
                "deviation_percent": delta_percent,
                "tolerance": 5.0
            }
        ))
    
    return discrepancies


def _build_calculation_breakdown(
    base: float,
    all_coefficients: List,
    calculated_total: float,
    state: RowState
) -> CalculationBreakdown:
    """
    Создает детальную разбивку расчета
    """
    # Формируем список примененных коэффициентов
    coeffs_applied = []
    
    for coef in all_coefficients:
        coeffs_applied.append({
            "id": coef.id if coef.id else "K",
            "value": coef.value,
            "reason": coef.reason if coef.reason else "Коэффициент из сметы"
        })
    
    # Формируем формулу
    x_val = state.raw_input.X_claimed
    a_val = state.reference_data.ref_A
    b_val = state.reference_data.ref_B
    
    formula_parts = [f"({a_val:.2f} + {b_val:.2f} × {x_val:.2f})"]
    
    if coeffs_applied:
        coeff_str = " × ".join([f"{c['value']:.2f}" for c in coeffs_applied])
        formula_parts.append(f" × {coeff_str}")
    
    formula_used = "".join(formula_parts) + f" = {calculated_total:.2f} тыс.тг"
    
    return CalculationBreakdown(
        base_cost=round(base, 2),
        coefficients_applied=coeffs_applied,
        final_cost=round(calculated_total, 2),
        formula_used=formula_used
    )


def run_deterministic_calculator(
    state: RowState, tolerance: float = 100.0  # Увеличен tolerance для учета погрешностей
) -> RowState:
    """
    Deterministic math that must run after Crew agents complete their steps.
    Raises when mandatory parts of the state are missing.
    Применяет коэффициенты как из БД, так и из текста сметы.
    Генерирует детальный отчет о несоответствиях.
    """
    if state.raw_input is None:
        raise ValueError("RowState.raw_input is empty. Run the structurer agent first.")
    if state.reference_data is None:
        raise ValueError(
            "RowState.reference_data is empty. Run the auditor agent first."
        )

    reference = state.reference_data
    x_given = state.raw_input.X_claimed
    claimed_total = state.raw_input.total_claimed

    # Базовая стоимость по формуле C = a + b × V
    base = _compute_base(reference, x_given)
    
    # Получаем список всех коэффициентов
    all_coefficients = []
    if reference.valid_coefficients:
        for coef in reference.valid_coefficients:
            if coef.value is not None and 0.1 <= coef.value <= 10.0:
                all_coefficients.append(coef)
    
    if state.raw_input.claimed_coefficients:
        for coef in state.raw_input.claimed_coefficients:
            if coef.value is None:
                continue
            if coef.id and coef.id.upper() in ['K1', 'K2', 'К1', 'К2']:
                continue
            if 0.1 <= coef.value <= 10.0:
                all_coefficients.append(coef)
    
    # Применяем ВСЕ коэффициенты (из БД + из текста сметы)
    k_total = prod(coef.value for coef in all_coefficients) if all_coefficients else 1.0
    calculated_total = base * k_total

    # Конвертируем claimed_total в тыс. тенге если нужно
    # (если число > 1 миллиона, скорее всего это тенге, а не тыс. тенге)
    claimed_in_thousands = claimed_total
    if claimed_total > 1_000_000:
        claimed_in_thousands = claimed_total / 1000

    # Проверяем допустимость расхождения
    delta = abs(calculated_total - claimed_in_thousands)
    delta_percent = (delta / claimed_in_thousands * 100) if claimed_in_thousands > 0 else 0
    is_approved = delta_percent <= 5.0  # Допустимое расхождение 5%
    
    reason = (
        "Match within {:.2f}% tolerance".format(delta_percent)
        if is_approved
        else "Deviation {:.2f} тыс.тг ({:.2f}%)".format(delta, delta_percent)
    )

    # Определяем детальные несоответствия
    discrepancies = _detect_discrepancies(
        state, base, calculated_total, claimed_in_thousands,
        all_coefficients, delta_percent
    )
    
    # Создаем детальную разбивку расчета
    breakdown = _build_calculation_breakdown(
        base, all_coefficients, calculated_total, state
    )

    state.audit_verdict.calculated_total = round(calculated_total, 2)
    state.audit_verdict.is_approved = is_approved
    state.audit_verdict.reason = reason
    state.audit_verdict.discrepancies = discrepancies
    state.audit_verdict.calculation_breakdown = breakdown

    return state

