"""The agent's toolbox.

Each tool is narrow and does one thing (BUILD.md section 37). There is
deliberately no do_everything() tool: the sequence the agent chooses is what
makes its work visible in the activity feed.
"""

from app.agent.tools.application import get_application_link, get_card_sources
from app.agent.tools.calculator import calculate_card_cost
from app.agent.tools.cards import get_card_details, search_cards
from app.agent.tools.fx import get_fx_rate
from app.agent.tools.profile import get_user_profile, update_user_profile
from app.agent.tools.recommendation import compare_cards
from app.agent.tools.research import research_card

ALL_TOOLS = [
    get_user_profile,
    update_user_profile,
    search_cards,
    get_card_details,
    research_card,
    get_fx_rate,
    calculate_card_cost,
    compare_cards,
    get_application_link,
    get_card_sources,
]

__all__ = [
    "ALL_TOOLS",
    "get_user_profile",
    "update_user_profile",
    "search_cards",
    "get_card_details",
    "research_card",
    "get_fx_rate",
    "calculate_card_cost",
    "compare_cards",
    "get_application_link",
    "get_card_sources",
]
