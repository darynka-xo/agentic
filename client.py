import argparse
import json
import os
from pathlib import Path

import requests

SERVER_URL = os.getenv("VALIDATOR_URL", "http://localhost:8000")


def load_payload(path: str):
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Payload file not found: {path}")
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Send a Tabula row JSON to the Estimate Validator API."
    )
    parser.add_argument(
        "--payload-file",
        required=True,
        help="Path to a JSON file containing the Tabula row.",
    )
    parser.add_argument(
        "--route",
        default="/predict",
        help="API route to hit (default: /predict).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds (default: 60).",
    )
    args = parser.parse_args()

    tabula_json = load_payload(args.payload_file)
    payload = {"tabula_json": tabula_json}

    try:
        response = requests.post(
            f"{SERVER_URL}{args.route}", json=payload, timeout=args.timeout
        )
        response.raise_for_status()
        output = response.json().get("output")
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except requests.RequestException as exc:  # pragma: no cover - CLI helper
        print(f"Error sending request: {exc}")


if __name__ == "__main__":
    main()

