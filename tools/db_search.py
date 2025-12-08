from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

try:
    from fuzzywuzzy import fuzz  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    fuzz = None

logger = logging.getLogger(__name__)


class DBSearchInput(BaseModel):
    table_code_claimed: str = Field(..., description="Table code from Smeta (e.g., '1701-0207-01')")
    position_number: int = Field(..., description="Position number from Smeta (e.g., 24)")
    x_claimed: float = Field(..., description="Volume/area value for calculation (e.g., 2.5)")
    year: int = Field(2024, description="SCP year (2019-2025), defaults to 2024 if not specified")
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
        position_number: int,
        x_claimed: float,
        year: int = 2024,
        extracted_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # Найти таблицу (с учетом года)
        table_data = self._find_section(table_code_claimed, year)
        
        # Найти конкретную позицию по номеру (согласно инструкции)
        matching_row = self._match_row_by_position(table_data, position_number)
        
        # Найти применимые коэффициенты
        coefficients = self._match_coefficients(
            table_code_claimed, extracted_tags or []
        )

        # Extract values from MongoDB structure
        # Проверяем наличие param_a и param_b (обязательные для расчета)
        param_a = matching_row.get("param_a")
        param_b = matching_row.get("param_b")
        k1 = matching_row.get("k1")  # Коэффициент для стадии "Проект"
        k2 = matching_row.get("k2")  # Коэффициент для стадии "РП/РД"
        
        if param_a is None or param_b is None:
            logger.warning(f"Position {position_number} missing param_a or param_b")
        
        # Добавляем k1 и k2 как коэффициенты если они есть
        all_coefficients = list(coefficients)  # Копируем коэффициенты из поиска по тегам
        
        # Добавляем k2 если есть (для стадии РП/РД - обычно это основной коэффициент)
        if k2 is not None and k2 != 1.0:
            all_coefficients.append({
                "id": "k2_stage",
                "value": float(k2),
                "reason": "Коэффициент стадийности K2 (РП/РД)"
            })
        
        # Добавляем k1 если есть и k2 нет (для стадии Проект)
        if k1 is not None and k1 != 1.0 and k2 is None:
            all_coefficients.append({
                "id": "k1_stage",
                "value": float(k1),
                "reason": "Коэффициент стадийности K1 (Проект)"
            })
        
        logger.info(f"Found {len(all_coefficients)} coefficients for position {position_number}")
        
        return {
            "ref_A": float(param_a) if param_a is not None else 0.0,
            "ref_B": float(param_b) if param_b is not None else 0.0,
            "range_min": 0.0,  # Диапазон не используется в новой логике
            "range_max": 999999.0,  # Большое число вместо Infinity для JSON-совместимости
            "formula_strategy": "standard",  # Всегда standard, т.к. ищем по position_number
            "valid_coefficients": all_coefficients,
            "source_position_id": matching_row.get("position_id"),
        }

    # CrewAI uses the same hook for synchronous and asynchronous execution.
    async def _arun(self, *args, **kwargs):  # pragma: no cover - crewai hook
        return self._run(*args, **kwargs)

    def _find_section(self, table_code: str, year: int = 2024) -> Dict[str, Any]:
        """
        Find a table by table_code and year directly from 'tables' collection.
        As per ИНСТРУКЦИЯ_ДЛЯ_АГЕНТА.md
        """
        logger.info(f"Searching for table_code: {table_code}, year: {year}")
        
        # Check database connection
        try:
            tables_count = self._db["tables"].count_documents({})
            logger.info(f"Connected to database. Tables collection has {tables_count} documents")
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        
        # Query directly from 'tables' collection с указанным годом
        # Согласно инструкции: db.tables.aggregate([{'$match': {'table_code': '...', 'year': year}}])
        result = self._db["tables"].find_one({
            "table_code": table_code,
            "year": year
        })
        
        if not result:
            logger.warning(f"No table found for {table_code} in year {year}")
            
            # Попробуем найти в других годах
            all_years = self._db["tables"].find(
                {"table_code": table_code}
            ).sort("year", -1).limit(5)
            
            available_years = [t.get("year") for t in all_years]
            if available_years:
                logger.info(f"Table {table_code} available in years: {available_years}")
                # Используем последний доступный год
                latest_year = max(available_years)
                result = self._db["tables"].find_one({
                    "table_code": table_code,
                    "year": latest_year
                })
                logger.info(f"Using year {latest_year} instead of {year}")
            else:
                logger.error(f"Table {table_code} not found in any year")
                raise ValueError(f"No table found in SCP reference for code {table_code}.")
        
        logger.info(f"Found table: {result.get('table_code')} year {result.get('year')} ({result.get('name_ru', 'N/A')[:50]}...)")
        
        # Get positions from the table
        rows = result.get("positions", [])
        if not rows:
            logger.error(f"Table {table_code} has no positions")
            raise ValueError(f"Table {table_code} has no configured positions.")
        
        logger.info(f"Found table {table_code} with {len(rows)} positions")
        
        # Return a dict with table info and rows (positions)
        return {
            "code": table_code,
            "name_ru": result.get("name_ru"),
            "rows": rows,
            "table": result
        }

    def _match_row_by_position(
        self, table_data: Dict[str, Any], position_number: int
    ) -> Dict[str, Any]:
        """
        Найти позицию по номеру (position_number).
        Согласно ИНСТРУКЦИЯ_ДЛЯ_АГЕНТА.md - ищем по position_number из сметы.
        """
        rows = table_data.get("rows") or []
        
        if not rows:
            raise ValueError(
                f"No positions found for table {table_data.get('code')}."
            )
        
        # Ищем позицию с указанным номером
        for row in rows:
            # Пропускаем подзаголовки
            if row.get("is_subtitle", False):
                continue
            
            # Проверяем номер позиции
            row_pos_num = row.get("position_number")
            if row_pos_num == position_number:
                logger.info(
                    f"Found position {position_number}: {row.get('object_name', 'N/A')[:50]}..."
                )
                return row
        
        # Если не нашли точное совпадение
        logger.error(f"Position {position_number} not found in table {table_data.get('code')}")
        logger.info(f"Available positions: {[r.get('position_number') for r in rows if not r.get('is_subtitle')][:10]}")
        raise ValueError(
            f"Position {position_number} not found in table {table_data.get('code')}. "
            f"Check position number in Smeta."
        )

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

