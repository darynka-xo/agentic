from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RawInput(BaseModel):
    text_description: str
    table_code_claimed: str
    X_claimed: float
    total_claimed: float
    extracted_tags: List[str] = Field(default_factory=list)


class CoefficientData(BaseModel):
    id: Optional[str]
    value: float
    reason: Optional[str] = None


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


class AuditVerdict(BaseModel):
    calculated_total: Optional[float] = None
    is_approved: bool = False
    reason: Optional[str] = None


class RowState(BaseModel):
    id: str
    raw_input: Optional[RawInput] = None
    reference_data: Optional[ReferenceData] = None
    audit_verdict: AuditVerdict = Field(default_factory=AuditVerdict)

