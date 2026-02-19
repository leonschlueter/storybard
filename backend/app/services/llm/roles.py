from __future__ import annotations

import time
import structlog

from app.core.config import settings
from app.services.llm.ollama_client import OllamaClient
from app.services.llm.schemas import (
    IntentOut,
    CheckAdviceOut,
    KnowledgeSelectionOut,
    GMPlannerOut,
    NarratorOut,
    MemoryOut,
    ThreadAdvanceOut,
    CampaignSeedOut,
)

from app.services.llm.prompts.intent import build_intent_prompt
from app.services.llm.prompts.check import build_check_prompt
from app.services.llm.prompts.knowledge import build_knowledge_prompt
from app.services.llm.prompts.gm_planner import build_gm_planner_prompt
from app.services.llm.prompts.narrator import build_narrator_prompt
from app.services.llm.prompts.memory import build_memory_prompt
from app.services.llm.prompts.thread import build_thread_prompt
from app.services.llm.prompts.seeder import build_seeder_prompt

log = structlog.get_logger()

MAX_LOG_LEN = 8000  # avoid terminal flooding


# ---------------------------------------------------
# Logging Helpers
# ---------------------------------------------------

def log_llm_input(role: str, system: str, user: str):
    log.info(
        "llm_input",
        role=role,
        system=system[:MAX_LOG_LEN],
        user=user[:MAX_LOG_LEN],
    )


def log_llm_output(role: str, output):
    try:
        data = output.model_dump()
    except Exception:
        data = str(output)

    log.info(
        "llm_output",
        role=role,
        output=data,
    )


def log_llm_latency(role: str, ms: float):
    log.info(
        "llm_latency",
        role=role,
        latency_ms=round(ms, 2),
    )


# ---------------------------------------------------
# Roles
# ---------------------------------------------------

class LLMRoles:
    def __init__(self, client: OllamaClient):
        self.client = client

    # ---------- Intent ----------
    def parse_intent(self, *, player_text: str, mode: str) -> IntentOut:
        system, user = build_intent_prompt(player_text=player_text, mode=mode)

        log_llm_input("intent", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("intent"),
            system=system,
            user=user,
            output_model=IntentOut,
            temperature=0.1,
        )
        log_llm_latency("intent", (time.perf_counter() - t0) * 1000)
        log_llm_output("intent", out)

        return out

    # ---------- Check Advisor ----------
    def advise_check(
        self,
        *,
        player_text: str,
        mode: str,
        mechanics_snapshot: dict,
        location_name: str | None,
    ) -> CheckAdviceOut:

        system, user = build_check_prompt(
            player_text=player_text,
            mode=mode,
            mechanics_snapshot=mechanics_snapshot,
            location_name=location_name,
        )

        log_llm_input("check", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("check"),
            system=system,
            user=user,
            output_model=CheckAdviceOut,
            temperature=0.2,
        )
        log_llm_latency("check", (time.perf_counter() - t0) * 1000)
        log_llm_output("check", out)

        return out

    # ---------- Knowledge Selection ----------
    def select_knowledge(
        self,
        *,
        player_text: str,
        mode: str,
        catalogs: dict,
    ) -> KnowledgeSelectionOut:

        system, user = build_knowledge_prompt(
            player_text=player_text,
            mode=mode,
            catalogs=catalogs,
        )

        log_llm_input("knowledge", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("knowledge"),
            system=system,
            user=user,
            output_model=KnowledgeSelectionOut,
            temperature=0.1,
        )
        log_llm_latency("knowledge", (time.perf_counter() - t0) * 1000)
        log_llm_output("knowledge", out)

        return out

    # ---------- GM Planner ----------
    def gm_plan(self, *, payload: dict) -> GMPlannerOut:
        system, user = build_gm_planner_prompt(payload=payload)

        log_llm_input("gm_plan", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("gm"),
            system=system,
            user=user,
            output_model=GMPlannerOut,
            temperature=0.3,
        )
        log_llm_latency("gm_plan", (time.perf_counter() - t0) * 1000)
        log_llm_output("gm_plan", out)

        return out

    # ---------- Narrator ----------
    def narrate(self, *, payload: dict) -> NarratorOut:
        system, user = build_narrator_prompt(payload=payload)

        log_llm_input("narrator", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("narrator"),
            system=system,
            user=user,
            output_model=NarratorOut,
            temperature=0.7,
        )
        log_llm_latency("narrator", (time.perf_counter() - t0) * 1000)
        log_llm_output("narrator", out)

        return out

    # ---------- Memory Regression ----------
    def regress_memory(self, *, payload: dict) -> MemoryOut:
        system, user = build_memory_prompt(payload=payload)

        log_llm_input("memory", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("memory"),
            system=system,
            user=user,
            output_model=MemoryOut,
            temperature=0.2,
        )
        log_llm_latency("memory", (time.perf_counter() - t0) * 1000)
        log_llm_output("memory", out)

        return out

    # ---------- Thread Advancement ----------
    def advance_threads(self, *, payload: dict) -> ThreadAdvanceOut:
        system, user = build_thread_prompt(payload=payload)

        log_llm_input("thread", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("thread"),
            system=system,
            user=user,
            output_model=ThreadAdvanceOut,
            temperature=0.2,
        )
        log_llm_latency("thread", (time.perf_counter() - t0) * 1000)
        log_llm_output("thread", out)

        return out

    # ---------- Campaign Seeder ----------
    def seed_campaign(self, *, payload: dict) -> CampaignSeedOut:
        system, user = build_seeder_prompt(payload=payload)

        log_llm_input("seeder", system, user)

        t0 = time.perf_counter()
        out = self.client.structured_chat(
            model=settings.model_for("seeder"),
            system=system,
            user=user,
            output_model=CampaignSeedOut,
            temperature=0.3,
        )
        log_llm_latency("seeder", (time.perf_counter() - t0) * 1000)
        log_llm_output("seeder", out)

        return out
