import httpx

from app.core.config import settings


class SearchClient:
    def __init__(self) -> None:
        self.api_key = settings.SEARCH_API_KEY
        self.base_url = settings.SEARCH_API_BASE_URL

    async def search(self, query: str) -> list[dict]:
        # TODO: 실제 검색 API 응답 포맷에 맞춰 구현
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(
                "/",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"query": query},
            )
            response.raise_for_status()
            return response.json()


search_client = SearchClient()
