"""ตรวจต้นฉบับซีโหยวจี้รายบทกับ manifest

python -X utf8 tools/prepare_xiyouji.py --check  ตรวจ hash หัวบท และจำนวนหน่วยครบ 100 บท
โค้ดแบ่งไฟล์เดิมเก็บไว้เป็นประวัติ ใช้ได้เมื่อมีไฟล์รวมเท่านั้น
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = re.compile(r"^[ \t\u3000]*第([〇○零一二三四五六七八九十百]+)回[^\r\n]*", re.M)
DIGITS = dict(zip("零〇○一二三四五六七八九", [0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]))


def number(value):
    if not any(c in value for c in "十百"):
        return int("".join(str(DIGITS[c]) for c in value))
    result, digit = 0, 0
    for c in value:
        if c in "十百":
            result += (digit or 1) * {"十": 10, "百": 100}[c]
            digit = 0
        else:
            digit = DIGITS[c]
    return result + digit


def source_units(text):
    """หนึ่งกลุ่มบรรทัดคั่นด้วยบรรทัดว่างเป็นหนึ่งหน่วย ไม่แยกบรรทัดพับคำ"""
    return [block.strip() for block in re.split(r"\n[^\S\n]*\n", text) if block.strip()]


def build():
    raw = (ROOT / "ไซอิ๋ว.txt").read_bytes()
    # แปลงเฉพาะ CRLF เป็น LF; hash ไฟล์ดิบยังเก็บแยกไว้
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    end = text.index("*** END OF THE PROJECT GUTENBERG EBOOK 西遊記 ***")
    matches = list(HEADER.finditer(text, 0, end))
    assert [number(m[1]) for m in matches] == list(range(1, 101)), "หัวบทไม่ครบ 001–100"
    outputs, entries = {}, []
    for i, match in enumerate(matches):
        num = i + 1
        stop = matches[i + 1].start() if i + 1 < len(matches) else end
        title = match[0].strip()
        body_start = match.end()
        title_lines = [text.count("\n", 0, match.start()) + 1]
        if num == 47:
            continuation = re.match(r"\s*木垂慈救小童(?=\n)", text[body_start:stop])
            assert continuation, "รูปหัวบท 047 เปลี่ยน ต้องตรวจด้วยตาก่อน"
            title += "　木垂慈救小童"
            body_start += continuation.end()
            title_lines.append(text.count("\n", 0, body_start) + 1)
        # เนื้อเรื่องเก็บทุกตัวอักษร รวมช่องว่างและบรรทัดว่างจากขอบเขตนี้
        body = text[body_start:stop]
        filename = f"{num:03d}.md"
        content = "# " + title + "\n" + body
        outputs[f"chapters/{filename}"] = content
        entries.append({
            "chapter": num, "path": f"chapters/{filename}", "title": title,
            "title_source_lines": title_lines,
            "body_start_line": text.count("\n", 0, body_start) + 1,
            "end_line_exclusive": text.count("\n", 0, stop) + 1,
            "units": len(source_units(body)),
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    manifest = {
        "source": "ไซอิ๋ว.txt", "source_sha256": hashlib.sha256(raw).hexdigest(),
        "edition": "Project Gutenberg eBook 23962 (metadata in supplied file)",
        "transformations": ["UTF-8 BOM removed if present; CRLF to LF",
                            "heading prefixed with #; leading heading whitespace removed",
                            "047: join separated title fragment 木垂慈救小童; no character correction",
                            "Gutenberg preamble and postamble excluded from chapters, retained in original"],
        "chapters": entries,
    }
    outputs["docs/SOURCE_MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return outputs, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (ROOT / "ไซอิ๋ว.txt").exists():
        if not args.check:
            parser.error("ใช้ต้นฉบับรายบทใน chapters/ แล้ว; ใช้ --check เพื่อตรวจกับ manifest")
        manifest = json.loads((ROOT / "docs/SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
        entries = manifest["chapters"]
        assert [e["chapter"] for e in entries] == list(range(1, 101)), "manifest ไม่ครบ 100 บท"
        expected = {ROOT / "chapters" / f"{n:03d}.md" for n in range(1, 101)}
        assert set((ROOT / "chapters").glob("*.md")) == expected, "ชุดไฟล์บทไม่ตรง manifest"
        for entry in entries:
            path = ROOT / "chapters" / f"{entry['chapter']:03d}.md"
            assert entry["path"] == path.relative_to(ROOT).as_posix(), "path ใน manifest ไม่ตรงบท"
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"], f"hash ไม่ตรง: {path.name}"
            heading, _, body = raw.decode("utf-8").partition("\n")
            assert heading == "# " + entry["title"], f"หัวบทไม่ตรง: {path.name}"
            assert len(source_units(body)) == entry["units"], f"จำนวนหน่วยไม่ตรง: {path.name}"
        print(f"ตรงกับ manifest ครบ 100 บท; {sum(e['units'] for e in entries)} หน่วยเทียบ (ไม่มีไฟล์รวมให้เทียบซ้ำ)")
        return
    outputs, manifest = build()
    expected = {ROOT / name for name in outputs if name.startswith("chapters/")}
    actual = set((ROOT / "chapters").glob("*.md"))
    if args.check:
        assert actual == expected, "ชุดไฟล์บทไม่ตรง manifest"
        for name, content in outputs.items():
            assert (ROOT / name).read_bytes() == content.encode("utf-8"), f"เนื้อหาไม่ตรง: {name}"
        print(f"ตรงกับต้นฉบับครบ 100 บท; {sum(e['units'] for e in manifest['chapters'])} หน่วยเทียบ")
    else:
        assert not actual, "มีต้นฉบับรายบทอยู่แล้ว ไม่เขียนทับ"
        assert not any((ROOT / name).exists() for name in outputs), "มีไฟล์ปลายทางอยู่แล้ว"
        for name, content in outputs.items():
            path = ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        print("สร้างต้นฉบับ 100 บทและ SOURCE_MANIFEST.json แล้ว")


if __name__ == "__main__":
    main()
