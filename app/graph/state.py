from typing import TypedDict


class StageState(TypedDict):
    keywords: list[str]
    analysis: str
    chat_history: list[dict]
    approved: bool
    last_intent: str | None


def new_stage_state() -> StageState:
    return {
        "keywords": [],
        "analysis": "",
        "chat_history": [],
        "approved": False,
        "last_intent": None,
    }


class PicoState(TypedDict):
    idea: str
    market_research: StageState
    pestel: StageState
    competitor_analysis: StageState
    draft: str
