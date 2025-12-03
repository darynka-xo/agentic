from __future__ import annotations
from typing import Any, Dict
import litserve as ls
from pydantic import BaseModel
from agents import build_crew
from config import get_db
from core.calculator import run_deterministic_calculator


class RequestBody(BaseModel):
    tabula_json: Dict[str, Any]
    

class EstimateValidatorAPI(ls.LitAPI):
    def setup(self, device: str | None = None):
        self.db = get_db()
        self.crew = build_crew(self.db)

    def decode_request(self, request: RequestBody) -> Dict[str, Any]:
        """
        LitServe/FastAPI will automatically parse and validate the JSON body against RequestBody.
        If validation fails, it returns a 422 error with details.
        """
        return request.tabula_json

    def predict(self, tabula_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single Tabula extracted row. Returns the fully populated
        RowState model (as a dict) or an error descriptor.
        """
        state = self.crew.run(tabula_json)
        state = run_deterministic_calculator(state)
        return state.model_dump()

    def encode_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrap the RowState (or error) into a consistent API contract so clients
        always receive an `output` envelope.
        """
        return {"output": response}


if __name__ == "__main__":
    api = EstimateValidatorAPI()
    server = ls.LitServer(api, timeout=30)
    server.run(port=8000)