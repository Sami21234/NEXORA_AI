"""
Flask web server for the Dynamic AI Chatbot. All the real logic (NLP,
Gemini calls, context memory, logging) lives in chat_engine.py and db.py --
this file is just the thin HTTP layer on top, deliberately kept small.
"""

from flask import Flask, request, jsonify, send_from_directory      
from flask_cors import CORS
import db
import chat_engine

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

db.init_db()

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    message = data.get("message", "").strip()

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        result = chat_engine.process_message(session_id, message)
        return jsonify(result)
    except Exception as e:
        print(f"[server] /chat error: {e}")
        return jsonify({"error": "Something went wrong processing your message."}), 500

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json(silent=True) or {}
    message_id = data.get("message_id")
    value = data.get("feedback")

    if value not in ("up", "down"):
        return jsonify({"error": "feedback must be 'up' or 'down'"}), 400
    if not message_id:
        return jsonify({"error": "message_id is required"}), 400

    ok = db.set_feedback(message_id, value)
    if not ok:
        return jsonify({"error": "message_id not found"}), 404
    return jsonify({"status": "ok"})

@app.route("/analytics")
def analytics():
    return jsonify(db.get_analytics())


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
