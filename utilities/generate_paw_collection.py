"""
generate_paw_collection.py

Reads _data/paw_prints.csv (one column: image_path) and:
  1. Copies each image into objects/ as paw_001.jpg, paw_002.jpg, …
  2. Writes _data/paw-print-repository.csv with CollectionBuilder metadata

Run from the repo root or from the utilities/ directory:
    python utilities/generate_paw_collection.py
"""

import csv
import json
import random
import re
import shutil
from pathlib import Path

import reverse_geocoder
from tqdm import tqdm
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Paths
REPO_ROOT = Path(__file__).parent.parent
SRC_CSV = REPO_ROOT / "_data" / "paw_prints.csv"
OUT_CSV = REPO_ROOT / "_data" / "paw-print-repository.csv"
OBJ_DIR = REPO_ROOT / "objects"
GEO_CACHE_FILE = REPO_ROOT / "_data" / "geo_cache.json"

FIELDNAMES = [
    "objectid",
    "title",
    "date",
    "time",
    "description",
    "subject",
    "species",
    "location",
    "country",
    "latitude",
    "longitude",
    "type",
    "format",
    "display_template",
    "object_location",
    "image_small",
    "image_thumb",
]


def extract_gps(image_path: Path):
    """Return (latitude, longitude) as decimal-degree strings, or ('', '') if not found."""
    try:
        img = Image.open(image_path)
        exif_raw = img._getexif()
        if not exif_raw:
            return "", ""
        # Find the GPSInfo tag
        gps_raw = None
        for tag_id, value in exif_raw.items():
            if TAGS.get(tag_id) == "GPSInfo":
                gps_raw = value
                break
        if not gps_raw:
            return "", ""
        gps = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

        def to_decimal(coord, ref):
            d, m, s = (float(x) for x in coord)
            dec = d + m / 60 + s / 3600
            if ref in ("S", "W"):
                dec = -dec
            return round(dec, 6)

        lat = to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
        lon = to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
        return str(lat), str(lon)
    except Exception:
        return "", ""


def extract_date(path_str: str) -> str:
    """Try to pull a date out of the filename (YYYYMMDD) or fall back to the year folder."""
    stem = Path(path_str).stem
    # Match YYYYMMDD at the start or anywhere in the stem
    m = re.search(r"(\d{4})(\d{2})(\d{2})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Fall back: grab a 4-digit year from the path (e.g. \2023\)
    m2 = re.search(r"[/\\](\d{4})[/\\]", path_str)
    if m2:
        return m2.group(1)
    return ""


def extract_time(image_path: Path) -> str:
    """Return time as HH:MM:SS from EXIF DateTimeOriginal, or '' if not found."""
    try:
        img = Image.open(image_path)
        exif_raw = img._getexif()
        if not exif_raw:
            return ""
        for tag_id, value in exif_raw.items():
            if TAGS.get(tag_id) in ("DateTimeOriginal", "DateTime"):
                # EXIF format: "YYYY:MM:DD HH:MM:SS"
                parts = str(value).strip().split(" ")
                if len(parts) == 2:
                    return parts[1]
        return ""
    except Exception:
        return ""


def main():
    OBJ_DIR.mkdir(exist_ok=True)

    # Read source paths
    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        paths = [row["image_path"].strip() for row in csv.DictReader(f) if row["image_path"].strip()]

    if not paths:
        print("No image paths found in paw_prints.csv — nothing to do.")
        return

    CC_TO_NAME = {
        "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AR": "Argentina",
        "AU": "Australia", "AT": "Austria", "BE": "Belgium", "BR": "Brazil",
        "BG": "Bulgaria", "CA": "Canada", "CL": "Chile", "CN": "China",
        "CO": "Colombia", "HR": "Croatia", "CZ": "Czech Republic", "DK": "Denmark",
        "EG": "Egypt", "EE": "Estonia", "FI": "Finland", "FR": "France",
        "DE": "Germany", "GR": "Greece", "HK": "Hong Kong", "HU": "Hungary",
        "IN": "India", "ID": "Indonesia", "IE": "Ireland", "IL": "Israel",
        "IT": "Italy", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan",
        "KE": "Kenya", "KR": "South Korea", "LV": "Latvia", "LT": "Lithuania",
        "LU": "Luxembourg", "MY": "Malaysia", "MX": "Mexico", "NL": "Netherlands",
        "NZ": "New Zealand", "NG": "Nigeria", "NO": "Norway", "PK": "Pakistan",
        "PE": "Peru", "PH": "Philippines", "PL": "Poland", "PT": "Portugal",
        "RO": "Romania", "RU": "Russia", "SA": "Saudi Arabia", "SG": "Singapore",
        "SK": "Slovakia", "ZA": "South Africa", "ES": "Spain", "SE": "Sweden",
        "CH": "Switzerland", "TW": "Taiwan", "TH": "Thailand", "TR": "Turkey",
        "UA": "Ukraine", "GB": "United Kingdom", "US": "United States",
        "VN": "Vietnam",
    }

    # Load geo cache from disk; keys are "lat,lon" strings
    if GEO_CACHE_FILE.exists():
        geo_cache = json.loads(GEO_CACHE_FILE.read_text(encoding="utf-8"))
    else:
        geo_cache = {}

    rows = []
    errors = []

    for i, src_path in enumerate(tqdm(paths, desc="Processing images"), 1):
        src = Path(src_path)
        oid = f"paw_{i:03d}"
        ext = src.suffix.lower() or ".jpg"
        dest_name = f"{oid}{ext}"
        dest = OBJ_DIR / dest_name

        if not src.exists():
            print(f"  WARNING: source not found, skipping — {src_path}")
            errors.append(src_path)
            continue

        shutil.copy2(src, dest)

        date = extract_date(src_path)
        time = extract_time(src)
        lat, lon = extract_gps(src)
        title = f"Paw Print {i}" + (f" ({date})" if date else "")

        location = ""
        country_name = ""
        if lat and lon:
            cache_key = f"{lat},{lon}"
            if cache_key in geo_cache:
                location, country_name = geo_cache[cache_key]
            else:
                result = reverse_geocoder.search([(float(lat), float(lon))], verbose=False)[0]
                city = result.get("name", "")
                cc = result.get("cc", "")
                location = f"{city}, {cc}" if city else cc
                country_name = CC_TO_NAME.get(cc, cc)
                geo_cache[cache_key] = [location, country_name]

        obj_path = f"/objects/{dest_name}"
        rows.append({
            "objectid": oid,
            "title": title,
            "date": date,
            "time": time,
            "description": "",
            "subject": "",
            "species": random.choice(["species1", "species2", "species3"]),
            "location": location,
            "country": country_name,
            "latitude": lat,
            "longitude": lon,
            "type": "Image",
            "format": "image/jpeg",
            "display_template": "image",
            "object_location": obj_path,
            "image_small": obj_path,
            "image_thumb": obj_path,
        })

    # Flush geo cache to disk
    GEO_CACHE_FILE.write_text(json.dumps(geo_cache, indent=2), encoding="utf-8")

    # Write metadata CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    gps_count = sum(1 for r in rows if r["latitude"])
    print(f"Done. {len(rows)} items written to {OUT_CSV}")
    print(f"  {gps_count} of {len(rows)} images have GPS coordinates")
    if errors:
        print(f"  {len(errors)} file(s) not found and skipped:")
        for e in errors:
            print(f"    {e}")
    print()
    print("Next steps:")
    print("  1. Run 'bundle exec jekyll serve' to preview the site")
    print("  2. Optionally run 'rake generate_derivatives' to create thumbnails/small images")


if __name__ == "__main__":
    main()
