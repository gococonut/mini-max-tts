from pydantic import BaseModel, Field
from typing import Optional
from .config import settings

class TTSRequest(BaseModel):
    text: Optional[str] = Field(None, min_length=1, description="Text to synthesize")
    file_path: Optional[str] = Field(None, description="Path to the local text file to synthesize")
    enable_subtitles: bool = Field(True, description="Enable SRT subtitle generation")
    output_dir: Optional[str] = Field(None, description="Custom output directory path")
    output_filename: Optional[str] = Field(None, description="Custom output filename (without extension)")
    use_default_intro: bool = Field(False, description="Whether to use default intro audio")
    intro_file_url: Optional[str] = Field(None, description="URL or local path to intro audio file")
    intro_start_time: Optional[float] = Field(None, description="Start time in seconds for intro clip")
    intro_end_time: Optional[float] = Field(None, description="End time in seconds for intro clip")
    intro_fade_duration: float = Field(2.0, description="Fade duration in seconds for intro")
    use_default_outro: bool = Field(False, description="Whether to use default outro audio")
    outro_file_url: Optional[str] = Field(None, description="URL or local path to outro music file")
    outro_fade_duration: float = Field(2.0, description="Fade duration in seconds for outro")
    outro_merge: bool = Field(False, description="Whether to merge outro with main audio instead of appending")
    outro_merge_volume: float = Field(0.3, description="Volume ratio for outro when merging (0.0-1.0)")
    # Add other MiniMax parameters here if needed, e.g.:
    # voice_id: Optional[str] = "male-qn-jingying"
    # speed: Optional[float] = 1.05

class TTSResponse(BaseModel):
    status: str # e.g., "success", "error"
    message: Optional[str] = None
    audio_file: Optional[str] = None # Path to the generated MP3
    srt_file: Optional[str] = None   # Path to the generated SRT, or None