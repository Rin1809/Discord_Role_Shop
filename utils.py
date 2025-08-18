def format_text(text: str) -> str:
    """
    Thay thế chuỗi ký tự '\\n' thành ký tự xuống dòng '\n'.
    Điều này cần thiết vì PostgreSQL có thể escape ký tự '\' trong JSON.
    """
    if isinstance(text, str):
        return text.replace('\\n', '\n')
    return text