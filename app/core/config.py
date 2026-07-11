from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PICO"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    LLM_PROVIDER: str = "clova"
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = ""
    LLM_MODEL: str = ""

    SEARCH_API_KEY: str = ""
    SEARCH_API_BASE_URL: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
