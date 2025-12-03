from __future__ import annotations

from typing import Any, Dict

import litserve as ls

from agents import build_crew
from config import get_db
from core.calculator import run_deterministic_calculator


class EstimateValidatorAPI(ls.LitAPI):
    """
    LitServe entry point. LitServe automatically executes methods in order:
    decode_request -> predict -> encode_response for every inbound HTTP call.
    """

    def setup(self, device: str | None = None):
        # LitServe passes the worker/device identifier even if it is unused here.
        self.db = get_db()
        self.crew = build_crew(self.db)

    def decode_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the Tabula row JSON from the incoming request body. We allow
        users to send the payload either as `tabula_json` or directly as the
        body for convenience.
        """
        if isinstance(request, dict) and "tabula_json" in request:
            return request["tabula_json"]
        if isinstance(request, dict):
            return request
        raise ValueError("Request body must be a JSON object describing the row.")

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

