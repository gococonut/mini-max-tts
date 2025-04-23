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

    # 验证输入参数
    if not request.text and not request.file_path:
        raise HTTPException(status_code=400, detail="Either text or file_path must be provided")

    # 如果提供了文件路径，读取文件内容
    text_to_process = request.text
    if request.file_path:
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {request.file_path}")
        try:
            with open(request.file_path, 'r', encoding='utf-8') as file:
                text_to_process = file.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    # 确定输出路径和文件名
    if request.output_dir:
        output_dir = request.output_dir
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = settings.OUTPUT_DIR

    if request.output_filename:
        output_filename_base = os.path.join(output_dir, request.output_filename)
    else:
        job_id = str(uuid.uuid4())
        output_filename_base = os.path.join(output_dir, job_id)

    output_mp3_path = f"{output_filename_base}.mp3"
    output_srt_path_potential = f"{output_filename_base}.srt"

    # 处理默认 intro/outro
    intro_file_url = request.intro_file_url
    intro_start_time = request.intro_start_time
    intro_end_time = request.intro_end_time
    intro_fade_duration = request.intro_fade_duration
    outro_file_url = request.outro_file_url

    if request.use_default_intro:
        intro_file_url = settings.DEFAULT_INTRO_FILE
        intro_start_time = settings.DEFAULT_INTRO_START_TIME
        intro_end_time = settings.DEFAULT_INTRO_END_TIME
        intro_fade_duration = settings.DEFAULT_INTRO_FADE_DURATION

    if request.use_default_outro:
        outro_file_url = settings.DEFAULT_OUTRO_FILE

    try:
        success, message, final_srt_path = await process_long_text_to_speech(
            text=text_to_process,
            enable_subtitles=request.enable_subtitles,
            output_mp3_path=output_mp3_path,
            output_srt_path_base=output_filename_base,
            intro_file_url=intro_file_url,
            intro_start_time=intro_start_time,
            intro_end_time=intro_end_time,
            intro_fade_duration=intro_fade_duration,
            outro_file_url=outro_file_url,
            outro_fade_duration=request.outro_fade_duration,
            outro_merge=request.outro_merge,
            outro_merge_volume=request.outro_merge_volume
        )

        if success:
            return TTSResponse(
                status="success",
                message="TTS generation complete.",
                audio_file=output_mp3_path,
                srt_file=final_srt_path
            )
        else:
            raise HTTPException(status_code=500, detail=f"TTS generation failed: {message}")

    except Exception as e:
        print(f"Error during TTS generation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)