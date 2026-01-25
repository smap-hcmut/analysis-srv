"""
Download PhoBERT ONNX model artifacts from a MinIO server using Python SDK.

This script is intended to be run via:

    uv run python scripts/download_phobert_model.py

It mirrors the behaviour of `scripts/download_phobert_model.sh`:
- Uses the same bucket name, version and target directory.
- Downloads the same required files.
- Reads MinIO connection info from environment variables that the shell
  script already collects:
    - MINIO_ENDPOINT  (e.g. 192.168.1.100:9000)
    - MINIO_ACCESS_KEY
    - MINIO_SECRET_KEY

Credentials are required; the bucket does NOT need to be public.
"""

from __future__ import annotations

import os
import sys
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv  # type: ignore
from minio import Minio  # type: ignore
from minio.error import S3Error  # type: ignore


BUCKET_NAME = "phobert-onnx-artifacts"
VERSION = "v2"
TARGET_DIR = Path("infrastructure/phobert/models")
REQUIRED_FILES = [
    "added_tokens.json",
    "bpe.codes",
    "model_quantized.onnx",
    "config.json",
    "vocab.txt",
    "special_tokens_map.json",
    "tokenizer_config.json",
]


def _get_env(name: str, prompt: str, secret: bool = False) -> str:
    """
    Resolve a configuration value with the following precedence:
    1. Environment variables (including values loaded from .env)
    2. Interactive prompt (if running in a TTY)
    """
    value = os.getenv(name)
    if value:
        return value

    # If running interactively, fall back to prompting the user.
    if sys.stdin.isatty():
        if secret:
            value = getpass(prompt)
        else:
            value = input(prompt)

        if not value:
            raise SystemExit(f"{name} is required and was not provided.")

        # Make it available to subsequent calls in this process.
        os.environ[name] = value
        return value

    # Non-interactive and no env value available.
    raise SystemExit(
        f"Environment variable {name} is required but not set, and no TTY is available "
        "for interactive input."
    )


def main() -> None:
    # Load .env so users can configure MINIO_* there without exporting manually.
    load_dotenv()

    endpoint = _get_env(
        "MINIO_ENDPOINT",
        "Enter MinIO server IP/hostname (e.g., 192.168.1.100:9000): ",
        secret=False,
    )
    access_key = _get_env("MINIO_ACCESS_KEY", "Enter MinIO Access Key: ", secret=False)
    secret_key = _get_env("MINIO_SECRET_KEY", "Enter MinIO Secret Key: ", secret=True)

    # Ensure target directory exists
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Normalise endpoint: script expects host:port, Minio SDK needs same without scheme
    # The shell script already prepends "http://" when using mc, so we keep that behaviour.
    client = Minio(
        (
            endpoint
            if not endpoint.startswith(("http://", "https://"))
            else endpoint.split("://", 1)[1]
        ),
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )

    print(f"Using MinIO endpoint: {endpoint}")
    print(f"Bucket: {BUCKET_NAME}, version: {VERSION}")
    print(f"Target directory: {TARGET_DIR}")
    print("")

    # Download each required file
    for filename in REQUIRED_FILES:
        object_name = f"{VERSION}/{filename}"
        target_path = TARGET_DIR / filename

        print(f"Downloading {object_name} -> {target_path} ...")

        try:
            response = client.get_object(BUCKET_NAME, object_name)
            try:
                with target_path.open("wb") as f:
                    for chunk in response.stream(32 * 1024):
                        f.write(chunk)
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise SystemExit(
                f"❌ Failed to download {filename} from bucket '{BUCKET_NAME}': {exc}"
            ) from exc

    print("\n✅ Download complete!\n")
    print("Verifying downloaded files...")
    for filename in REQUIRED_FILES:
        path = TARGET_DIR / filename
        if not path.is_file():
            raise SystemExit(f"  ✗ {filename} (missing)")
        size = path.stat().st_size
        print(f"  ✓ {filename} ({size} bytes)")

    print("\n🎉 All model files downloaded successfully!")
    print(f"   Location: {TARGET_DIR}")


if __name__ == "__main__":
    main()
