"""
Kiểm tra models available trong MegaLLM
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI


# Load config
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("MEGALLM_API_KEY")
api_url = os.getenv("MEGALLM_API_URL") or "https://ai.megallm.io/v1"

client = OpenAI(
    base_url=api_url,
    api_key=api_key,
)

print("🔍 Checking available models...")
print()

try:
    models = client.models.list()
    print(f"✅ Found {len(models.data)} models:")
    print()
    for model in models.data:
        print(f"  • {model.id}")
except Exception as e:
    print(f"❌ Error: {e}")
    print()
    print("Trying some common models...")

    test_models = [
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "claude-3-5-sonnet-20241022",
        "claude-3-haiku",
    ]

    for model_name in test_models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            print(f"  ✅ {model_name} - AVAILABLE")
        except Exception as e:
            if "permission" in str(e).lower():
                print(f"  ❌ {model_name} - NOT AVAILABLE (free tier)")
            else:
                print(f"  ❌ {model_name} - {str(e)[:50]}")
