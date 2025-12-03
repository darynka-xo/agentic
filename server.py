from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import Body, FastAPI, HTTPException

from agents import build_crew
from config import get_db
from core.calculator import run_deterministic_calculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


app = FastAPI(title="Estimate Validator API")
crew_cache = None


def _init_crew():
    db = get_db()
    return build_crew(db)


@app.on_event("startup")
def on_startup():
    global crew_cache
    logger.info("Starting up server and initializing crew")
    try:
        crew_cache = _init_crew()
        logger.info("Crew initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize crew: {str(e)}", exc_info=True)
        raise


def _extract_payload(request: Dict[str, Any]) -> Dict[str, Any]:
    if "tabula_json" in request:
        tabula_json = request["tabula_json"]
    else:
        tabula_json = request

    if not isinstance(tabula_json, dict):
        raise HTTPException(
            status_code=400, detail="tabula_json payload must be a JSON object."
        )
    return tabula_json


@app.post("/predict")
def predict(tabula_request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    logger.info("Received /predict request")
    
    if crew_cache is None:
        logger.error("Crew cache is None - initialization failed")
        raise HTTPException(status_code=503, detail="Crew initialization pending.")

    tabula_json = _extract_payload(tabula_request)
    logger.info(f"Extracted tabula_json payload with keys: {list(tabula_json.keys())}")
    
    try:
        logger.info("Starting crew run")
        state = crew_cache.run(tabula_json)
        logger.info("Crew run completed successfully")
        
        logger.info("Running deterministic calculator")
        state = run_deterministic_calculator(state)
        logger.info("Calculation completed successfully")
        
        return {"output": state.model_dump()}
    except ValueError as exc:
        logger.error(f"ValueError in predict: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.error(f"Unexpected error in predict: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )