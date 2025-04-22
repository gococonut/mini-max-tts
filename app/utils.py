import math
from datetime import timedelta

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