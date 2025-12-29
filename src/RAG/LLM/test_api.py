"""
Test MegaLLM API connection
Quick test để kiểm tra API hoạt động trước khi chạy RAG đầy đủ
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI


def test_api_connection():
    """Test API connection với MegaLLM"""
    print("=" * 70)
    print("🧪 TESTING MEGALLM API CONNECTION")
    print("=" * 70)
    print()

    # Load config
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("MEGALLM_API_KEY")
    api_url = os.getenv("MEGALLM_API_URL")
    model_name = os.getenv("MEGALLM_MODEL")

    print("📋 Configuration:")
    print(f"   Base URL: {api_url}")
    print(f"   Model: {model_name}")
    print(
        f"   API Key: {api_key[:20]}..." if api_key else "   API Key: NOT SET"
    )
    print()

    if not api_key or api_key == "your_megallm_api_key_here":
        print("❌ ERROR: API key chưa được cấu hình!")
        print("   Hãy cập nhật MEGALLM_API_KEY trong file .env")
        print()
        print("📝 Hướng dẫn:")
        print("   1. Lấy API key từ https://ai.megallm.io/")
        print("   2. Mở file: d:\\GR\\.env")
        print("   3. Sửa dòng: MEGALLM_API_KEY = your_key_here")
        return False

    if not api_url:
        api_url = "https://ai.megallm.io/v1"
        print(f"   Using default URL: {api_url}")

    if not model_name:
        model_name = "gpt-4o-mini"
        print(f"   Using default model: {model_name}")

    # Test với OpenAI SDK
    print()
    print("🔄 Testing API connection...")
    print()

    try:
        client = OpenAI(
            base_url=api_url,
            api_key=api_key,
        )

        # Simple test
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": "Hello! Please respond in Vietnamese: Xin chào!",
                }
            ],
            temperature=0.7,
            max_tokens=100,
        )

        message = response.choices[0].message.content

        print("✅ SUCCESS! API hoạt động tốt!")
        print()
        print("📩 Response:")
        print("-" * 70)
        print(message)
        print("-" * 70)
        print()
        print("🎉 Bạn có thể chạy RAG system ngay bây giờ:")
        print("   python main_megallm.py")
        print("   hoặc:")
        print("   python llm_megallm.py")
        print()
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()

        # Common errors
        error_str = str(e).lower()
        if "unauthorized" in error_str or "401" in error_str:
            print("💡 Lỗi xác thực - Kiểm tra API key")
            print("   Lấy key tại: https://ai.megallm.io/")
        elif "not found" in error_str or "404" in error_str:
            print("💡 API endpoint không tồn tại - Kiểm tra MEGALLM_API_URL")
        elif "rate limit" in error_str or "429" in error_str:
            print("💡 Rate limit - Đợi vài giây rồi thử lại")
        elif "model" in error_str:
            print("💡 Model không tồn tại")
            print(
                "   Available models: gpt-5, gpt-4o, claude-3-5-sonnet-20241022"
            )

        return False


if __name__ == "__main__":
    success = test_api_connection()

    if not success:
        print()
        print("=" * 70)
        print("📚 Tài liệu hữu ích:")
        print("=" * 70)
        print("   - QUICKSTART_MEGALLM.md - Hướng dẫn setup từng bước")
        print("   - README_MEGALLM.md - Chi tiết đầy đủ")
        print()
