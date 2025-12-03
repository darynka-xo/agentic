from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

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
    args_schema: Type[BaseModel] = DBSearchInput

    _db: Any = PrivateAttr()

    def __init__(self, db):
        super().__init__()
        self._db = db

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

        # Extract values from MongoDB structure
        range_obj = matching_row.get("range", {})
        
        return {
            "ref_A": float(matching_row.get("param_a", 0)),
            "ref_B": float(matching_row.get("param_b", 0)),
            "range_min": float(range_obj.get("min", 0)),
            "range_max": float(range_obj.get("max", 0)),
            "formula_strategy": strategy,
            "valid_coefficients": coefficients,
            "source_position_id": matching_row.get("position_id"),
        }

    # CrewAI uses the same hook for synchronous and asynchronous execution.
    async def _arun(self, *args, **kwargs):  # pragma: no cover - crewai hook
        return self._run(*args, **kwargs)

    def _find_section(self, table_code: str) -> Dict[str, Any]:
        """
        Find a table by table_code in the nested MongoDB structure.
        Structure: sections -> subsections -> chapters -> tables
        """
        # Query for a section document that contains the table_code in its nested structure
        # Use MongoDB's dot notation to search within nested arrays
        result = self._db["sections"].find_one(
            {"subsections.chapters.tables.table_code": table_code}
        )
        
        if not result:
            raise ValueError(f"No section found in SCP reference for code {table_code}.")
        
        # Now navigate the nested structure to find the specific table
        for subsection in result.get("subsections", []):
            for chapter in subsection.get("chapters", []):
                for table in chapter.get("tables", []):
                    if table.get("table_code") == table_code:
                        # Found the table! Return it with rows
                        rows = table.get("positions", [])
                        if not rows:
                            raise ValueError(f"Table {table_code} has no configured positions.")
                        # Return a dict with table info and rows
                        return {
                            "code": table_code,
                            "name_ru": table.get("name_ru"),
                            "rows": rows,
                            "table": table
                        }
        
        raise ValueError(f"Table {table_code} found in section but could not extract positions.")

    def _match_row(self, section: Dict[str, Any], x_value: float):
        rows = section.get("rows") or []
        matching_row = None
        strategy = "standard"

        # Filter out subtitle rows
        data_rows = [r for r in rows if not r.get("is_subtitle", False)]
        
        if not data_rows:
            raise ValueError(f"No data rows found for code {section.get('code')}.")

        for row in data_rows:
            # MongoDB structure has range.min and range.max
            range_obj = row.get("range", {})
            min_value = float(range_obj.get("min", float("-inf")))
            max_value = float(range_obj.get("max", float("inf")))
            
            if min_value <= x_value <= max_value:
                matching_row = row
                break

        if not matching_row:
            # Find row with highest max value for extrapolation
            max_row = max(data_rows, key=lambda r: float(r.get("range", {}).get("max", float("-inf"))))
            max_range = float(max_row.get("range", {}).get("max", 0))
            
            if x_value > max_range:
                matching_row = max_row
                strategy = "extrapolation_above"
            else:
                # Check if it's below minimum
                min_row = min(data_rows, key=lambda r: float(r.get("range", {}).get("min", float("inf"))))
                min_range = float(min_row.get("range", {}).get("min", float("inf")))
                
                if x_value < min_range:
                    matching_row = min_row
                    strategy = "extrapolation_below"
                else:
                    raise ValueError(
                        f"Value X={x_value} is out of range for code {section.get('code')}."
                    )

        return matching_row, strategy

    def _match_coefficients(
        self, table_code: str, extracted_tags: List[str]
    ) -> List[Dict[str, Any]]:
        if not extracted_tags:
            return []

        coefficients = self._db["coefficients"].find({"applies_to.codes": table_code})
        matched: List[Dict[str, Any]] = []
        lowered_tags = [tag.lower() for tag in extracted_tags]

        for coef in coefficients:
            condition = (coef.get("condition_full") or "").lower()
            if not condition:
                continue

            if self._condition_matches(condition, lowered_tags):
                matched.append(
                    {
                        "id": coef.get("_id"),
                        "value": float(coef.get("coefficient_value", 1.0)),
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

