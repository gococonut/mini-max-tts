import httpx
import asyncio
import os
import uuid
import json
from pydub import AudioSegment
from .config import settings
from .utils import split_text_into_chunks, format_ms_to_srt_time # Assuming these helpers exist

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


async def process_long_text_to_speech(text: str, enable_subtitles: bool, output_mp3_path: str, output_srt_path_base: str, **kwargs):
    """Splits text, calls API for chunks, merges audio, generates SRT."""
    chunks = split_text_into_chunks(text) # Max length handled in util
    temp_dir = os.path.join(settings.OUTPUT_DIR, f"temp_{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)

    tasks = []
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            tasks.append(process_chunk(client, chunk, enable_subtitles, temp_dir))

        results = await asyncio.gather(*tasks)

    successful_results = [r for r in results if r and r.get("success")]
    errors = [r.get("error") for r in results if r and not r.get("success")]

    if not successful_results or len(successful_results) != len(chunks):
        # Cleanup partial temp files if main process failed
        for res in successful_results:
             if os.path.exists(res["audio_path"]):
                 os.remove(res["audio_path"])
        if os.path.exists(temp_dir):
             os.rmdir(temp_dir) # Remove temp dir only if empty
        return False, f"Failed to process all chunks. Errors: {'; '.join(errors)}", None

    # --- Audio Merging ---
    combined_audio = AudioSegment.empty()
    temp_audio_files = []
    try:
        for result in successful_results: # Assuming results are in order
            chunk_audio_path = result["audio_path"]
            temp_audio_files.append(chunk_audio_path)
            segment = AudioSegment.from_mp3(chunk_audio_path)
            combined_audio += segment
        combined_audio.export(output_mp3_path, format="mp3", bitrate="128k") # Use API's bitrate
    except Exception as e:
        print(f"Error merging audio: {e}")
         # Cleanup
        for f in temp_audio_files: os.remove(f)
        if os.path.exists(temp_dir): os.rmdir(temp_dir) # Remove temp dir only if empty
        return False, f"Error during audio merging: {e}", None

    # --- SRT Generation ---
    final_srt_path = None
    if enable_subtitles:
        srt_content = ""
        srt_index = 1
        current_offset_ms = 0
        all_subs_present = True

        for i, result in enumerate(successful_results):
            chunk_subtitles = result.get("subtitles")
            chunk_duration_ms = result.get("duration_ms", 0) # Get duration for offset

            if chunk_subtitles is None and len(chunks[i].strip()) > 0: # Check if chunk wasn't just whitespace
                 print(f"Warning: Missing subtitle data for chunk {i+1}. SRT file may be incomplete.")
                 all_subs_present = False # Mark potentially incomplete
                 # Decide if you want to continue or fail SRT generation
                 # continue # Option 1: Skip this chunk's subtitles
                 # break # Option 2: Stop SRT generation if any part missing

            if chunk_subtitles:
                for sub_item in chunk_subtitles:
                     time_begin = sub_item.get("time_begin")
                     time_end = sub_item.get("time_end")
                     sub_text = sub_item.get("text")

                     if time_begin is not None and time_end is not None and sub_text:
                         adj_time_begin = time_begin + current_offset_ms
                         adj_time_end = time_end + current_offset_ms
                         start_ts = format_ms_to_srt_time(adj_time_begin)
                         end_ts = format_ms_to_srt_time(adj_time_end)

                         srt_content += f"{srt_index}\n"
                         srt_content += f"{start_ts} --> {end_ts}\n"
                         srt_content += f"{sub_text}\n\n"
                         srt_index += 1
                     else:
                        print(f"Warning: Invalid subtitle item format in chunk {i+1}: {sub_item}")

            # Add duration of the *current* chunk to the offset for the *next* chunk
            current_offset_ms += chunk_duration_ms

        if srt_content: # Only write if we generated something
             final_srt_path = f"{output_srt_path_base}.srt"
             try:
                 with open(final_srt_path, "w", encoding="utf-8") as f:
                     f.write(srt_content)
                 if not all_subs_present:
                     print(f"Warning: SRT file generated at {final_srt_path}, but might be incomplete due to missing chunk data.")
             except IOError as e:
                 print(f"Error writing SRT file: {e}")
                 final_srt_path = None # Failed to write
        else:
             print("No subtitle content generated.")


    # --- Cleanup ---
    try:
         for f in temp_audio_files:
             if os.path.exists(f):
                 os.remove(f)
         # Remove the temporary directory if it's empty
         if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)
         elif os.path.exists(temp_dir): # If not empty, something else might be there? Log warning.
             print(f"Warning: Temporary directory {temp_dir} not empty after processing.")

    except OSError as e:
        print(f"Error during cleanup: {e}")


    return True, "Processing successful.", final_srt_path