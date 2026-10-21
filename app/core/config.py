from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./comercio_exterior.db"
    jwt_secret: SecretStr = Field(min_length=32)
    dashboard_cache_ttl_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    access_token_expire_minutes: int = Field(default=30, gt=0)

    @field_validator("jwt_secret")
    @classmethod
    def reject_example_secret(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value() == "replace-with-a-random-secret-at-least-32-characters":
            raise ValueError("Genera un JWT_SECRET propio antes de arrancar la API")
        return value
