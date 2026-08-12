from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str

    model_vision: str = "gemini-2.0-flash"
    model_image: str = "gemini-2.0-flash-preview-image-generation"
    model_image_draft: str = "gemini-2.0-flash-preview-image-generation"
    model_embed: str = "text-embedding-004"
    embed_dim: int = 768

    database_url: str = "postgresql+psycopg://dressing:dressing@localhost:5433/dressing"
    max_renders_par_jour: int = 40

    @property
    def dir_wardrobe(self) -> Path:
        return DATA / "wardrobe"

    @property
    def dir_cutouts(self) -> Path:
        return DATA / "cutouts"

    @property
    def dir_renders(self) -> Path:
        return DATA / "renders"


settings = Settings()