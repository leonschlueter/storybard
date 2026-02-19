from __future__ import annotations
from prometheus_client import Counter, Histogram

TURN_COUNTER = Counter("storybard_turns_total", "Total turns processed", ["result"])
LLM_CALL_COUNTER = Counter("storybard_llm_calls_total", "Total LLM calls", ["role", "status"])
PIPELINE_SECONDS = Histogram("storybard_pipeline_seconds", "Turn pipeline duration in seconds")
LLM_SECONDS = Histogram("storybard_llm_seconds", "LLM call duration in seconds", ["role"])
