import httpx
import asyncio
import os
import uuid
import json
from pydub import AudioSegment
from .config import settings
from .utils import (
    split_text_into_chunks,
    format_ms_to_srt_time,
    download_audio_file,
    process_audio_segment,
    adjust_srt_timestamps,
    merge_audio_segments
)

# Placeholder - replace with actual MiniMax hex/base64 decoding
def decode_audio_data(audio_hex_or_base64):
    # Example if it were hex:
    try:
        return bytes.fromhex(audio_hex_or_base64)
    except ValueError as e:
        print(f"Error decoding hex: {e}")
        # Add Base64 handling if needed
        raise ValueError("Invalid audio data format from API") from e


async def fetch_subtitle_data(url: str, client: httpx.AsyncClient):
    try:
        response = await client.get(url, timeout=30.0) # Add timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        # MiniMax subtitle format is JSON, precise to sentence (<=50 chars), unit ms.
        # Example structure assumed: [{"time_begin": 100, "time_end": 1500, "text": "Sentence 1."}, ...]
        return response.json()
    except httpx.RequestError as e:
        print(f"Error fetching subtitle URL {url}: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding subtitle JSON from {url}: {e}")
    except Exception as e:
        print(f"Unexpected error fetching subtitles from {url}: {e}")
    return None # Return None on failure

