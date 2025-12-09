from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CoefficientData(BaseModel):
    id: Optional[str] = None
    value: Optional[float] = None  # Опционально чтобы не ломаться если LLM не может извлечь
    reason: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Проверка что коэффициент валидный для использования"""
        return self.value is not None and 0.1 <= self.value <= 10.0


class RawInput(BaseModel):
    text_description: str
    table_code_claimed: str
    position_number: int  # Номер позиции из сметы (e.g., 24)
    X_claimed: float  # Объем/площадь для расчета (e.g., 2.5)
    total_claimed: float
    year: int = 2024  # Год СЦП (2019-2025), если не указан в смете - используется 2024
    claimed_coefficients: List[CoefficientData] = Field(
        default_factory=list,
        description="Коэффициенты из текста сметы (K3, K4, K5 и т.д.)"
    )
    extracted_tags: List[str] = Field(default_factory=list)


class ReferenceData(BaseModel):
    ref_A: float
    ref_B: float
    range_min: float
    range_max: float
    formula_strategy: Literal[
        "standard", "extrapolation_above", "extrapolation_below"
    ] = "standard"
    valid_coefficients: List[CoefficientData] = Field(default_factory=list)
    source_position_id: Optional[str] = None


class Discrepancy(BaseModel):
    """Детальное описание одного несоответствия"""
    type: str  # Тип несоответствия: "year_mismatch", "coefficient_error", "value_deviation", etc
    severity: str  # "critical", "warning", "info"
    message: str  # Описание на русском языке
    details: Optional[dict] = None  # Дополнительные детали


class CalculationBreakdown(BaseModel):
    """Детальная разбивка расчета"""
    base_cost: Optional[float] = None  # Базовая стоимость (A + B × X)
    coefficients_applied: List[dict] = Field(default_factory=list)  # Примененные коэффициенты
    final_cost: Optional[float] = None  # Итоговая стоимость
    formula_used: Optional[str] = None  # Формула в текстовом виде


class AuditVerdict(BaseModel):
    calculated_total: Optional[float] = None
    is_approved: bool = False
    reason: Optional[str] = None
    discrepancies: List[Discrepancy] = Field(
        default_factory=list,
        description="Список обнаруженных несоответствий"
    )
    calculation_breakdown: Optional[CalculationBreakdown] = Field(
        default=None,
        description="Детальная разбивка расчета"
    )


class RowState(BaseModel):
    id: str
    raw_input: Optional[RawInput] = None
    reference_data: Optional[ReferenceData] = None
    audit_verdict: AuditVerdict = Field(default_factory=AuditVerdict)

