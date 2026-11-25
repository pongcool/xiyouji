"""ดาวน์โหลดสแกน 世德堂 1592 (PDF) จาก GitHub Release มาไว้ใน sources/

ไฟล์ PDF ใหญ่ 1.64 GB จึงไม่อยู่ใน Git (.gitignore) แต่แนบไว้ใน Release
แท็ก sources-scan-1592 ของ repo นี้ สคริปต์ดาวน์โหลดผ่าน HTTPS
(ไม่ต้องติดตั้งหรือล็อกอินอะไร) แล้วตรวจ SHA-256

ใช้งาน:
    python -X utf8 tools/fetch_sources.py           # ดาวน์โหลดถ้ายังไม่มีหรือ hash ไม่ตรง
    python -X utf8 tools/fetch_sources.py --check   # ตรวจ hash ไฟล์ในเครื่องอย่างเดียว
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"

TAG = "sources-scan-1592"
ASSET = "shidetang-1592-xiyouji-scan.pdf"
URL = f"https://github.com/pongcool/xiyouji/releases/download/{TAG}/{ASSET}"
LOCAL_NAME = "新刻出像官板大字西游记.二十卷一百回.明.吴承恩撰.明万历二十年金陵世德堂刊本.灰度胶片.pdf"
SHA256 = "cb888f4321987f2e77b0c9aad07a4e1c61283511c86d356223aa4c204c932e19"
SIZE = 1_639_462_509  # ไบต์
CHUNK = 8 * 1024 * 1024


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def check(path: Path) -> bool:
    if not path.exists():
        print(f"ไม่พบ {path.relative_to(ROOT)}")
        return False
    print(f"กำลังตรวจ SHA-256 ของ {path.name} …")
    digest = sha256_of(path)
    if digest != SHA256:
        print(f"hash ไม่ตรง: {digest} (ต้องเป็น {SHA256})")
        return False
    print("hash ตรง ไฟล์พร้อมใช้")
    return True


def download(target: Path) -> None:
    part = SOURCES / (ASSET + ".part")
    print(f"ดาวน์โหลด {URL} (~{SIZE / 1e9:.2f} GB) …")
    h = hashlib.sha256()
    done = 0
    try:
        with urllib.request.urlopen(URL) as resp, part.open("wb") as out:
            for chunk in iter(lambda: resp.read(CHUNK), b""):
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                print(f"\r  {done / 1e6:,.0f} / {SIZE / 1e6:,.0f} MB", end="", flush=True)
        print()
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    if h.hexdigest() != SHA256:
        part.unlink(missing_ok=True)
        sys.exit(f"hash ของไฟล์ที่ดาวน์โหลดไม่ตรง: {h.hexdigest()} — ลบไฟล์แล้ว ลองใหม่")
    part.replace(target)
    print(f"บันทึกเป็น sources/{LOCAL_NAME} hash ตรงแล้ว")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="ตรวจ hash อย่างเดียว ไม่ดาวน์โหลด")
    args = ap.parse_args()

    target = SOURCES / LOCAL_NAME
    if args.check:
        sys.exit(0 if check(target) else 1)
    if target.exists() and check(target):
        return
    SOURCES.mkdir(exist_ok=True)
    download(target)


if __name__ == "__main__":
    main()
