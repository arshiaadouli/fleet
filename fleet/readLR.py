import os
from typing import Optional

def get_receipt_no(file_path: str) -> Optional[str]:
    """Extract the word following 'Receipt No' from a file given its full path."""

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read as binary, then decode
    with open(file_path, "rb") as f:
        raw = f.read()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    # Handle both "Receipt No 12345" and "Receipt No: 12345"
    words = text.replace(":", " ").split()

    for i, word in enumerate(words):
        if word == "Receipt" and i + 2 < len(words) and words[i + 1] == "No":
            return words[i + 2][0]+str(int(words[i + 2][6:])+1)

    return None


