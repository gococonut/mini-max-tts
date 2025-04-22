from fastapi import FastAPI, HTTPException, BackgroundTasks
from .models import TTSRequest, TTSResponse
from .tts_processor import process_long_text_to_speech
from .config import settings
import os
import uuid

app = FastAPI()

@app.post("/generate_tts", response_model=TTSResponse)
async def generate_tts_endpoint(request: TTSRequest, background_tasks: BackgroundTasks):
    if not settings.MINIMAX_API_KEY or not settings.MINIMAX_GROUP_ID:
        raise HTTPException(status_code=500, detail="API key or Group ID not configured")

    job_id = str(uuid.uuid4())
    output_filename_base = os.path.join(settings.OUTPUT_DIR, job_id)
    output_mp3_path = f"{output_filename_base}.mp3"
    output_srt_path_potential = f"{output_filename_base}.srt" # Potential path

    try:
        # Consider running the potentially long process in the background
        # or handle timeouts carefully if running synchronously.
        # For simplicity here, running async inline:
        success, message, final_srt_path = await process_long_text_to_speech(
            text=request.text,
            enable_subtitles=request.enable_subtitles,
            output_mp3_path=output_mp3_path,
            output_srt_path_base=output_filename_base, # Pass base name
            # Pass other optional params like voice_id, speed if needed
        )

        if success:
            return TTSResponse(
                status="success",
                message="TTS generation complete.",
                audio_file=output_mp3_path, # Return path relative to container/host
                srt_file=final_srt_path     # This will be the actual path or None
            )
        else:
            raise HTTPException(status_code=500, detail=f"TTS generation failed: {message}")

    except Exception as e:
        # Log the exception details properly
        print(f"Error during TTS generation: {e}") # Replace with proper logging
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Add lifespan event to create output dir on startup if needed
@app.on_event("startup")
async def startup_event():
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)