r"""
Feedback-driven, human-in-the-loop retraining pipeline for the intent
classifier.

What this is: pulls canned-reply bot messages that got a thumbs-down,
shows you the user message that triggered them plus what the classifier
guessed, and lets YOU decide the correct intent. Approved corrections
are appended to data/intents.csv, after which re-running
models/train_intent_classifier.py retrains on the corrected dataset.

What this is NOT: fully automatic self-learning. The model does not
retrain itself in the background and does not decide the correct label
on its own -- a thumbs-down only tells us the reply was wrong, not what
the right intent was. A human has to supply that. We only look at
feedback on CANNED replies (used_canned_reply=1), not Gemini fallback
replies -- a thumbs-down on an LLM answer could mean many things besides
"intent misclassified", and including it would add noise, not signal,
to the training data.

Run from the project root after collecting some real feedback:
    source venv/bin/activate   (or venv\Scripts\activate on Windows)
    python retrain_from_feedback.py
"""

import csv
import json
import os

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "intents.csv")
REVIEWED_PATH = os.path.join(BASE_DIR, "models", "reviewed_feedback_ids.json")


def load_known_intents():
    intents = set()
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            intents.add(row["intent"])
    return sorted(intents)


def load_existing_texts():
    texts = set()
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts.add(row["text"].strip().lower())
    return texts


def load_reviewed_ids():
    if not os.path.exists(REVIEWED_PATH):
        return set()
    with open(REVIEWED_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_reviewed_ids(ids):
    os.makedirs(os.path.dirname(REVIEWED_PATH), exist_ok=True)
    with open(REVIEWED_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)


def get_flagged_messages():
    """
    Bot replies that were canned AND got a thumbs-down -- the only case
    where negative feedback gives real evidence of a misclassification.
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            """SELECT id, session_id FROM messages
               WHERE role = 'bot' AND feedback = 'down' AND used_canned_reply = 1
               ORDER BY id ASC"""
        ).fetchall()
    return [{"bot_id": r["id"], "session_id": r["session_id"]} for r in rows]


def get_triggering_user_message(session_id, bot_id):
    """
    The user message that caused this bot reply: the most recent 'user'
    row in the same session with a smaller id. A session is only ever
    written to by one request at a time, so within one session_id, rows
    are strictly ordered user -> bot -> user -> bot.
    """
    with db.get_connection() as conn:
        row = conn.execute(
            """SELECT text, intent FROM messages
               WHERE session_id = ? AND role = 'user' AND id < ?
               ORDER BY id DESC LIMIT 1""",
            (session_id, bot_id),
        ).fetchone()
    return (row["text"], row["intent"]) if row else (None, None)


def append_correction(text, correct_intent):
    with open(DATA_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([text, correct_intent])


def main():
    known_intents = load_known_intents()
    existing_texts = load_existing_texts()
    reviewed_ids = load_reviewed_ids()

    flagged = get_flagged_messages()
    pending = [m for m in flagged if m["bot_id"] not in reviewed_ids]

    if not pending:
        print("No new thumbs-down canned replies to review. Nothing to do.")
        return

    print(f"Found {len(pending)} canned reply(ies) with thumbs-down feedback.\n")
    print(f"Known intents: {', '.join(known_intents)}\n")

    added = 0
    for item in pending:
        text, predicted_intent = get_triggering_user_message(item["session_id"], item["bot_id"])

        if not text:
            reviewed_ids.add(item["bot_id"])
            continue

        if text.strip().lower() in existing_texts:
            reviewed_ids.add(item["bot_id"])
            continue

        print(f'User said:          "{text}"')
        print(f"Classifier guessed: {predicted_intent}")
        answer = input(f"Correct intent (one of {known_intents}, or Enter to skip): ").strip()

        if not answer:
            print("Skipped.\n")
            reviewed_ids.add(item["bot_id"])
            continue

        if answer not in known_intents:
            print(f"'{answer}' is not a known intent -- skipped without changes.\n")
            reviewed_ids.add(item["bot_id"])
            continue

        append_correction(text, answer)
        existing_texts.add(text.strip().lower())
        reviewed_ids.add(item["bot_id"])
        added += 1
        print(f'Added: "{text}" -> {answer}\n')

    save_reviewed_ids(reviewed_ids)

    print(f"Done. {added} correction(s) appended to {DATA_PATH}.")
    if added:
        print("Re-run `python models/train_intent_classifier.py` to retrain on the corrected data.")


if __name__ == "__main__":
    main()