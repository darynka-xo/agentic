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


def _coeff_product(reference: ReferenceData) -> float:
    if not reference.valid_coefficients:
        return 1.0
    return prod(coef.value for coef in reference.valid_coefficients)


def run_deterministic_calculator(
    state: RowState, tolerance: float = 1.0
) -> RowState:
    """
    Deterministic math that must run after Crew agents complete their steps.
    Raises when mandatory parts of the state are missing.
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

    base = _compute_base(reference, x_given)
    k_total = _coeff_product(reference)
    calculated_total = base * k_total

    delta = abs(calculated_total - claimed_total)
    is_approved = delta <= tolerance
    reason = (
        "Within tolerance ±{:.2f}".format(tolerance)
        if is_approved
        else "Claim deviates by {:.2f} (> {:.2f})".format(delta, tolerance)
    )

    state.audit_verdict.calculated_total = round(calculated_total, 2)
    state.audit_verdict.is_approved = is_approved
    state.audit_verdict.reason = reason

    return state

