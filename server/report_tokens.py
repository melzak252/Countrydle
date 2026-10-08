"""Opaque capabilities for reporting persisted answers, independent of guest sync."""
import hashlib
import hmac
from runtime_configuration import SECRET_KEY


def create_report_token(mode: str, question_id: int) -> str | None:
    if question_id <= 0:
        return None
    message = f"answer-report:v1:{mode}:{question_id}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_report_token(mode: str, question_id: int, token: str | None) -> bool:
    if not token or question_id <= 0 or not token.isascii():
        return False
    expected = create_report_token(mode, question_id)
    return expected is not None and hmac.compare_digest(expected, token)
