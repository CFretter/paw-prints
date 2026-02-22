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
import re
import shutil
import subprocess
from pathlib import Path

import reverse_geocoder
from tqdm import tqdm
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from PIL import IptcImagePlugin

# Paths
REPO_ROOT      = Path(__file__).parent.parent
SRC_CSV        = REPO_ROOT / "_data" / "paw_prints.csv"
OUT_CSV        = REPO_ROOT / "_data" / "paw-print-repository.csv"
OBJ_DIR        = REPO_ROOT / "objects"
GEO_CACHE_FILE = REPO_ROOT / "_data" / "geo_cache.json"
ANNOTATION_MAP = REPO_ROOT / "_data" / "annotation_map.csv"
ANNOTATION_DIR = REPO_ROOT / "annotation"

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
    "spotter",
    "source_file",
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


def extract_date(path_str: str, image_path: Path = None) -> str:
    """Try to pull a date from filename (YYYYMMDD), then EXIF, then year folder."""
    stem = Path(path_str).stem
    m = re.search(r"(\d{4})(\d{2})(\d{2})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Try EXIF DateTimeOriginal
    if image_path:
        try:
            img = Image.open(image_path)
            exif_raw = img._getexif()
            if exif_raw:
                for tag_id, value in exif_raw.items():
                    if TAGS.get(tag_id) in ("DateTimeOriginal", "DateTime"):
                        parts = str(value).strip().split(" ")
                        if parts:
                            d = parts[0].split(":")
                            if len(d) == 3 and len(d[0]) == 4:
                                y, mo, dy = int(d[0]), int(d[1]), int(d[2])
                                if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= dy <= 31:
                                    return f"{d[0]}-{d[1]}-{d[2]}"
        except Exception:
            pass
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


def extract_spotter(image_path: Path) -> str:
    """Return IPTC Credit (2, 110) value, or 'Christoph' if absent or empty."""
    try:
        img = Image.open(image_path)
        iptc = IptcImagePlugin.getiptcinfo(img)
        if iptc:
            credit = iptc.get((2, 110), b"")
            if isinstance(credit, list):
                credit = credit[0]
            value = credit.decode("utf-8", errors="replace").strip()
            if value:
                return value
    except Exception:
        pass
    return "Christoph"


def _read_species(src_path: str, annotation_map: dict) -> str:
    """Return semicolon-joined true flags from the LabelMe .json sidecar, or ''."""
    ann_file = annotation_map.get(src_path)
    if not ann_file:
        return ""
    json_path = ANNOTATION_DIR / (Path(ann_file).stem + ".json")
    if not json_path.exists():
        return ""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        active = [k for k, v in data.get("flags", {}).items() if v]
        return ";".join(active)
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

    paths.sort(key=lambda p: extract_date(p, Path(p)) or "0000")

    CC_TO_NAME = {
        "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AR": "Argentina",
        "AU": "Australia", "AT": "Austria", "BE": "Belgium", "BR": "Brazil",
        "BG": "Bulgaria", "CA": "Canada", "CL": "Chile", "CN": "China",
        "CO": "Colombia", "HR": "Croatia", "CZ": "Czech Republic", "DK": "Denmark",
        "EG": "Egypt", "EE": "Estonia", "FI": "Finland", "FR": "France",
        "DE": "Germany", "GR": "Greece", "HK": "Hong Kong", "HU": "Hungary",
        "IN": "India", "ID": "Indonesia", "IE": "Ireland", "IL": "Israel",
        "IT": "Italy", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan",
        "KE": "Kenya", "KR": "South Korea", "LA": "Laos", "LV": "Latvia", "LT": "Lithuania",
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

    # Load annotation map (source_file -> annotation_file)
    annotation_map = {}
    if ANNOTATION_MAP.exists():
        with open(ANNOTATION_MAP, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                annotation_map[row["source_file"]] = row["annotation_file"]

    rows = []
    errors = []

    for i, src_path in enumerate(tqdm(paths, desc="Processing images"), 1):
        src = Path(src_path)
        oid = f"paw_{i:03d}"
        ext = ".jpg"
        dest_name = f"{oid}{ext}"
        dest = OBJ_DIR / dest_name

        if not src.exists():
            print(f"  WARNING: source not found, skipping — {src_path}")
            errors.append(src_path)
            continue

        # Detect if source has changed; if so, wipe stale derivatives
        changed = not dest.exists() or src.stat().st_size != dest.stat().st_size
        shutil.copy2(src, dest)
        if changed:
            for stale in [
                OBJ_DIR / "small" / f"{oid}_sm.jpg",
                OBJ_DIR / "thumbs" / f"{oid}_th.jpg",
            ]:
                stale.unlink(missing_ok=True)

        date = extract_date(src_path, src)
        time = extract_time(src)
        lat, lon = extract_gps(src)
        spotter = extract_spotter(src)
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

        obj_path   = f"/objects/{dest_name}"
        small_path = f"/objects/small/{oid}_sm.jpg"
        thumb_path = f"/objects/thumbs/{oid}_th.jpg"
        rows.append({
            "objectid": oid,
            "title": title,
            "date": date,
            "time": time,
            "description": "",
            "subject": "",
            "species": _read_species(src_path, annotation_map),
            "location": location,
            "country": country_name,
            "latitude": lat,
            "longitude": lon,
            "type": "Image",
            "format": "image/jpeg",
            "display_template": "image",
            "object_location": obj_path,
            "image_small": small_path,
            "image_thumb": thumb_path,
            "spotter": spotter,
            "source_file": src_path,
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

    print("Running rake generate_derivatives...")
    subprocess.run(["bundle", "exec", "rake", "generate_derivatives"], cwd=REPO_ROOT, check=True, shell=True)

    print("Deploying...")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(REPO_ROOT / "deploy.ps1")], cwd=REPO_ROOT, shell=True)


if __name__ == "__main__":
    main()
