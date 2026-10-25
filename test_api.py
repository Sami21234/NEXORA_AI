"""
End-to-end test suite for the Flask API. Hits a REAL running server over
HTTP (not Flask's test client) -- these are integration tests of the
actual request/response contract, including the real Gemini API call for
the fallback case. Run the server first:

    python server.py

Then, in a second terminal:
    python test_api.py

Each test is independent and prints PASS/FAIL with the reason -- nothing
here is faked or skipped to make the count look better.
"""

import sys

import requests

BASE_URL = "http://127.0.0.1:5000"
results = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append(condition)
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))


def test_canned_reply():
    r = requests.post(f"{BASE_URL}/chat", json={"session_id": "test-canned", "message": "hello"})
    ok = r.status_code == 200
    data = r.json() if ok else {}
    check("canned reply: status 200", ok, f"got {r.status_code}")
    check("canned reply: used_canned_reply is True", ok and data.get("used_canned_reply") is True, f"got {data}")
    check("canned reply: reply text present", ok and bool(data.get("reply")), f"got {data}")
    check("canned reply: message_id present", ok and data.get("message_id") is not None, f"got {data}")
    return data


def test_gemini_fallback():
    r = requests.post(
        f"{BASE_URL}/chat",
        json={"session_id": "test-fallback", "message": "explain how neural networks work"},
    )
    ok = r.status_code == 200
    data = r.json() if ok else {}
    check("gemini fallback: status 200", ok, f"got {r.status_code}")
    check("gemini fallback: used_canned_reply is False", ok and data.get("used_canned_reply") is False, f"got {data}")
    check("gemini fallback: reply text present", ok and bool(data.get("reply")), f"got {data}")
    return data


def test_context_memory():
    session_id = "test-context"
    requests.post(f"{BASE_URL}/chat", json={"session_id": session_id, "message": "my name is Sami"})
    r = requests.post(f"{BASE_URL}/chat", json={"session_id": session_id, "message": "what did I just tell you my name was?"})
    ok = r.status_code == 200
    data = r.json() if ok else {}
    reply_mentions_name = ok and "sami" in data.get("reply", "").lower()
    check("context memory: status 200", ok, f"got {r.status_code}")
    check("context memory: reply references earlier turn", reply_mentions_name, f"got reply: {data.get('reply')}")


def test_feedback_valid(message_id):
    r = requests.post(f"{BASE_URL}/feedback", json={"message_id": message_id, "feedback": "up"})
    ok = r.status_code == 200
    check("feedback: valid vote returns 200", ok, f"got {r.status_code} {r.text}")


def test_feedback_invalid_value(message_id):
    r = requests.post(f"{BASE_URL}/feedback", json={"message_id": message_id, "feedback": "sideways"})
    check("feedback: invalid value returns 400", r.status_code == 400, f"got {r.status_code}")


def test_feedback_missing_message_id():
    r = requests.post(f"{BASE_URL}/feedback", json={"feedback": "up"})
    check("feedback: missing message_id returns 400", r.status_code == 400, f"got {r.status_code}")


def test_history():
    session_id = "test-history"
    requests.post(f"{BASE_URL}/chat", json={"session_id": session_id, "message": "hi"})
    r = requests.get(f"{BASE_URL}/history/{session_id}")
    ok = r.status_code == 200
    data = r.json() if ok else []
    check("history: status 200", ok, f"got {r.status_code}")
    check("history: returns at least 2 messages (user + bot)", ok and len(data) >= 2, f"got {len(data) if ok else 'n/a'} messages")
    check(
        "history: ordered user then bot",
        ok and len(data) >= 2 and data[0]["role"] == "user" and data[1]["role"] == "bot",
        f"got roles: {[m.get('role') for m in data[:2]]}" if ok else "n/a",
    )


def test_analytics():
    r = requests.get(f"{BASE_URL}/analytics")
    ok = r.status_code == 200
    data = r.json() if ok else {}
    expected_keys = {
        "total_conversations",
        "total_messages",
        "avg_response_time_ms",
        "sentiment_distribution",
        "intent_distribution",
        "canned_reply_vs_llm",
        "feedback",
    }
    check("analytics: status 200", ok, f"got {r.status_code}")
    check("analytics: all expected keys present", ok and expected_keys.issubset(data.keys()), f"got keys: {list(data.keys())}")
    check("analytics: total_conversations is a non-negative int", ok and isinstance(data.get("total_conversations"), int) and data["total_conversations"] >= 0)


def test_chat_validation():
    r1 = requests.post(f"{BASE_URL}/chat", json={"message": "hi"})
    check("validation: missing session_id returns 400", r1.status_code == 400, f"got {r1.status_code}")

    r2 = requests.post(f"{BASE_URL}/chat", json={"session_id": "test-validation"})
    check("validation: missing message returns 400", r2.status_code == 400, f"got {r2.status_code}")

    r3 = requests.post(f"{BASE_URL}/chat", json={"session_id": "test-validation", "message": "   "})
    check("validation: whitespace-only message returns 400", r3.status_code == 400, f"got {r3.status_code}")


def main():
    print("Running Nexora API test suite against", BASE_URL, "\n")

    canned_data = test_canned_reply()
    test_gemini_fallback()
    test_context_memory()

    if canned_data.get("message_id") is not None:
        test_feedback_valid(canned_data["message_id"])
        test_feedback_invalid_value(canned_data["message_id"])
    test_feedback_missing_message_id()

    test_history()
    test_analytics()
    test_chat_validation()

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} checks passed.")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()