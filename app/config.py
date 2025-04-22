import os
from dotenv import load_dotenv

# Load .env file for local development if it exists
load_dotenv()

class Settings:
    MINIMAX_GROUP_ID: str = os.getenv("MINIMAX_GROUP_ID", "")
    MINIMAX_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/app/output") # Default inside container
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()