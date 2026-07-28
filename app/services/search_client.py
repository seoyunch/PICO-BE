import html
import re

import httpx

from app.core.config import settings
from app.utils.perf import timed

_TAG_PATTERN = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """네이버 webkr API는 검색어 매칭 부분을 <b>...</b>로 감싸고 HTML 엔티티를
    이스케이프해서 내려준다(예: '<b>반려견</b>도 ... &amp; ...'). 이 원문 그대로
    LLM 프롬프트/인용에 흘러들어가면 <b> 태그와 '&amp;' 같은 엔티티가 최종 답변에
    그대로 노출되므로, 검색 결과를 쓰는 시점(여기)에서 한 번만 정제한다."""
    return html.unescape(_TAG_PATTERN.sub("", text)).strip()


class SearchClient:
    def __init__(self) -> None:
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET

    @timed("naver_search")
    async def search(self, query: str, *, display: int = 10) -> list[dict]:
        async with httpx.AsyncClient(
            base_url="https://naverapihub.apigw.ntruss.com", timeout=30.0
        ) as client:
            response = await client.get(
                "/search/v1/webkr",
                headers={
                    "X-NCP-APIGW-API-KEY-ID": self.client_id,
                    "X-NCP-APIGW-API-KEY": self.client_secret,
                },
                params={"query": query, "display": display},
            )
            response.raise_for_status()
            items = response.json().get("items", [])
            return [
                {
                    "title": _clean(item.get("title", "")),
                    "link": item.get("link", ""),
                    "description": _clean(item.get("description", "")),
                }
                for item in items
            ]


search_client = SearchClient()
