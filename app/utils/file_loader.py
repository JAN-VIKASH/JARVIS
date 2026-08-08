"""
File loader utility to safely read configurations or resources.
"""

import os
import anyio

def load_file_content(file_path: str) -> str:
    """
    Synchronously load content of a text file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        raise RuntimeError(f"Error reading file {file_path}: {str(e)}")


async def load_file_content_async(file_path: str) -> str:
    """
    Asynchronously load content of a text file using anyio.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at: {file_path}")
    try:
        path = anyio.Path(file_path)
        content = await path.read_text(encoding="utf-8")
        return content.strip()
    except Exception as e:
        raise RuntimeError(f"Error asynchronously reading file {file_path}: {str(e)}")
