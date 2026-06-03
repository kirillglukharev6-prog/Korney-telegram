import telebot
import requests
import os
import io
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
STEOS_TOKEN = os.getenv("STEOS_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

VOICE_ID = 552  # Лунтик
TTS_URL = "https://public.api.voice.steos.io/api/v1/tts/synthesize"

bot = telebot.TeleBot(BOT_TOKEN)


def generate_text(user_question: str) -> str | None:
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_KEY')}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [
                {"role": "system", "content": "Ты Лунтик — добрый, наивный, отвечай коротко и мило. Максимум 3 предложения."},
                {"role": "user", "content": user_question}
            ]
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        data = response.json()
        logger.info(f"OpenRouter ответ: {data}")
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        logger.error(f"Неожиданный ответ: {data}")
        return None
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        return None


def synthesize_voice(text: str) -> bytes | None:
    headers = {
        "Authorization": STEOS_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "voice_id": VOICE_ID,
        "text": text,
        "format": "mp3"
    }
    try:
        response = requests.post(TTS_URL, headers=headers, json=payload, verify=False, timeout=15)
        if response.status_code == 200:
            return response.content
        logger.error(f"TTS ошибка {response.status_code}: {response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"TTS ошибка: {e}")
        return None


@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    bot.reply_to(
        message,
        "Привет! Я бот с голосом Лунтика 🌙\n\n"
        "Напиши /нейро и задай любой вопрос!\n"
        "Пример: /нейро Что такое дружба?"
    )


@bot.message_handler(commands=["нейро"])
def handle_neuro(message):
    user_text = message.text.replace("/нейро", "", 1).strip()

    if not user_text:
        bot.reply_to(message, "Напиши вопрос! Пример: /нейро Как дела?")
        return

    if len(user_text) > 500:
        bot.reply_to(message, "Слишком длинный вопрос! Максимум 500 символов.")
        return

    bot.send_chat_action(message.chat.id, "typing")
    status_msg = bot.reply_to(message, "🤔 Думаю...")

    generated_text = generate_text(user_text)

    if not generated_text:
        bot.edit_message_text("Не смог придумать ответ, попробуй ещё раз!", 
                              message.chat.id, status_msg.message_id)
        return

    bot.edit_message_text("🎙️ Записываю голосовое...", message.chat.id, status_msg.message_id)
    bot.send_chat_action(message.chat.id, "record_voice")

    audio_bytes = synthesize_voice(generated_text)
    bot.delete_message(message.chat.id, status_msg.message_id)

    if audio_bytes:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "voice.mp3"
        bot.send_voice(message.chat.id, audio_file, caption=f"💬 {generated_text[:1024]}")
    else:
        bot.reply_to(message, f"💬 {generated_text}\n\n_(голос недоступен)_", parse_mode="Markdown")


if __name__ == "__main__":
    logger.info("Бот запущен!")
    bot.infinity_polling(none_stop=True, interval=1)
