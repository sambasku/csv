#!/usr/bin/env python3
"""Parse sumber pasangan `<sambas> : <indonesia>` -> CSV impor (aturan csv/RULES.md).

Format input (lihat seksi "Varian input: pasangan" di csv/RULES.md):
  najor :                              -> lemma tanpa terjemahan (file terpisah)
  gulli : kelereng;                    -> satu baris (titik koma ujung dibuang)
  anginan : masuk angin; mood naik     -> dua baris, lemma sama
  geye, goye, giye : begitu            -> tiga lemma, arti sama
  entayap/intayap : keluyuran          -> dua lemma
  simpakl;simper : gombeng             -> dua lemma
  antang = anggan                      -> dua lemma tanpa terjemahan

Pakai:
  python3 csv/scripts/parse_pasangan_kata.py csv/a-23-10-2025.txt
  python3 csv/scripts/parse_pasangan_kata.py --selftest
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

CSV_DIR = Path(__file__).resolve().parent.parent
REQUIRED = "kata,terjemahan,penjelasan_arti,type,contoh,arti_contoh"
HEADER = REQUIRED.split(",")

# pemisah lemma Sambas: garis miring, koma, titik koma
LEMMA_SEP = re.compile(r"[/,;]")
# pemisah arti Indonesia: titik koma saja (garis miring di arti tidak dipecah)
ARTI_SEP = ";"
WS = re.compile(r"\s+")


def clean(s: str) -> str:
    return WS.sub(" ", s).strip()


def cap(s: str) -> str:
    """Huruf pertama kapital, sisanya apa adanya (`TEBIRRONG` -> `Tebirrong`)."""
    return s[:1].upper() + s[1:].lower() if s.isupper() else s[:1].upper() + s[1:]


def parse_line(raw: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Satu baris sumber -> (rows [(kata, terjemahan)], lemma tanpa terjemahan)."""
    line = raw.strip()
    if not line:
        return [], []

    if "=" in line and (":" not in line or line.index("=") < line.index(":")):
        # `<sambas> = <sambas>`: dua lemma, tanpa arti
        lemmas = [cap(clean(p)) for p in re.split(r"[=/,;]", line) if clean(p)]
        return [], lemmas

    if ":" not in line:
        return [], [cap(clean(line))]

    kiri, kanan = line.split(":", 1)
    lemmas = [cap(clean(p)) for p in LEMMA_SEP.split(kiri) if clean(p)]
    artis = [clean(p) for p in kanan.split(ARTI_SEP) if clean(p)]
    if not lemmas:
        return [], []
    if not artis:
        return [], lemmas
    return [(k, a) for k in lemmas for a in artis], []


def next_number(out_dir: Path) -> str:
    nums = [int(m.group(1)) for p in out_dir.glob("[0-9][0-9][0-9]-*.csv") if (m := re.match(r"(\d{3})-", p.name))]
    return f"{(max(nums) if nums else 0) + 1:03d}"


def build(src: Path) -> tuple[list[tuple[str, str]], list[tuple[int, str]], list[str]]:
    rows: list[tuple[str, str]] = []
    missing: list[tuple[int, str]] = []
    notes: list[str] = []
    for no, raw in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        data, tanpa = parse_line(raw)
        rows.extend(data)
        missing.extend((no, kata) for kata in tanpa)
        if "...." in raw:
            notes.append(f"baris {no}: definisi terpotong di sumber -> {raw.strip()!r}")
        if raw.count(":") > 1 and "=" not in raw:
            notes.append(f"baris {no}: titik dua ganda, dipertahankan utuh -> {raw.strip()!r}")
    return rows, missing, notes


def write_csv(rows: list[tuple[str, str]], out: Path, title: str, url: str) -> None:
    with out.open("w", encoding="utf-8", newline="") as f:
        f.write("# @format sambasku-dictionary\n")
        f.write("# @version 2\n")
        f.write("# @encoding UTF-8\n")
        f.write("# @separator ,\n")
        f.write(f"# @title {title}\n")
        f.write(f"# @url {url}\n")
        f.write(f"# @required {REQUIRED}\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for kata, arti in rows:
            w.writerow([kata, arti, "", "", "", ""])


def write_missing(missing: list[tuple[int, str]], out: Path) -> None:
    lines = [f"{no}\t{kata}" for no, kata in missing]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def selftest() -> None:
    assert parse_line("najor :") == ([], ["Najor"])
    assert parse_line("TEBIRRONG : wajah mencong") == ([("Tebirrong", "wajah mencong")], [])
    assert parse_line("gulli : kelereng;") == ([("Gulli", "kelereng")], [])
    assert parse_line("anginan : masuk angin; mood, yang berubah-ubah; plin plan") == (
        [
            ("Anginan", "masuk angin"),
            ("Anginan", "mood, yang berubah-ubah"),
            ("Anginan", "plin plan"),
        ],
        [],
    )
    assert parse_line("geye, goye, giye : begitu") == (
        [("Geye", "begitu"), ("Goye", "begitu"), ("Giye", "begitu")],
        [],
    )
    assert parse_line("entayap/intayap : keluyuran") == (
        [("Entayap", "keluyuran"), ("Intayap", "keluyuran")],
        [],
    )
    assert parse_line("simpakl;simper : gombeng") == (
        [("Simpakl", "gombeng"), ("Simper", "gombeng")],
        [],
    )
    assert parse_line("jannat : almarhum/almarhumah") == ([("Jannat", "almarhum/almarhumah")], [])
    assert parse_line("antang = anggan") == ([], ["Antang", "Anggan"])
    assert parse_line("andang dah : suatu ungkapan yang bermakna : memang seperti itu") == (
        [("Andang dah", "suatu ungkapan yang bermakna : memang seperti itu")],
        [],
    )
    assert parse_line("   ") == ([], [])
    print("selftest ok")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--selftest"]
    if "--selftest" in sys.argv:
        selftest()
        return
    if not args:
        sys.exit("pakai: parse_pasangan_kata.py <file-sumber.txt> [--title T] [--url U]")

    src = Path(args[0])
    title = sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv else src.stem
    url = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "sambasku.com"

    rows, missing, notes = build(src)
    out = CSV_DIR / f"{next_number(CSV_DIR)}-{src.stem}:{url}.csv"
    lost = CSV_DIR / f"{src.stem}:tanpa-terjemahan.txt"
    write_csv(rows, out, title, url)
    write_missing(missing, lost)

    print(f"rows={len(rows)} tanpa_terjemahan={len(missing)}")
    print(f"out={out}")
    print(f"missing={lost}")
    for note in notes:
        print(f"catatan: {note}")


if __name__ == "__main__":
    main()
