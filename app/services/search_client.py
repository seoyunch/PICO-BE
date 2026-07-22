import httpx

from app.core.config import settings


class SearchClient:
    def __init__(self) -> None:
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET

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
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "description": item.get("description", ""),
                }
                for item in items
            ]


search_client = SearchClient()
