"""ดาวน์โหลดสแกน 世德堂 1592 (PDF) จาก GitHub Release มาไว้ใน sources/

ไฟล์ PDF ใหญ่ 1.64 GB จึงไม่อยู่ใน Git (.gitignore) แต่แนบไว้ใน Release
แท็ก sources-scan-1592 ของ repo นี้ สคริปต์ใช้ `gh release download`
(ต้อง `gh auth login` ด้วยบัญชีที่มีสิทธิ์เข้า repo) แล้วตรวจ SHA-256

ใช้งาน:
    python -X utf8 tools/fetch_sources.py           # ดาวน์โหลดถ้ายังไม่มีหรือ hash ไม่ตรง
    python -X utf8 tools/fetch_sources.py --check   # ตรวจ hash ไฟล์ในเครื่องอย่างเดียว
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"

REPO = "pongcool/xiyouji"
TAG = "sources-scan-1592"
ASSET = "shidetang-1592-xiyouji-scan.pdf"
LOCAL_NAME = "新刻出像官板大字西游记.二十卷一百回.明.吴承恩撰.明万历二十年金陵世德堂刊本.灰度胶片.pdf"
SHA256 = "cb888f4321987f2e77b0c9aad07a4e1c61283511c86d356223aa4c204c932e19"
SIZE = 1_639_462_509  # ไบต์


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
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
    if shutil.which("gh") is None:
        sys.exit(
            "ไม่พบคำสั่ง gh — ติดตั้ง GitHub CLI แล้ว `gh auth login` "
            f"หรือดาวน์โหลด {ASSET} จาก https://github.com/{REPO}/releases/tag/{TAG} "
            f"มาวางที่ sources/ แล้วเปลี่ยนชื่อเป็น {LOCAL_NAME}"
        )
    part = SOURCES / (ASSET + ".part")
    part.unlink(missing_ok=True)
    print(f"ดาวน์โหลด {ASSET} (~{SIZE / 1e9:.2f} GB) จาก Release {TAG} …")
    subprocess.run(
        ["gh", "release", "download", TAG, "--repo", REPO,
         "--pattern", ASSET, "--output", str(part), "--clobber"],
        check=True,
    )
    digest = sha256_of(part)
    if digest != SHA256:
        part.unlink(missing_ok=True)
        sys.exit(f"hash ของไฟล์ที่ดาวน์โหลดไม่ตรง: {digest} — ลบไฟล์แล้ว ลองใหม่")
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
