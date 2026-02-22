"""
setup_annotation.py

Copies each source image from _data/paw_prints.csv into the annotation/ folder
using the original filename. Handles duplicate filenames by appending _2, _3, etc.
Maintains _data/annotation_map.csv as a stable source_file → annotation_file mapping.

Run from the repo root or from the utilities/ directory:
    python utilities/setup_annotation.py
"""

import csv
import shutil
from pathlib import Path

from tqdm import tqdm

REPO_ROOT      = Path(__file__).parent.parent
SRC_CSV        = REPO_ROOT / "_data" / "paw_prints.csv"
ANNOTATION_MAP = REPO_ROOT / "_data" / "annotation_map.csv"
ANNOTATION_DIR = REPO_ROOT / "annotation"


def load_map() -> dict:
    """Return existing {source_file: annotation_file} mapping, or empty dict."""
    if not ANNOTATION_MAP.exists():
        return {}
    with open(ANNOTATION_MAP, newline="", encoding="utf-8") as f:
        return {row["source_file"]: row["annotation_file"] for row in csv.DictReader(f)}


def save_map(mapping: dict) -> None:
    with open(ANNOTATION_MAP, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source_file", "annotation_file"])
        writer.writeheader()
        for src, ann in mapping.items():
            writer.writerow({"source_file": src, "annotation_file": ann})


def unique_name(wanted: str, taken: set) -> str:
    """Return wanted if not in taken, otherwise wanted_2, wanted_3, …"""
    if wanted not in taken:
        return wanted
    stem = Path(wanted).stem
    suffix = Path(wanted).suffix
    i = 2
    while True:
        candidate = f"{stem}_{i}{suffix}"
        if candidate not in taken:
            return candidate
        i += 1


def main():
    ANNOTATION_DIR.mkdir(exist_ok=True)

    # Read source paths
    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        paths = [row["image_path"].strip() for row in csv.DictReader(f) if row["image_path"].strip()]

    if not paths:
        print("No image paths found in paw_prints.csv — nothing to do.")
        return

    # Load existing mapping
    mapping = load_map()

    # Remove entries no longer in the CSV
    current_paths = set(paths)
    removed_count = 0
    for src_path in list(mapping):
        if src_path not in current_paths:
            ann_name = mapping.pop(src_path)
            img_file = ANNOTATION_DIR / ann_name
            json_file = ANNOTATION_DIR / (Path(ann_name).stem + ".json")
            if img_file.exists():
                img_file.unlink()
            if json_file.exists():
                json_file.unlink()
            removed_count += 1

    taken = set(mapping.values())  # annotation filenames already reserved

    new_count = 0
    skip_count = 0
    error_count = 0

    for src_path in tqdm(paths, desc="Setting up annotation folder"):
        src = Path(src_path)

        # Already in map → skip (preserves existing txt files)
        if src_path in mapping:
            skip_count += 1
            continue

        if not src.exists():
            print(f"  WARNING: source not found, skipping — {src_path}")
            error_count += 1
            continue

        ann_name = unique_name(src.name, taken)
        dest = ANNOTATION_DIR / ann_name

        shutil.copy2(src, dest)
        mapping[src_path] = ann_name
        taken.add(ann_name)
        new_count += 1

    save_map(mapping)

    print(f"\nDone.")
    print(f"  {new_count} image(s) newly copied to annotation/")
    print(f"  {skip_count} image(s) already mapped (skipped)")
    if removed_count:
        print(f"  {removed_count} image(s) removed (no longer in CSV)")
    if error_count:
        print(f"  {error_count} source file(s) not found and skipped")
  

if __name__ == "__main__":
    main()
