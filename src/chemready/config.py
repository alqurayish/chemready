"""Typed settings, read from environment variables or a local .env file.

Every setting has the prefix CHEMREADY_, for example CHEMREADY_LLM_PROVIDER.
Secrets use SecretStr, so they are hidden when printed or logged.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# "rules" is an offline baseline with no AI: for demos and as an eval baseline only.
LlmProvider = Literal["ollama", "gemini", "rules"]


class Settings(BaseSettings):
    """All configuration for ChemReady in one validated object."""

    model_config = SettingsConfigDict(
        env_prefix="CHEMREADY_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # an empty line like CHEMREADY_GEMINI_MODEL= counts as "not set"
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"

    # Model layer. Ollama is the default because it keeps files on our own machine.
    llm_provider: LlmProvider = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    # Google's free tier may use submitted content to improve its products.
    # Leave this True unless the project pays for Gemini.
    gemini_free_tier: bool = True

    # Storage. Everything under data/private/ is git-ignored.
    data_dir: Path = Path("data")
    database_path: Path = Path("data/private/chemready.sqlite")

    upload_dir: Path = Path("data/private/uploads")
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_batch_files: int = Field(default=50, ge=1, le=200)

    # Business rule R6: default for new facilities: flag SDS files older than this many years.
    sds_max_age_years: int = Field(default=3, ge=1, le=10)

    # Signs session cookies. Required in production; in development a random key is
    # made at start-up, so everyone is signed out when the server restarts.
    secret_key: SecretStr | None = None

    @model_validator(mode="after")
    def _check_provider_settings(self) -> "Settings":
        """Fail at start-up, not halfway through a batch, if a provider is half configured."""
        if self.llm_provider == "gemini":
            missing = [
                name
                for name, value in (
                    ("CHEMREADY_GEMINI_API_KEY", self.gemini_api_key),
                    ("CHEMREADY_GEMINI_MODEL", self.gemini_model),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"llm_provider is 'gemini' but these are not set: {', '.join(missing)}")
        if self.environment == "production" and (
            self.secret_key is None or len(self.secret_key.get_secret_value()) < 32
        ):
            raise ValueError("CHEMREADY_SECRET_KEY must be set to at least 32 characters in production")
        return self

    @property
    def allows_private_data(self) -> bool:
        """True only if the chosen provider may receive private factory files.

        Hard rule: private factory data is never sent to a free AI tier.
        """
        if self.llm_provider == "gemini":
            return not self.gemini_free_tier
        return True


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them everywhere."""
    return Settings()
