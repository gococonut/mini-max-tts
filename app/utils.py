import math
from datetime import timedelta
import httpx
from pydub import AudioSegment
import os
from typing import Optional, Tuple

MAX_CHUNK_LENGTH = 5000 # Example limit

def split_text_into_chunks(text: str, max_length: int = MAX_CHUNK_LENGTH) -> list[str]:
    """将文本分割成块，优先考虑自然断点，支持中英文标点。"""
    chunks = []
    remaining_text = text.strip()

    while len(remaining_text) > max_length:
        split_pos = -1
        # 尝试在段落分隔处分割
        possible_split = remaining_text.rfind('\n\n', 0, max_length)
        if possible_split != -1:
            split_pos = possible_split + 2
        else:
            # 尝试在句子结尾处分割（支持中英文标点）
            for delimiter in ['. ', '! ', '? ', '。', '！', '？', '；', '; ']:
                possible_split = remaining_text.rfind(delimiter, 0, max_length)
                if possible_split != -1:
                    split_pos = max(split_pos, possible_split + len(delimiter))
            if split_pos == -1:
                # 尝试在单换行处分割
                possible_split = remaining_text.rfind('\n', 0, max_length)
                if possible_split != -1:
                    split_pos = max(split_pos, possible_split + 1)
            if split_pos == -1:
                # 尝试在空格处分割
                possible_split = remaining_text.rfind(' ', 0, max_length)
                if possible_split != -1:
                    split_pos = max(split_pos, possible_split + 1)
            if split_pos == -1:
                # 如果没有找到自然断点，强制在最大长度处分割
                split_pos = max_length

        chunks.append(remaining_text[:split_pos].strip())
        remaining_text = remaining_text[split_pos:].strip()

    if remaining_text:  # 添加最后剩余的部分
        chunks.append(remaining_text)

    # 过滤掉可能因分割逻辑产生的空块
    return [chunk for chunk in chunks if chunk]

def format_ms_to_srt_time(milliseconds: int) -> str:
    """Converts milliseconds to SRT time format HH:MM:SS,ms."""
    if milliseconds < 0:
        milliseconds = 0
    td = timedelta(milliseconds=milliseconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    ms = td.microseconds // 1000 # Milliseconds part
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

async def download_audio_file(url: str, temp_path: str) -> bool:
    """从 URL 下载音频文件到临时路径"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Error downloading audio file: {e}")
        return False

def process_audio_segment(
    audio_path: str,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    fade_in_duration: float = 0,
    fade_out_duration: float = 0
) -> Optional[AudioSegment]:
    """处理音频片段，支持裁剪和淡入淡出"""
    try:
        audio = AudioSegment.from_file(audio_path)
        
        # 如果指定了开始和结束时间，进行裁剪
        if start_time is not None:
            start_ms = int(start_time * 1000)
            audio = audio[start_ms:]
        if end_time is not None:
            end_ms = int(end_time * 1000)
            audio = audio[:end_ms]
        
        # 应用淡入淡出效果
        if fade_in_duration > 0:
            audio = audio.fade_in(int(fade_in_duration * 1000))
        if fade_out_duration > 0:
            audio = audio.fade_out(int(fade_out_duration * 1000))
            
        return audio
    except Exception as e:
        print(f"Error processing audio segment: {e}")
        return None

def adjust_srt_timestamps(srt_content: str, offset_ms: int) -> str:
    """调整 SRT 文件的时间戳"""
    lines = srt_content.split('\n')
    adjusted_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            adjusted_lines.append('')
            i += 1
            continue
            
        # 检查是否是时间戳行
        if '-->' in line:
            try:
                start_time, end_time = line.split(' --> ')
                # 转换时间戳为毫秒
                start_ms = timestamp_to_ms(start_time.strip())
                end_ms = timestamp_to_ms(end_time.strip())
                
                # 添加偏移
                new_start = format_ms_to_srt_time(start_ms + offset_ms)
                new_end = format_ms_to_srt_time(end_ms + offset_ms)
                
                adjusted_lines.append(f"{new_start} --> {new_end}")
            except Exception as e:
                print(f"Error adjusting timestamp: {e}")
                adjusted_lines.append(line)
        else:
            adjusted_lines.append(line)
        i += 1
    
    return '\n'.join(adjusted_lines)

def timestamp_to_ms(timestamp: str) -> int:
    """将 SRT 时间戳转换为毫秒"""
    hours, minutes, seconds = timestamp.split(':')
    seconds, milliseconds = seconds.split(',')
    total_ms = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(milliseconds)
    return total_ms

def merge_audio_segments(
    main_audio: AudioSegment,
    overlay_audio: AudioSegment,
    volume_ratio: float = 0.3
) -> AudioSegment:
    """合并两个音频片段，支持音量调节"""
    # 调整第二个音频的音量
    overlay_audio = overlay_audio - (20 * math.log10(1/volume_ratio))
    
    # 确保两个音频长度相同
    if len(main_audio) > len(overlay_audio):
        # 循环 overlay_audio 直到达到所需长度
        times_to_repeat = math.ceil(len(main_audio) / len(overlay_audio))
        overlay_audio = overlay_audio * times_to_repeat
        overlay_audio = overlay_audio[:len(main_audio)]
    else:
        overlay_audio = overlay_audio[:len(main_audio)]
    
    # 合并音频
    return main_audio.overlay(overlay_audio)