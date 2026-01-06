import logging
import sys
from pathlib import Path
import chardet


def setup_logger():
    logger = logging.getLogger("gigachat_cli")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def read_text_from_file(path: str) -> str:
    file_path = Path(path).resolve()

    if not file_path.exists():
        raise RuntimeError(f"Файл не найден: {file_path}")

    raw = file_path.read_bytes()
    detected = chardet.detect(raw)

    encoding = detected.get("encoding")
    confidence = detected.get("confidence", 0)

    if not encoding or confidence < 0.6:
        raise RuntimeError(
            f"Не удалось уверенно определить кодировку файла {file_path} "
            f"(confidence={confidence})"
        )

    text = raw.decode(encoding)
    print(f"📄 Файл прочитан: {file_path} (encoding={encoding}, confidence={confidence:.2f})")
    return text
