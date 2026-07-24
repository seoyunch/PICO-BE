from typing import TypedDict

STAGE_ORDER = [
    "market_research",
    "pestel",
    "lean_canvas",
    "competitor_analysis",
    "market_sizing",
    "vpc_features",
    "mvp_roadmap",
]

DRAFT_STAGE = "__draft__"


class StageState(TypedDict):
    keywords: list[str]
    analysis: str
    chat_history: list[dict]
    approved: bool


def new_stage_state() -> StageState:
    return {
        "keywords": [],
        "analysis": "",
        "chat_history": [],
        "approved": False,
    }


class PicoState(TypedDict):
    idea: str
    current_stage: str
    next_route: str
    market_research: StageState
    pestel: StageState
    lean_canvas: StageState
    competitor_analysis: StageState
    market_sizing: StageState
    vpc_features: StageState
    mvp_roadmap: StageState
    draft: str


def new_pico_state(idea: str) -> PicoState:
    state: PicoState = {
        "idea": idea,
        "current_stage": STAGE_ORDER[0],
        "next_route": "",
        "draft": "",
    }
    for stage_key in STAGE_ORDER:
        state[stage_key] = new_stage_state()
    return state
