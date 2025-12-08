from __future__ import annotations

from math import prod
from typing import Optional

from core.state import ReferenceData, RowState


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


def run_deterministic_calculator(
    state: RowState, tolerance: float = 100.0  # Увеличен tolerance для учета погрешностей
) -> RowState:
    """
    Deterministic math that must run after Crew agents complete their steps.
    Raises when mandatory parts of the state are missing.
    Применяет коэффициенты как из БД, так и из текста сметы.
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
    
    # Применяем ВСЕ коэффициенты (из БД + из текста сметы)
    k_total = _coeff_product(reference, state.raw_input)
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

    state.audit_verdict.calculated_total = round(calculated_total, 2)
    state.audit_verdict.is_approved = is_approved
    state.audit_verdict.reason = reason

    return state

