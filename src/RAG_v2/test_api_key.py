"""Kiểm tra GOOGLE_API_KEY có hợp lệ không.

Chạy:
    python test_api_key.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Đọc .env trong thư mục RAG_v2
_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TEST_MODEL = "gemini-3.1-flash-lite-preview"


def check_key_present() -> bool:
    if not GOOGLE_API_KEY:
        print("❌ GOOGLE_API_KEY chưa được set (kiểm tra file .env)")
        return False
    masked = GOOGLE_API_KEY[:8] + "..." + GOOGLE_API_KEY[-4:]
    print(f"✅ GOOGLE_API_KEY tìm thấy: {masked}")
    return True


def call_gemini() -> bool:
    try:
        from google import genai
        from google.genai import errors as genai_errors
    except ImportError:
        print(
            "❌ Thiếu package 'google-genai'. Cài bằng: pip install google-genai"
        )
        return False

    client = genai.Client(api_key=GOOGLE_API_KEY)

    print(f"🔄 Gọi API với model {TEST_MODEL!r} ...")
    try:
        response = client.models.generate_content(
            model=TEST_MODEL,
            contents="Trả lời 'OK' và không thêm gì khác.",
        )
        reply = response.text or ""
        print(f"✅ API phản hồi thành công: {reply.strip()!r}")
        return True

    except genai_errors.ClientError as e:
        if "API_KEY_INVALID" in str(e) or "401" in str(e):
            print(f"❌ Lỗi xác thực (API key không hợp lệ hoặc hết hạn): {e}")
        elif "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print(f"⚠️  Rate limit / quota hết: {e}")
        else:
            print(f"❌ Lỗi client: {e}")
    except Exception as e:
        print(f"❌ Lỗi không xác định: {type(e).__name__}: {e}")

    return False


def main() -> None:
    print("=" * 50)
    print("  Google API Key Test")
    print("=" * 50)

    if not check_key_present():
        sys.exit(1)

    ok = call_gemini()
    print("=" * 50)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
