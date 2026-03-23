"""Pipeline configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """VecSmith pipeline configuration.

    All settings can be overridden via environment variables
    prefixed with VECSMITH_ (e.g., VECSMITH_LLM_BASE_URL).
    """

    # LLM (prompt enhancement)
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "default"
    llm_api_key: str = ""
    llm_max_tokens: int = 300
    llm_temperature: float = 0.7

    # Flux server (image generation)
    flux_base_url: str = "http://localhost:8081"
    flux_width: int = 1024
    flux_height: int = 1024
    flux_steps: int = 4

    # vtracer (vectorization)
    vtracer_filter_speckle: int = 4
    vtracer_color_precision: int = 6

    # SVG optimization
    svg_coordinate_precision: int = 2

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    model_config = {"env_prefix": "VECSMITH_"}


def get_settings() -> Settings:
    return Settings()
