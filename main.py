import asyncio
import storage
from storage import bot_token, chat_id, message_id, ya_token
from telegram import Bot
from telegram.error import BadRequest, RetryAfter
from api_yandex import get_current_track

bot = Bot(token=bot_token)
BACKOFF_SCHEDULE = [30, 30, 300, 900, 1800, 3600]
current_backoff_index = 0
track_change_multiplier = 1
last_track_id = None


async def edit_message():
    global track_change_multiplier, last_track_id

    track_info = await get_current_track(ya_token)
    if not track_info:
        print("Не удалось получить информацию о треке")
        return False, None

    current_track_id = track_info.get('id')
    duration_sec = track_info['duration'] // 1000

    if current_track_id == last_track_id:
        track_change_multiplier = min(track_change_multiplier + 1, 6)
        print(f"Трек не изменился, множитель увеличен до {track_change_multiplier}")
    else:
        track_change_multiplier = 1
        last_track_id = current_track_id
        print("Обнаружен новый трек, множитель сброшен")

    new_text = (
        f"🎵 Сейчас играет: {track_info['title']} 🎵\n"
        f"🎤 Исполнители: {', '.join(track_info['artists'])}\n"
        f"🔗 Ссылка: {track_info['url']}\n"
    )

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text
        )
        print("Сообщение успешно обновлено")
        return True, duration_sec

    except BadRequest as e:
        if "Message is not modified" in str(e):
            print("Трек не изменился, пропускаем обновление")
            return False, duration_sec
        elif "Message to edit not found" in str(e):
            print("Сообщение не найдено, отправляем новое")
            message = await bot.send_message(chat_id=chat_id, text=new_text)
            storage.message_id = message.message_id
            return True, duration_sec
        else:
            print(f"Ошибка Telegram: {e}")
            return False, duration_sec

    except RetryAfter as e:
        wait_time = e.retry_after
        print(f"Ожидаем {wait_time} секунд из-за ограничений Telegram")
        await asyncio.sleep(wait_time)
        return await edit_message()


async def main():
    global current_backoff_index, track_change_multiplier
    print("Запуск бота...")

    try:
        while True:
            updated, duration = await edit_message()

            if duration:
                wait_time = (duration + 2) * track_change_multiplier
                print(f"Ожидаем {wait_time} секунд (множитель: {track_change_multiplier})")
            else:
                wait_time = BACKOFF_SCHEDULE[current_backoff_index]
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="УПС ничего не играет"
                )
                current_backoff_index = (current_backoff_index + 1) % len(BACKOFF_SCHEDULE)
                print(f"Используем резервную задержку: {wait_time} сек (уровень {current_backoff_index})")

            await asyncio.sleep(wait_time)

    except asyncio.CancelledError:
        print("Завершение работы...")
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Работа остановлена пользователем")