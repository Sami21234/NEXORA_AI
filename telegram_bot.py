"""
Telegram front-end for the Dynamic AI Chatbot.

Reuses 100% of the NLP/Gemini/logging logic in chat_engine.py -- this file
only adapts that shared logic to Telegram's async, long-polling model.
See the module docstring discussion in the chat history / README for why
that adaptation is non-trivial (sync chat_engine + async PTB event loop,
session_id mapping, and the CommonMark-vs-Telegram-Markdown mismatch).

Run (separate process from server.py, own terminal, same venv):
    source venv/bin/activate
    python telegram_bot.py
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import chat_engine

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


def strip_markdown(text: str) -> str:
    """
    Removes common CommonMark syntax so Gemini's formatted replies read
    cleanly as plain text in Telegram, instead of showing raw '**' or '#'
    characters. Deliberately simple regex-based stripping, not a full
    markdown parser -- good enough for chat-length responses. We send
    plain text (no parse_mode) rather than risk Telegram's MarkdownV2
    rejecting arbitrary LLM output with a 400 over unescaped punctuation.
    """
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)                  # **bold**
    text = re.sub(r"\*(.*?)\*", r"\1", text)                       # *italic*
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)     # # headers
    text = re.sub(r"^[-*]\s+", "\u2022 ", text, flags=re.MULTILINE)  # bullets
    text = re.sub(r"`(.*?)`", r"\1", text)                         # `code`
    return text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm Nexora, your AI assistant. Ask me anything -- I can chat, "
        "answer questions, and remember our conversation as it goes."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session_id = f"telegram-{chat_id}"
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        # process_message does blocking network (Gemini) + SQLite I/O.
        # Run it in a worker thread so it never blocks the bot's asyncio
        # event loop -- otherwise one slow Gemini call would freeze every
        # other Telegram conversation this bot is handling.
        result = await asyncio.to_thread(chat_engine.process_message, session_id, user_text)
        reply_text = strip_markdown(result["reply"])
    except Exception as e:
        print(f"[telegram_bot] error handling message: {e}")
        reply_text = "Sorry, something went wrong on my end. Please try again."

    await update.message.reply_text(reply_text)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your .env file "
            "(get one by messaging @BotFather on Telegram) before running this bot."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).connect_timeout(30).read_timeout(30).get_updates_read_timeout(30).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Nexora Telegram bot starting (long polling)... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()