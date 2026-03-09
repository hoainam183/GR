import json
import sys


def extract_texts(data):
    texts = []

    # Handle both dict with "result.points" and direct list
    if isinstance(data, dict):
        points = data.get("result", {}).get("points", [])
    elif isinstance(data, list):
        points = data
    else:
        points = []

    for point in points:
        text = point.get("payload", {}).get("text")
        if text:
            texts.append(text)

    return texts


if __name__ == "__main__":
    # Đọc từ file nếu có argument, ngược lại đọc từ stdin
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    texts = extract_texts(data)

    # Lưu vào file JSON mới
    output_file = "texts_quydinh.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)

    print(f"Đã lưu {len(texts)} texts vào '{output_file}'")
