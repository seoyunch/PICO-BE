from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PICO"
    API_STR: str = "/api"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    CLOVA_API_KEY: str = ""
    CLOVA_MODEL: str = "HCX-005"
    CLOVA_API_BASE_URL: str = "https://clovastudio.stream.ntruss.com"

    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    DATABASE_URL: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    REDIS_URL: str = "redis://localhost:6379/0"

    COOKIE_SECURE: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
