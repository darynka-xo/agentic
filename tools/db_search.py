from __future__ import annotations

from typing import Any, Dict, List, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    from fuzzywuzzy import fuzz  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    fuzz = None


class DBSearchInput(BaseModel):
    table_code_claimed: str = Field(..., description="Table code claimed in Smeta row")
    x_claimed: float = Field(..., description="Primary technical parameter value X")
    extracted_tags: List[str] = Field(
        default_factory=list,
        description="Tags such as seismic or reconstruction extracted by LLM",
    )


class DBSearchTool(BaseTool):
    """
    CrewAI tool that encapsulates the deterministic database lookup logic required
    for each estimate row. It returns the reference constants and coefficient
    modifiers that downstream math relies on.
    """

    name: str = "db_search"
    description: str = (
        "Look up official SCP reference rows and applicable coefficients for the "
        "current estimate line item. Always call this tool with the table code, "
        "numeric X value, and the list of extracted tags."
    )
    args_schema = DBSearchInput

    def __init__(self, db):
        super().__init__()
        self.db = db

    def _run(
        self,
        table_code_claimed: str,
        x_claimed: float,
        extracted_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        section = self._find_section(table_code_claimed)
        matching_row, strategy = self._match_row(section, x_claimed)
        coefficients = self._match_coefficients(
            table_code_claimed, extracted_tags or []
        )

        return {
            "ref_A": float(matching_row.get("a")),
            "ref_B": float(matching_row.get("b")),
            "range_min": float(matching_row.get("min_value", 0)),
            "range_max": float(matching_row.get("max_value", 0)),
            "formula_strategy": strategy,
            "valid_coefficients": coefficients,
            "source_position_id": matching_row.get("position_id"),
        }

    # CrewAI uses the same hook for synchronous and asynchronous execution.
    async def _arun(self, *args, **kwargs):  # pragma: no cover - crewai hook
        return self._run(*args, **kwargs)

    def _find_section(self, code: str) -> Dict[str, Any]:
        section = self.db["sections"].find_one({"code": code})
        if not section:
            raise ValueError(f"No section found in SCP reference for code {code}.")
        rows = section.get("rows") or []
        if not rows:
            raise ValueError(f"Section {code} has no configured rows.")
        return section

    def _match_row(self, section: Dict[str, Any], x_value: float):
        rows = section.get("rows") or []
        matching_row = None
        strategy = "standard"

        for row in rows:
            min_value = float(row.get("min_value", float("-inf")))
            max_value = float(row.get("max_value", float("inf")))
            if min_value <= x_value <= max_value:
                matching_row = row
                break

        if not matching_row:
            max_row = max(rows, key=lambda r: float(r.get("max_value", "-inf")))
            max_range = float(max_row.get("max_value", 0))
            if x_value > max_range:
                matching_row = max_row
                strategy = "extrapolation_above"
            else:
                raise ValueError(
                    f"Value X={x_value} is below the minimum reference range for "
                    f"code {section.get('code')}."
                )

        return matching_row, strategy

    def _match_coefficients(
        self, table_code: str, extracted_tags: List[str]
    ) -> List[Dict[str, Any]]:
        if not extracted_tags:
            return []

        coefficients = self.db["coefficients"].find({"applies_to.codes": table_code})
        matched: List[Dict[str, Any]] = []
        lowered_tags = [tag.lower() for tag in extracted_tags]

        for coef in coefficients:
            condition = (coef.get("condition_full") or "").lower()
            if not condition:
                continue

            if self._condition_matches(condition, lowered_tags):
                matched.append(
                    {
                        "id": coef.get("id"),
                        "value": float(coef.get("value", 1.0)),
                        "reason": coef.get("condition_full"),
                    }
                )

        return matched

    def _condition_matches(self, condition: str, lowered_tags: List[str]) -> bool:
        for tag in lowered_tags:
            if fuzz:
                if fuzz.partial_ratio(tag, condition) >= 65:
                    return True
            elif tag in condition:
                return True
        return False

