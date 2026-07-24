import json
from collections.abc import AsyncIterator


def _jsonable(event: dict) -> dict:
    # stream_mode="updates" 이벤트는 interrupt() 발생 시 {"__interrupt__": (Interrupt(...),)}
    # 형태로 오는데, Interrupt는 NamedTuple이라 json.dumps에 그대로 넘기면 필드명이 사라지고
    # (value/resumable/ns가 배열 순서로만 남음) 값 자체도 직렬화 불가능한 경우 TypeError가 난다.
    # review_node가 걸리는 매 단계마다 발생하는 경로라 dict로 펼쳐서 보내야 한다.
    interrupts = event.get("__interrupt__")
    if interrupts is None:
        return event
    return {
        "__interrupt__": [
            {"value": i.value, "resumable": i.resumable, "ns": i.ns} for i in interrupts
        ]
    }


async def sse_stream(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for event in events:
        yield f"data: {json.dumps(_jsonable(event), ensure_ascii=False)}\n\n"
