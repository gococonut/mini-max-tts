import os
from dotenv import load_dotenv

# Load .env file for local development if it exists
load_dotenv()

class Settings:
    MINIMAX_GROUP_ID: str = os.getenv("MINIMAX_GROUP_ID", "")
    MINIMAX_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/app/output") # Default inside container
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    # 默认音频文件路径
    DEFAULT_INTRO_FILE: str = os.path.join(os.path.dirname(__file__), "assets", "intro.mp3")
    DEFAULT_OUTRO_FILE: str = os.path.join(os.path.dirname(__file__), "assets", "outro.mp3")
    # 默认音频参数
    DEFAULT_INTRO_START_TIME: float = 0.0
    DEFAULT_INTRO_END_TIME: float = 17.5
    DEFAULT_INTRO_FADE_DURATION: float = 3.5

settings = Settings()