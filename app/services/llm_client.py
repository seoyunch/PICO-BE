import httpx

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_API_BASE_URL
        self.model = settings.LLM_MODEL

    async def complete(self, prompt: str) -> str:
        # TODO: provider(clova 등)별 요청 포맷에 맞춰 구현
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.post(
                "/",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "prompt": prompt},
            )
            response.raise_for_status()
            return response.text


llm_client = LLMClient()
