"""Download cfbfastR season PBP assets for local CFB research.

Raw data is intentionally kept outside git. Use one or more seasons:
    python research/cfb/download_pbp.py 2024 2025
"""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfbfastR_cfb_pbp"

def download(season: int, out_dir: Path, force: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"play_by_play_{season}.parquet"
    if dest.exists() and not force:
        print(f"exists: {dest}")
        return dest
    url = f"{BASE}/play_by_play_{season}.parquet"
    print(f"downloading {season}: {url}")
    urlretrieve(url, dest)
    print(f"saved: {dest}")
    return dest

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("seasons", nargs="+", type=int)
    p.add_argument("--out-dir", default="runtime/cfb/raw")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    for season in args.seasons:
        if season < 2014:
            raise SystemExit("Classic cfbfastR PBP research starts at 2014.")
        download(season, Path(args.out_dir), args.force)

if __name__ == "__main__":
    main()
