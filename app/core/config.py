from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PICO"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    CLOVA_API_KEY: str = ""
    CLOVA_MODEL: str = "HCX-005"
    CLOVA_API_BASE_URL: str = "https://clovastudio.stream.ntruss.com"

    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
