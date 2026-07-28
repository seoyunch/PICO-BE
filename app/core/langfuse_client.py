from langfuse import Langfuse

from app.core.config import settings

langfuse_client = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    base_url=settings.LANGFUSE_BASE_URL,
)
