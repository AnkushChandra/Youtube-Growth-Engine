import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / '.env'

load_dotenv(ENV_PATH)

DATA_DIR = ROOT_DIR
MEMORY_FILE = DATA_DIR / 'memory.txt'
if not MEMORY_FILE.exists():
    MEMORY_FILE.write_text('', encoding='utf-8')

class Settings:
    api_prefix: str = '/api'
    port: int = int(os.getenv('PORT', 4000))
    dev_mode: bool = os.getenv('DEV_MODE', 'false').lower() == 'true'
    composio_base_url: str = os.getenv('COMPOSIO_BASE_URL', 'https://backend.composio.dev/api/v3')
    composio_api_key: str | None = os.getenv('COMPOSIO_API_KEY')
    composio_user_id: str = os.getenv('COMPOSIO_USER_ID', 'default')
    gemini_api_key: str | None = os.getenv('GEMINI_API_KEY')
    gemini_model: str = os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview')
    database_url: str = os.getenv('DATABASE_URL', '')
    memory_file: Path = MEMORY_FILE
    max_memory_lines: int = int(os.getenv('MEMORY_MAX_LINES', '20'))
    rate_limit_per_min: int = int(os.getenv('RATE_LIMIT_PER_MIN', '60'))

settings = Settings()
