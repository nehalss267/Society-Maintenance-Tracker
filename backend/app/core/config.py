from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OVERDUE_THRESHOLD_DAYS: int = 3

    # Async jobs: celery (broker=Redis) | inline (no broker needed)
    JOB_EXECUTION_MODE: str = "inline"
    REDIS_URL: str = "redis://localhost:6379/0"

    # File storage: local | cloudinary
    STORAGE_BACKEND: str = "local"
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    UPLOAD_MAX_BYTES: int = 5 * 1024 * 1024

    # Payments (Razorpay) - blank = simulated payment flow
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Email (Resend) - blank key = log-only delivery
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Society Maintenance Tracker <onboarding@resend.dev>"

    # Scheduler endpoints - requests must present X-Cron-Secret
    CRON_SECRET: str = ""

    # CORS - comma-separated origins allowed to call the API from a browser
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Base URL of the frontend - used to build password-reset links
    FRONTEND_URL: str = "http://localhost:5173"

    # Public base URL of this API - prefixes stored-file paths (/uploads/*)
    # so separately hosted frontends can load them. Empty = relative paths.
    PUBLIC_API_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()