from pathlib import Path
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
    llm_model: str = "claude-haiku-4-5-20251001"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    # Stored as a plain comma-separated string so pydantic-settings never
    # tries to JSON-parse it. Parsed into a list by main.py.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Ensure upload directory exists
settings.upload_dir.mkdir(parents=True, exist_ok=True)
