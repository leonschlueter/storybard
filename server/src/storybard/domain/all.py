"""Import every domain model so Base.metadata / Alembic autogenerate can discover them."""

from storybard.domain.actor import Actor, ActorProfile, CharacterSheet  # noqa: F401
from storybard.domain.campaign import Campaign  # noqa: F401
from storybard.domain.campaign_settings import CampaignSettings  # noqa: F401
from storybard.domain.chain_trace import ChainStep, TurnRun  # noqa: F401
from storybard.domain.clock import Clock  # noqa: F401
from storybard.domain.faction import Faction  # noqa: F401
from storybard.domain.hook import Hook  # noqa: F401
from storybard.domain.inventory import InventoryItem  # noqa: F401
from storybard.domain.item import ItemDef  # noqa: F401
from storybard.domain.memory import Memory  # noqa: F401
from storybard.domain.narrator import NarratorProfile  # noqa: F401
from storybard.domain.reveal import PlantedReveal  # noqa: F401
from storybard.domain.ruleset import AncestryDef, AttributeDefinition, ClassDef  # noqa: F401
from storybard.domain.spell import SpellDef  # noqa: F401
from storybard.domain.thread import Thread  # noqa: F401
from storybard.domain.thread_beat import ThreadBeat  # noqa: F401
from storybard.domain.world import WorldNode  # noqa: F401
