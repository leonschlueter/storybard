from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class CampaignSettings(Base):
    """One row per campaign, one field per configurable feature — the real, runtime
    "make everything configurable" surface (`GET`/`PATCH /campaigns/{id}/settings`,
    api/campaigns.py), replacing what would otherwise be Python constants. Every consumer
    below reads this row live via context_assembly.py::get_campaign_settings rather than a
    hardcoded default, so toggling a setting takes effect on the next turn with no
    redeploy. See the "All 20 Features, Configurable" plan.

    Everything defaults on/reasonable, matching "add everything" — a campaign seeded
    before this table existed gets one auto-created on first read (get_campaign_settings),
    not a missing-row error.
    """

    __tablename__ = "campaign_settings"

    # Deliberately no ForeignKey — matches every other campaign_id column in this codebase
    # (Actor, Thread, Hook, ItemDef, ...): tests routinely construct entities against a
    # synthetic campaign_id with no real Campaign row, and nothing else here enforces it.
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # --- Seeding enrichment ---
    seed_npc_count: Mapped[int] = mapped_column(Integer, default=3)
    seed_hook_count: Mapped[int] = mapped_column(Integer, default=3)
    seed_npc_relationships: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_rumor_count: Mapped[int] = mapped_column(Integer, default=3)
    # 1 = root location only (pre-existing behavior). 2 = root + N seeded children
    # ("region -> settlement"). See chain/seed_service.py's name-based parent resolution.
    seed_location_depth: Mapped[int] = mapped_column(Integer, default=2)
    seed_calendar_from_pitch: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_always_faction: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_session_zero: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_starting_inventory: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_starting_inventory_count: Mapped[int] = mapped_column(Integer, default=3)
    seed_planted_reveal: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Narration liveliness ---
    narration_npc_offscreen: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_npc_offscreen_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    narration_twist_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_twist_frequency: Mapped[int] = mapped_column(Integer, default=5)
    narration_npc_voices: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_consequence_ledger: Mapped[bool] = mapped_column(Boolean, default=True)
    # 0 disables the hard pacing floor entirely (chain/service.py::resolve_step).
    narration_hard_stagnation_threshold: Mapped[int] = mapped_column(Integer, default=5)
    mechanical_degrees_of_success: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_thinking_gloss: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_oracle_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_npc_memory: Mapped[bool] = mapped_column(Boolean, default=True)
