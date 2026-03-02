import json
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RedlineAI"
    app_version: str = "0.1.0"
    debug: bool = True

    # File upload
    upload_dir: Path = Path("uploads")
    max_file_size_mb: int = 50
    max_files_per_session: int = 10
    allowed_extensions: set[str] = {".docx"}

    # Document processing
    max_pages_per_file: int = 500

    # AI / LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5-20250929"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if not isinstance(v, str):
            return v
        v = v.strip()
        if not v:
            return ["http://localhost:5173", "http://localhost:3000"]
        # Try JSON array first: ["https://x.vercel.app"]
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        # Fall back to comma-separated: https://x.vercel.app,https://y.vercel.app
        return [origin.strip() for origin in v.split(",") if origin.strip()]


settings = Settings()

# Ensure upload directory exists
settings.upload_dir.mkdir(parents=True, exist_ok=True)