async def process_chunk(client: httpx.AsyncClient, chunk_text: str, enable_subtitles: bool, temp_dir: str):
    """Processes a single text chunk using the MiniMax API."""
    payload = {
        "model": "speech-01-turbo", # Or configurable
        "text": chunk_text,
        "timber_weights": [{"voice_id": "male-qn-jingying", "weight": 1}], # Or configurable
        "voice_setting": {"speed": 1.05, "pitch": 0, "vol": 1, "voice_id": "male-qn-jingying" }, # Or configurable
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
        "subtitle_enable": enable_subtitles
    }
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={settings.MINIMAX_GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {settings.MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    temp_audio_path = os.path.join(temp_dir, f"chunk_{uuid.uuid4()}.mp3")
    subtitle_data = None
    audio_duration_ms = 0

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=60.0) # Add timeout
        response.raise_for_status()
        result = response.json()

        if result.get("base_resp", {}).get("status_code") == 0 and result.get("data", {}).get("status") == 2:
            audio_hex = result.get("data", {}).get("audio")
            if not audio_hex:
                 raise ValueError("No audio data found in successful API response.")

            audio_bytes = decode_audio_data(audio_hex)
            with open(temp_audio_path, "wb") as f:
                f.write(audio_bytes)

            extra_info = result.get("extra_info", {})
            audio_duration_ms = extra_info.get("audio_length", 0)

            if enable_subtitles:
                subtitle_url = result.get("data", {}).get("subtitle_file") # Correct field name from docs
                if subtitle_url:
                    # Use the same client to fetch subtitle data
                    subtitle_data = await fetch_subtitle_data(subtitle_url, client)
                else:
                    print(f"Warning: Subtitles enabled, but no subtitle_file URL provided for chunk.")

            return {"success": True, "audio_path": temp_audio_path, "subtitles": subtitle_data, "duration_ms": audio_duration_ms}
        else:
            status_code = result.get("base_resp", {}).get("status_code")
            status_msg = result.get("base_resp", {}).get("status_msg", "Unknown API error")
            print(f"MiniMax API Error: Code={status_code}, Msg={status_msg}")
            return {"success": False, "error": f"API Error: {status_msg} (Code: {status_code})"}

    except httpx.RequestError as e:
        print(f"HTTP Request Error processing chunk: {e}")
        return {"success": False, "error": f"HTTP Request Error: {e}"}
    except httpx.HTTPStatusError as e:
         print(f"HTTP Status Error processing chunk: {e.response.status_code} - {e.response.text}")
         return {"success": False, "error": f"HTTP Status Error: {e.response.status_code}"}
    except Exception as e:
        print(f"Unexpected error processing chunk: {e}")
        return {"success": False, "error": f"Unexpected Error: {str(e)}"}
    # finally:
        # Ensure temp file is removed if it exists but processing failed before returning success
        # if not 'success' in locals() or not success:
        #      if os.path.exists(temp_audio_path):
        #          os.remove(temp_audio_path)


async def process_long_text_to_speech(
    text: str,
    enable_subtitles: bool,
    output_mp3_path: str,
    output_srt_path_base: str,
    intro_file_url: str = None,
    intro_start_time: float = None,
    intro_end_time: float = None,
    intro_fade_duration: float = 2.0,
    outro_file_url: str = None,
    outro_fade_duration: float = 2.0,
    outro_merge: bool = False,
    outro_merge_volume: float = 0.3,
    **kwargs
):
    """处理长文本到语音转换，支持添加片头和片尾音乐。"""
    temp_dir = os.path.join(settings.OUTPUT_DIR, f"temp_{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)

    # 处理 intro 音频
    intro_audio = None
    intro_duration_ms = 0
    intro_overlap_duration_ms = 0  # 重叠部分的持续时间
    if intro_file_url:
        intro_temp_path = os.path.join(temp_dir, "intro_temp.mp3")
        if intro_file_url.startswith(("http://", "https://")):
            if not await download_audio_file(intro_file_url, intro_temp_path):
                print("Failed to download intro audio file")
        else:
            # 如果是本地文件路径
            if os.path.exists(intro_file_url):
                intro_temp_path = intro_file_url
            else:
                print(f"Intro file not found: {intro_file_url}")
                intro_file_url = None

        if intro_file_url:
            intro_audio = process_audio_segment(
                intro_temp_path,
                start_time=intro_start_time,
                end_time=intro_end_time,
                fade_in_duration=intro_fade_duration,
                fade_out_duration=intro_fade_duration
            )
            if intro_audio:
                intro_duration_ms = len(intro_audio)
                intro_overlap_duration_ms = int(intro_fade_duration * 1000)  # 转换为毫秒

    # 处理主要 TTS 内容
    chunks = split_text_into_chunks(text)
    tasks = []
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            tasks.append(process_chunk(client, chunk, enable_subtitles, temp_dir))

        results = await asyncio.gather(*tasks)

    successful_results = [r for r in results if r and r.get("success")]
    errors = [r.get("error") for r in results if r and not r.get("success")]

    if not successful_results or len(successful_results) != len(chunks):
        # Cleanup
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        return False, f"Failed to process all chunks. Errors: {'; '.join(errors)}", None

    # 处理 outro 音频
    outro_audio = None
    if outro_file_url:
        outro_temp_path = os.path.join(temp_dir, "outro_temp.mp3")
        if outro_file_url.startswith(("http://", "https://")):
            if not await download_audio_file(outro_file_url, outro_temp_path):
                print("Failed to download outro audio file")
        else:
            # 如果是本地文件路径
            if os.path.exists(outro_file_url):
                outro_temp_path = outro_file_url
            else:
                print(f"Outro file not found: {outro_file_url}")
                outro_file_url = None

        if outro_file_url:
            outro_audio = process_audio_segment(
                outro_temp_path,
                fade_in_duration=outro_fade_duration,
                fade_out_duration=outro_fade_duration
            )

    # 合并音频
    combined_audio = AudioSegment.empty()
    temp_audio_files = []

    try:
        # 添加主要内容（先处理第一个片段）
        first_segment = None
        remaining_segments = []
        
        for i, result in enumerate(successful_results):
            chunk_audio_path = result["audio_path"]
            temp_audio_files.append(chunk_audio_path)
            segment = AudioSegment.from_mp3(chunk_audio_path)
            if i == 0:
                first_segment = segment
            else:
                remaining_segments.append(segment)

        # 处理 intro 和第一个 TTS 片段的重叠
        if intro_audio and first_segment:
            # 计算非重叠部分的长度
            non_overlap_intro_duration = intro_duration_ms - intro_overlap_duration_ms
            
            # 将 intro 分成两部分：主体部分和淡出部分
            intro_main = intro_audio[:-intro_overlap_duration_ms]
            intro_fade = intro_audio[-intro_overlap_duration_ms:].fade_out(intro_overlap_duration_ms)
            
            # 将第一个 TTS 片段分成两部分：重叠部分和主体部分
            first_overlap = first_segment[:intro_overlap_duration_ms]
            first_main = first_segment[intro_overlap_duration_ms:]
            
            # 合并重叠部分
            overlap_segment = intro_fade.overlay(first_overlap)
            
            # 组合所有部分
            combined_audio = intro_main + overlap_segment + first_main
        else:
            # 如果没有 intro，直接添加第一个片段
            if first_segment:
                combined_audio = first_segment
        
        # 添加剩余的 TTS 片段
        for segment in remaining_segments:
            combined_audio += segment

        # 处理 outro
        if outro_audio:
            if outro_merge:
                # 获取 outro 的长度
                outro_length = len(outro_audio)
                # 添加 2 秒静音延迟
                delay_ms = 2000
                delayed_outro = AudioSegment.silent(duration=delay_ms) + outro_audio
                # 获取主音频的最后部分（与 outro 等长）
                main_end = combined_audio[-(outro_length + delay_ms):]
                # 将 outro 与主音频的最后部分合并
                merged_end = merge_audio_segments(
                    main_end,
                    delayed_outro,
                    volume_ratio=outro_merge_volume
                )
                # 替换原音频的最后部分
                combined_audio = combined_audio[:-(outro_length + delay_ms)] + merged_end
            else:
                combined_audio +=  outro_audio

        # 导出最终音频
        combined_audio.export(output_mp3_path, format="mp3", bitrate="128k")
    except Exception as e:
        print(f"Error merging audio: {e}")
        # Cleanup
        for f in temp_audio_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return False, f"Error during audio merging: {e}", None

    # 处理字幕
    final_srt_path = None
    if enable_subtitles:
        srt_content = ""
        srt_index = 1
        # 调整字幕偏移时间，考虑重叠部分
        current_offset_ms = intro_duration_ms - intro_overlap_duration_ms if intro_audio else 0
        all_subs_present = True

        for i, result in enumerate(successful_results):
            chunk_subtitles = result.get("subtitles")
            chunk_duration_ms = result.get("duration_ms", 0)

            if chunk_subtitles is None and len(chunks[i].strip()) > 0:
                print(f"Warning: Missing subtitle data for chunk {i+1}")
                all_subs_present = False
                continue

            if chunk_subtitles:
                for sub_item in chunk_subtitles:
                    time_begin = sub_item.get("time_begin")
                    time_end = sub_item.get("time_end")
                    sub_text = sub_item.get("text")

                    if time_begin is not None and time_end is not None and sub_text:
                        # 为第一个片段特殊处理时间戳
                        if i == 0:
                            # 如果是第一个片段，考虑重叠时间
                            adj_time_begin = time_begin
                            adj_time_end = time_end
                            if intro_audio:
                                # 只对重叠范围内的字幕进行特殊处理
                                if time_begin < intro_overlap_duration_ms:
                                    adj_time_begin = time_begin + (intro_duration_ms - intro_overlap_duration_ms)
                                if time_end < intro_overlap_duration_ms:
                                    adj_time_end = time_end + (intro_duration_ms - intro_overlap_duration_ms)
                        else:
                            # 非第一个片段使用正常偏移
                            adj_time_begin = time_begin + current_offset_ms
                            adj_time_end = time_end + current_offset_ms

                        start_ts = format_ms_to_srt_time(adj_time_begin)
                        end_ts = format_ms_to_srt_time(adj_time_end)

                        srt_content += f"{srt_index}\n"
                        srt_content += f"{start_ts} --> {end_ts}\n"
                        srt_content += f"{sub_text}\n\n"
                        srt_index += 1
                    else:
                        print(f"Warning: Invalid subtitle item format in chunk {i+1}")

            current_offset_ms += chunk_duration_ms

        if srt_content:
            final_srt_path = f"{output_srt_path_base}.srt"
            try:
                with open(final_srt_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                if not all_subs_present:
                    print(f"Warning: SRT file might be incomplete")
            except IOError as e:
                print(f"Error writing SRT file: {e}")
                final_srt_path = None
        else:
            print("No subtitle content generated.")

    # Cleanup
    try:
        for f in temp_audio_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)
        elif os.path.exists(temp_dir):
            print(f"Warning: Temporary directory not empty after processing")
    except OSError as e:
        print(f"Error during cleanup: {e}")

    return True, "Processing successful.", final_srt_path