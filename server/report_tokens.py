"""Opaque capabilities for reporting persisted answers, independent of guest sync."""
import hashlib
import hmac
import os


def create_report_token(mode: str, question_id: int) -> str | None:
    if question_id <= 0:
        return None
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY is required for answer report tokens")
    message = f"answer-report:v1:{mode}:{question_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_report_token(mode: str, question_id: int, token: str | None) -> bool:
    if not token or question_id <= 0 or not token.isascii():
        return False
    expected = create_report_token(mode, question_id)
    return expected is not None and hmac.compare_digest(expected, token)
