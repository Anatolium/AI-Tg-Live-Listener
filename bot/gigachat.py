import os
import uuid
import aiohttp
import logging
from pathlib import Path
from dotenv import load_dotenv

# Определяем корень проекта относительно этого файла (поднимаемся на уровень выше)
root_dir = Path(__file__).resolve().parent.parent

load_dotenv(root_dir / ".env")

logger = logging.getLogger("gigachat")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


class GigaChatError(Exception):
    pass


async def get_access_token_async() -> str:
    """Асинхронное получение токена доступа."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise GigaChatError("CLIENT_ID или CLIENT_SECRET не заданы")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {CLIENT_SECRET}",
    }
    payload = {"scope": "GIGACHAT_API_PERS"}

    # verify_ssl=False заменяет verify=False из requests
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                    OAUTH_URL,
                    headers=headers,
                    data=payload,
                    ssl=False
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data["access_token"]
        except Exception as e:
            logger.error(f"Ошибка получения токена: {e}")
            raise GigaChatError(f"Не удалось получить токен: {e}")


async def generate_summary_async(text: str) -> str:
    """Асинхронная генерация саммари."""
    try:
        token = await get_access_token_async()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "Сделай краткую структурированную сводку."},
                {"role": "user", "content": text},
            ],
            "temperature": 0.7
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    CHAT_URL,
                    json=payload,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Ошибка GigaChat: {e}")
        return f"Ошибка при генерации сводки: {str(e)}"
