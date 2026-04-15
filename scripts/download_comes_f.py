#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


FIGSHARE_API_URL = "https://api.figshare.com/v2/articles/1466917"
DEFAULT_OUTPUT_DIR = Path("data/raw/comes_f")


def fetch_article_metadata() -> dict:
    with urlopen(FIGSHARE_API_URL, timeout=60) as response:
        return json.load(response)


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the public COMES-F workbook from Figshare.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true", help="Re-download even if the file already exists.")
    args = parser.parse_args()

    article = fetch_article_metadata()
    files = article.get("files") or []
    if not files:
        raise SystemExit("No downloadable files were exposed by the Figshare article metadata.")

    file_info = files[0]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = output_dir / file_info["name"]

    if args.force or not workbook_path.exists():
        download_file(file_info["download_url"], workbook_path)

    computed_md5 = md5sum(workbook_path)
    supplied_md5 = file_info.get("supplied_md5")
    metadata = {
        "article_id": article.get("id"),
        "title": article.get("title"),
        "doi": article.get("doi"),
        "figshare_url": article.get("figshare_url"),
        "license": article.get("license", {}).get("name"),
        "downloaded_file": str(workbook_path),
        "download_url": file_info.get("download_url"),
        "size_bytes": file_info.get("size"),
        "supplied_md5": supplied_md5,
        "computed_md5": computed_md5,
        "md5_matches": supplied_md5 == computed_md5 if supplied_md5 else None,
        "description": article.get("description"),
        "created_date": article.get("created_date"),
        "modified_date": article.get("modified_date"),
    }

    metadata_path = output_dir / "comes_f_figshare_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    if supplied_md5 and supplied_md5 != computed_md5:
        raise SystemExit("Downloaded workbook checksum does not match Figshare metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
