from gigachat import generate_summary_async

# Лимит символов для GigaChat (безопасное значение для Lite-модели)
MAX_CHARS = 10000


async def summarize_messages(messages: list[str]) -> str:
    if not messages:
        return "Нет сообщений для суммаризации."

    # Если сообщений очень много, делим их на группы
    chunks = []
    current_chunk = []
    current_length = 0

    for msg in messages:
        if current_length + len(msg) > MAX_CHARS:
            chunks.append("\n".join(current_chunk))
            current_chunk = [msg]
            current_length = len(msg)
        else:
            current_chunk.append(msg)
            current_length += len(msg)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    # Суммаризируем каждый чанк
    summaries = []
    for i, chunk_text in enumerate(chunks):
        prompt = (
            "Ты — аналитический помощник. Твоя задача — составить краткую сводку переписки.\n"
            f"ЧАСТЬ {i + 1} ИЗ {len(chunks)}:\n\n"
            "ПРАВИЛА:\n"
            "1. Только ключевые факты и решения.\n"
            "2. Нейтральный тон, без имен и приветствий.\n"
            "3. Не более 3 предложений для этой части.\n\n"
            f"ТЕКСТ:\n{chunk_text}"
        )
        res = await generate_summary_async(prompt)
        summaries.append(res)

    # Если чанк был один — возвращаем его. Если много — делаем финальный проход.
    final_text = "\n".join(summaries)
    if len(chunks) == 1:
        return final_text

    final_prompt = (
        "Ты — главный аналитик. Перед тобой несколько кратких сводок одного канала.\n"
        "Объедини их в один связный финальный дайджест.\n"
        "ПРАВИЛА:\n"
        "- Строго не более 5 предложений.\n"
        "- Исключи повторы.\n"
        f"ВВОДНЫЕ ДАННЫЕ:\n{final_text}"
    )
    return await generate_summary_async(final_prompt)
