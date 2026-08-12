from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./vocalvitals.db"  # override with Render Postgres URL

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    # CORS – set to your Vercel domain in production
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8080", "http://localhost:3000"]

    # Admin
    ADMIN_EMAIL: str = "admin@vocalvitals.dev"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
