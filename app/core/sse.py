import json
from collections.abc import AsyncIterator


async def sse_stream(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for event in events:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
