from pydantic import BaseModel, Field
from typing import Optional

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize")
    enable_subtitles: bool = Field(True, description="Enable SRT subtitle generation")
    # Add other MiniMax parameters here if needed, e.g.:
    # voice_id: Optional[str] = "male-qn-jingying"
    # speed: Optional[float] = 1.05

class TTSResponse(BaseModel):
    status: str # e.g., "success", "error"
    message: Optional[str] = None
    audio_file: Optional[str] = None # Path to the generated MP3
    srt_file: Optional[str] = None   # Path to the generated SRT, or None