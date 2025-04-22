from pydantic import BaseModel, Field
from typing import Optional

class TTSRequest(BaseModel):
    text: Optional[str] = Field(None, min_length=1, description="Text to synthesize")
    file_path: Optional[str] = Field(None, description="Path to the local text file to synthesize")
    enable_subtitles: bool = Field(True, description="Enable SRT subtitle generation")
    output_dir: Optional[str] = Field(None, description="Custom output directory path")
    output_filename: Optional[str] = Field(None, description="Custom output filename (without extension)")
    # Add other MiniMax parameters here if needed, e.g.:
    # voice_id: Optional[str] = "male-qn-jingying"
    # speed: Optional[float] = 1.05

class TTSResponse(BaseModel):
    status: str # e.g., "success", "error"
    message: Optional[str] = None
    audio_file: Optional[str] = None # Path to the generated MP3
    srt_file: Optional[str] = None   # Path to the generated SRT, or None