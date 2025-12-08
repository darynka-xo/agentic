#!/usr/bin/env python3
"""
Test if Ollama can do JSON extraction.
"""

import os
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ollama/qwen3:30b").replace("ollama/", "")

prompt = """Extract these fields from the text into JSON:
1. text_description: main description
2. table_code_claimed: code like '1706-0201-01'
3. X_claimed: numeric value
4. total_claimed: final cost
5. extracted_tags: list of tags

Text: "1 Жилой дом Секция 1 12 этажей м2 4 675,08 Сборник цен табл. 1706-0201-01 Сейсмичность 7 баллов монолитное здание 52 690 700"

Return ONLY valid JSON, no other text.

Example:
{"text_description": "Жилой дом Секция 1 12 этажей", "table_code_claimed": "1706-0201-01", "X_claimed": 4675.08, "total_claimed": 52690700, "extracted_tags": ["жилой дом", "12 этажей", "монолитное", "сейсмичность"]}
"""

print(f"Testing {OLLAMA_MODEL} at {OLLAMA_BASE_URL}")
print("=" * 60)

try:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 512
            }
        },
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        generated = result.get("response", "")
        
        print("✓ Ollama responded:")
        print("-" * 60)
        print(generated)
        print("-" * 60)
        
        # Try to parse as JSON
        import json
        try:
            parsed = json.loads(generated)
            print("\n✓ Valid JSON!")
            print("Fields:")
            for key, value in parsed.items():
                print(f"  {key}: {value}")
        except json.JSONDecodeError as e:
            print(f"\n✗ NOT valid JSON: {e}")
            print("This is why LLM returns None/empty!")
            print("\nSolutions:")
            print("1. Try a different model: export OLLAMA_MODEL='ollama/qwen2.5:7b'")
            print("2. Or use a model with better JSON support like llama3")
    else:
        print(f"✗ HTTP {response.status_code}: {response.text}")

except Exception as e:
    print(f"✗ Error: {e}")

