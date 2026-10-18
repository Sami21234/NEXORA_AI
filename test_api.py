"""
Quick manual test script for the chatbot API. Run this with the Flask
server already running in another terminal (python server.py).
"""

import requests

BASE_URL = "http://127.0.0.1:5000"


def test_chat_canned():
    print("Testing canned reply (greeting)...")
    r = requests.post(f"{BASE_URL}/chat", json={"session_id": "test-api", "message": "hello"})
    print(r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["used_canned_reply"] is True
    print("PASSED\n")


def test_chat_gemini():
    print("Testing Gemini fallback (real question)...")
    r = requests.post(f"{BASE_URL}/chat", json={"session_id": "test-api", "message": "What is the capital of Japan?"})
    print(r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["used_canned_reply"] is False
    return r.json()["message_id"]


def test_feedback(message_id):
    print("Testing feedback endpoint...")
    r = requests.post(f"{BASE_URL}/feedback", json={"message_id": message_id, "feedback": "up"})
    print(r.status_code, r.json())
    assert r.status_code == 200
    print("PASSED\n")


def test_analytics():
    print("Testing analytics endpoint...")
    r = requests.get(f"{BASE_URL}/analytics")
    print(r.status_code, r.json())
    assert r.status_code == 200
    print("PASSED\n")


def test_missing_session_id():
    print("Testing validation (missing session_id)...")
    r = requests.post(f"{BASE_URL}/chat", json={"message": "hello"})
    print(r.status_code, r.json())
    assert r.status_code == 400
    print("PASSED\n")


if __name__ == "__main__":
    test_chat_canned()
    mid = test_chat_gemini()
    test_feedback(mid)
    test_analytics()
    test_missing_session_id()
    print("All tests passed.")