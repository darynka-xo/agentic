from __future__ import annotations

import os
from typing import Any, Dict, Type
from uuid import uuid4

from crewai import Agent, Crew, LLM, Process, Task
from pydantic import BaseModel

from core.state import RawInput, ReferenceData, RowState
from tools.db_search import DBSearchTool


class EstimateValidationCrew:
    """
    Wraps the CrewAI configuration so server code can trigger a full validation
    pass in a single call.
    """

    def __init__(self, db):
        self.db_tool = DBSearchTool(db)
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:30b")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.structurer_agent = self._make_structurer_agent()
        self.auditor_agent = self._make_auditor_agent()

    def run(self, tabula_payload: Dict[str, Any]) -> RowState:
        structurer_task = self._make_structurer_task()
        auditor_task = self._make_auditor_task(structurer_task)

        crew = Crew(
            agents=[self.structurer_agent, self.auditor_agent],
            tasks=[structurer_task, auditor_task],
            process=Process.sequential,
            verbose=False,
        )

        crew.kickoff(inputs={"tabula_payload": tabula_payload})

        raw_input = structurer_task.output.pydantic
        reference_data = auditor_task.output.pydantic
        state = RowState(
            id=str(uuid4()),
            raw_input=raw_input,
            reference_data=reference_data,
        )
        return state

    def _make_structurer_agent(self) -> Agent:
        llm = self._build_llm(RawInput)
        return Agent(
            role="Structurer",
            goal="Transform raw Tabula JSON into the normalized RowState.raw_input.",
            backstory="You specialize in interpreting disorganized construction rows.",
            llm=llm,
            tools=[],
            verbose=False,
        )

    def _make_auditor_agent(self) -> Agent:
        llm = self._build_llm(ReferenceData)
        return Agent(
            role="Auditor",
            goal="Fetch SCP reference constants and coefficients via tools.",
            backstory="You never guess values; you only return DB-backed data.",
            llm=llm,
            tools=[self.db_tool],
            verbose=False,
        )

    def _build_llm(self, response_model: Type[BaseModel]):
        base_url = self.ollama_base_url.rstrip("/") + "/v1"
        return LLM(
            model=self.ollama_model,
            provider="ollama",
            base_url=base_url,
            api_key="ollama",
            temperature=0.0,
            response_format=response_model,
        )

    def _make_structurer_task(self) -> Task:
        schema_hint = RawInput.model_json_schema()
        description = (
            "Use the provided Tabula payload ({{tabula_payload}}) to extract exactly "
            "five fields: text_description, table_code_claimed, X_claimed (float), "
            "total_claimed (float), and extracted_tags (list of strings). "
            "Always respond with valid JSON that matches this schema: "
            f"{schema_hint}. No prose."
        )

        return Task(
            description=description,
            agent=self.structurer_agent,
            expected_output="Valid JSON for RowState.raw_input.",
            output_pydantic=RawInput,
        )

    def _make_auditor_task(self, structurer_task: Task) -> Task:
        schema_hint = ReferenceData.model_json_schema()
        description = (
            "Read the latest RowState.raw_input JSON from the structurer task and call "
            "the db_search tool using table_code_claimed, X_claimed, and extracted_tags. "
            "Do not invent values. Return the JSON from the tool unchanged, making sure "
            f"it conforms to this schema: {schema_hint}."
        )

        return Task(
            description=description,
            agent=self.auditor_agent,
            expected_output="Valid JSON for RowState.reference_data.",
            output_pydantic=ReferenceData,
            context=[structurer_task],
            depends_on=[structurer_task],
        )


def build_crew(db) -> EstimateValidationCrew:
    return EstimateValidationCrew(db)

