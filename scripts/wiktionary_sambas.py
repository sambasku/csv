#!/usr/bin/env python3
"""Generate CSV batch import dari dump lokal id.wiktionary (Melayu Sambas).

Sumber : csv/source/wiktionary-raw/  (pages_*.json + titles.json, API id.wiktionary.org,
         kategori "WikiTutur 2.0 - Melayu Sambas")
Output : csv/<NNN>-wiktionary:id.wiktionary.org.csv  (aturan csv/RULES.md)

Entri diambil dari seksi =={{bahasa|ms}}== per halaman; definisi diikutkan bila
berlabel Sambas ({{sambas}} / {{label|ms|...Sambas...}}) atau bila seksi ms
memiliki penanda audio Sambas ({{a|Sambas}} / q=Sambas). Definisi berlabel
dialek lain (mis. {{kepri}}) dibuang.

Jalankan ulang setelah dump diperbarui: python3 csv/scripts/wiktionary_sambas.py
"""

import csv
import datetime
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "source", "wiktionary-raw")
OUT_DIR = os.path.join(HERE, "..")

POS_LABEL = {
    "n": "kata benda (kb)",
    "v": "kata kerja (kk)",
    "adj": "kata sifat (ks)",
    "adv": "kata keterangan",
    "pron": "kata ganti",
    "prep": "kata depan",
    "conj": "kata hubung",
}
POS_RE = re.compile(r"^\{\{-([a-z]+)-\|(?:ms)\}\}", re.M)


def ms_section(wikitext):
    parts = wikitext.split("=={{bahasa|ms}}==")
    if len(parts) < 2:
        return None
    tail = parts[1]
    nxt = re.search(r"\n==(?!=)", tail)
    return tail[: nxt.start()] if nxt else tail


def clean(text):
    """Wikitext inline -> teks polos."""
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)  # [[x|y]] -> y
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)  # [[x]] -> x
    text = re.sub(r"\{\{ragam dari\|\w+\|([^}|]+)[^}]*\}\}", r"ragam dari \1", text)
    text = re.sub(r"\{\{l\|\w+\|([^}|]+)[^}]*\}\}", r"\1", text)  # {{l|id|x}} -> x
    text = re.sub(r"\{\{[^}]*\}\}", "", text)  # template sisanya dibuang
    text = text.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip(" ;.")


def has_sambas_marker(ms):
    return bool(
        re.search(r"\{\{a\|Sambas\}\}", ms) or re.search(r"q=+'{0,2}Sambas", ms)
    )


def parse_page(wikitext):
    """-> list of (pos_key, [terjemahan...], contoh) atau None bila bukan entri Sambas."""
    ms = ms_section(wikitext)
    if ms is None:
        return None
    marker = has_sambas_marker(ms)
    out = []
    contoh = ""
    for pm in POS_RE.finditer(ms):
        chunk = ms[pm.end():]
        nxt = POS_RE.search(chunk)
        chunk = chunk[: nxt.start()] if nxt else chunk
        senses = []
        lines = chunk.splitlines()
        for i, line in enumerate(lines):
            if not re.match(r"^#\s", line):
                continue
            m = re.match(r"^#\s*(\(\s*(?:\{\{[^}]+\}\}\s*,?\s*)+\))?\s*(.*)$", line)
            label, body = m.group(1) or "", m.group(2)
            labeled_sambas = "{{sambas}}" in label.lower() or re.search(
                r"\{\{label\|\w+\|[^}]*Sambas", body, re.I
            )
            if not (labeled_sambas or (marker and not label)):
                continue  # def berlabel dialek lain, atau tanpa label & tanpa penanda Sambas
            text = clean(body)
            # contoh: baris #: berikutnya + terjemahan #:: (sekali saja untuk halaman)
            if (
                not contoh
                and i + 1 < len(lines)
                and re.match(r"^#:\s*\S", lines[i + 1])
                and not re.match(r"^#:\s*\{\{(syn|ant)", lines[i + 1])  # anotasi sinonim/antonim
            ):
                ex = clean(lines[i + 1][2:])
                tr = ""
                if i + 2 < len(lines) and lines[i + 2].startswith("#::"):
                    tr = clean(lines[i + 2][3:])
                contoh = f"'{ex}' ({tr})" if ex else ""
            if text:
                senses.append(text)
        if senses:
            out.append((pm.group(1), senses))
    return out or None, contoh


def main():
    titles = json.load(open(os.path.join(RAW, "titles.json")))
    pages = {}
    for f in sorted(glob.glob(os.path.join(RAW, "pages_*.json"))):
        for p in json.load(open(f)):
            pages[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]

    rows, skipped = [], []
    for t in titles:
        result = parse_page(pages[t])
        if not result or not result[0]:
            skipped.append(t)
            continue
        pos_list, contoh = result
        terjemahan = "; ".join(s for _, senses in pos_list for s in senses)
        penjelasan = "; ".join(POS_LABEL.get(pos, pos) for pos, _ in pos_list)
        rows.append([t[:1].upper() + t[1:], terjemahan, penjelasan, contoh])

    # nomor batch berikutnya
    nums = [
        int(os.path.basename(f)[:3])
        for f in glob.glob(os.path.join(OUT_DIR, "[0-9][0-9][0-9]-*.csv"))
    ]
    nnn = max(nums, default=0) + 1
    out_path = os.path.join(OUT_DIR, f"{nnn:03d}-wiktionary:id.wiktionary.org.csv")

    dump_date = datetime.date.fromtimestamp(
        os.path.getmtime(os.path.join(RAW, "titles.json"))
    ).isoformat()
    header = [
        "# @format sambasku-dictionary",
        "# @version 1",
        "# @encoding UTF-8",
        "# @separator ,",
        "# @title Wiktionary",
        "# @url id.wiktionary.org",
        "# @required kata,terjemahan,penjelasan_arti,contoh",
        f"# Sumber: id.wiktionary.org, Kategori:WikiTutur 2.0 - Melayu Sambas (dump {dump_date})",
        f"# {len(rows)} entri; dilewati (tanpa data Sambas): {', '.join(skipped) or '-'}",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n")
        w = csv.writer(fh)
        w.writerow(["kata", "terjemahan", "penjelasan_arti", "contoh"])
        w.writerows(rows)

    # validasi: setiap baris data tepat 4 kolom
    with open(out_path, encoding="utf-8") as fh:
        data = [r for r in csv.reader(l for l in fh if not l.startswith("#"))]
    assert data[0] == ["kata", "terjemahan", "penjelasan_arti", "contoh"]
    assert all(len(r) == 4 for r in data), "ada baris dengan jumlah kolom != 4"
    empty = sum(1 for r in data[1:] if not r[1])
    print(f"{out_path}: {len(data) - 1} baris data, {empty} terjemahan kosong")
    print("dilewati:", ", ".join(skipped) or "-")


if __name__ == "__main__":
    main()
