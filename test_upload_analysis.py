#!/usr/bin/env python3
"""Quick test: upload analysis files from output/analysis/ to Feishu, bypassing upload_enabled."""

import sys
from pathlib import Path

# Ensure .env is loaded before config
from dotenv import load_dotenv
load_dotenv()

from src.config_loader import load_config
from src.feishu_uploader import FeishuUploader
from src.main import _read_analysis_file, _title_from_analysis_body, _title_from_filename, _infer_source_name


def main():
    analysis_dir = Path("output/analysis")
    config = load_config("config/config.yaml")

    # Force enable upload for this test
    config["feishu"]["upload_enabled"] = True

    uploader = FeishuUploader(config)

    files = sorted(analysis_dir.glob("*.md"))
    if not files:
        print(f"No markdown files found in {analysis_dir}")
        sys.exit(1)

    print(f"Found {len(files)} file(s) to upload\n")

    for file_path in files:
        metadata, body = _read_analysis_file(file_path, config)
        title = metadata.get("title") or _title_from_analysis_body(body) or _title_from_filename(file_path)
        source_name = metadata.get("source_name") or _infer_source_name(file_path, config)

        print(f"File:        {file_path.name}")
        print(f"Title:       {title}")
        print(f"Source name: {source_name or '(none, will use default parent)'}")

        # Show which parent node token will be used
        parent_token = uploader._resolve_parent_node_token(source_name)
        print(f"Parent node: {parent_token or '(root)'}")

        print(f"\nUploading...")
        try:
            url = uploader.upload(title, body, source_name=source_name)
            print(f"✅ Uploaded: {url}")
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            sys.exit(1)

    print("\n🎉 Done!")


if __name__ == "__main__":
    main()
