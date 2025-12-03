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
    """
    LitServe entry point. LitServe automatically executes methods in order:
    decode_request -> predict -> encode_response for every inbound HTTP call.
    """

    def setup(self, device: str | None = None):
        self.db = get_db()
        self.crew = build_crew(self.db)

    # -------------------------------------------------------------------------
    # FIX: Change type hint to Dict[str, Any] to force Body parsing
    # -------------------------------------------------------------------------
    def decode_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        LitServe passes the raw JSON body as a dictionary.
        We manually validate it against RequestBody here.
        """
        # 1. Parse the raw dict into your Pydantic model
        validated_data = RequestBody(**request)
        
        # 2. Return the inner payload required by predict()
        return validated_data.tabula_json

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