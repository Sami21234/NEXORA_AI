"""
Shared chat logic used by both the web backend (server.py) and the Telegram
bot (telegram_bot.py). Keeping this in one place means both front ends use
the exact same NLP pipeline, context-memory logic, and logging -- not two
copies that could silently drift apart.
"""

import os
import random
import time
import requests
from dotenv import load_dotenv
import db
from nlp_pipeline import pipeline

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-flash-lite-latest"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

BOT_NAME = "Nexora"

# Canned replies for small-talk intents. Several variants per intent, chosen at random, so the bot doesn't sound robotically repetitive on these --
# this is NLG (response generation) built on top of a real NLU prediction (the intent classifier), not a hardcoded keyword match pretending to be one.

CANNED_REPLIES = {
    "greeting": [
        f"Hello! I'm {BOT_NAME}. How can I help you today?",
        "Hi there! What can I do for you?",
        "Hey! Good to see you. What's on your mind?",
    ],
    "goodbye": [
        "Goodbye! Feel free to come back anytime.",
        "Bye! Have a great day.",
        "See you later!",
    ],
    "thanks": [
        "You're welcome!",
        "Happy to help!",
        "Anytime!",
    ],
    "how_are_you": [
        "I'm doing well, thanks for asking! How can I help you today?",
        "All good on my end! What can I do for you?",
    ],
    "what_can_you_do": [
        f"I'm {BOT_NAME}, an AI chatbot. I can chat about most topics, answer "
        "questions, detect the sentiment of what you write, and pick out "
        "names/places/dates from your messages. Ask me anything!",
    ],
    "joke": [
        "Why don't scientists trust atoms? Because they make up everything!",
        "I told my computer I needed a break, and it said no problem — it froze immediately.",
        "Why do programmers prefer dark mode? Because light attracts bugs.",
    ],
    "identity": [
        f"I'm {BOT_NAME}, an AI chatbot built with Flask and Google's Gemini model, "
        "with some extra natural language processing on top for intent "
        "detection, sentiment analysis, and entity recognition.",
    ],
    "help": [
        "I'm here to help! You can ask me questions, chat casually, or just "
        "say hello. What do you need?",
    ],
}

def get_canned_reply(intent):
    return random.choice(CANNED_REPLIES[intent])

def call_gemini(history, user_text, _retry=True):
    """
    Sends real multi-turn conversation history to Gemini, not just the
    current message in isolation -- this is the context-memory fix over the
    original starter code, which had none.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment (.env file).")

    contents = []
    for turn in history:
        role = "user" if turn["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": turn["text"]}]})
    contents.append({"role": "user", "parts": [{"text": user_text}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 1000,
        },
    }

    response = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if response.status_code == 503 and _retry:
        # Google's servers report transient overload -- worth one retry
        # after a short wait before giving up, since this isn't a bug in
        # our request, it's the provider being temporarily busy.
        print("[chat_engine] Gemini returned 503, retrying once after 2s...")
        time.sleep(2)
        return call_gemini(history, user_text, _retry=False)

    if response.status_code != 200:
        raise RuntimeError(f"Gemini API error {response.status_code}: {response.text[:300]}")

    data = response.json()
    candidates = data.get("candidates")
    if not candidates or not candidates[0].get("content", {}).get("parts"):
        raise RuntimeError(f"Gemini returned no usable content: {data}")

    return candidates[0]["content"]["parts"][0]["text"]

def process_message(session_id, user_text):
    """
    The single entry point both server.py and telegram_bot.py call.
    Returns a dict with everything the caller needs to respond to the user
    and (for the web UI) attach feedback to the specific bot message later.
    """
    start_time = time.time()

    analysis = pipeline.analyze(user_text)
    sentiment = analysis["sentiment"]
    intent = analysis["intent"]
    entities = analysis["entities"]

    db.log_message(
        session_id, "user", user_text,
        sentiment=sentiment, intent=intent, entities=entities,
    )

    if intent["use_canned_reply"]:
        reply_text = get_canned_reply(intent["intent"])
        used_canned_reply = True
    else:
        history = db.get_recent_history(session_id, limit=6)
        try:
            reply_text = call_gemini(history, user_text)
        except Exception as e:
            reply_text = (
                "Sorry, I'm having trouble reaching my AI service right now. "
                "Please try again in a moment."
            )
            print(f"[chat_engine] Gemini call failed: {e}")
        used_canned_reply = False

    response_time_ms = (time.time() - start_time) * 1000

    message_id = db.log_message(
        session_id, "bot", reply_text,
        used_canned_reply=used_canned_reply,
        response_time_ms=response_time_ms,
    )

    return {
        "reply": reply_text,
        "message_id": message_id,
        "sentiment": sentiment,
        "intent": intent["intent"],
        "entities": entities,
        "used_canned_reply": used_canned_reply,
        "response_time_ms": round(response_time_ms, 1),
    }