#!/usr/bin/env python3
"""Parse OCR text KAMUS DAN ENSIKLOPEDIA MELAYU SAMBAS -> CSV 007.

Forward (p13-118):  <lemma> = <terjemahan> = <english>   (english dibuang)
Reverse (p163-230): <english> = <terjemahan> = <lemma>   (dibalik)
Baris tanpa '=' = lanjutan terjemahan entri aktif.

Pakai: python3 parse_kamus_ensiklopedia.py [--selftest]
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

CSV_DIR = Path(__file__).resolve().parent.parent
OCR_DIR = CSV_DIR / ".ocr" / "text"
OUT = CSV_DIR / "007-kamus-dan-ensiklopedia-melayu-sambas:ocr-clean.csv"

FORWARD = range(13, 119)
REVERSE = range(163, 231)

# OCR salah baca permanen (tak terbaca bahkan 400dpi): lemma garbage -> benaran.
# key = lemma garbage persis, value = lemma benar.
# "sel'" ambigu: forward "Sela' = Sila" (p-099) vs reverse "sel', pippe" = lipat
# paha (p-190). Keduanya sah; biarkan reverse jadi "Sel'" agar tak collide dedupe.
OCR_FIXES = {
    "buras aaa": "Gesek",
    "if ae": "kissai",
    "didi": "Aro'",
    "ida adl": "Untong",
    "ryddu": "Ruddu",
    "roval": "Royal",
    "rovah": "Royah",
    "sontok": "Sontoh",  # OCR k/h: user konfirmasi lemma "Sontoh"
}

# entri yang definisinya tak mungkin dipulihkan dari stream OCR (kontinuasi
# tercampur noise margin); paksa nilai final. key = norm_lemma.
TERJ_OVERRIDES = {
    "tiong": "Tiung/nama burung yg bisa bicara",
    "reli": "Sepeda raleigh buatan Inggeris merupakan sepeda termewah dan termahal dizamannya :",
    "ruddu": "Maju terus",
    "sontoh": "Dalam keadaan sulit baik keuangan maupun lainnya",  # raw split "ke" + "uangan"
}

# perbaikan baris OCR persis (setelah normalisasi kutip): substring -> pengganti.
OCR_LINE_FIXES = {
    "Afloat - terapung -.ngapong": "Afloat = terapung = ngapong",  # "-." = "=" salah baca
    "Tibroseke ~ Tipiliyok": "Tipiliyok",  # "Tibroseke ~" noise margin; tanpa ini "Seleo" nempel ke Tiperedok
    "kutu. <p Ulu ile'": "Ulu ile'",  # tanpa ini "Hilir mudik" nempel ke Ullu
}

# noise OCR umum di margin/garis tabel
NOISE = re.compile(r"^[|\u00ab/\s_\-\.~\u2013\u2014]+|[|\u00ab_~]+$")

# entri tak terpulihkan dari OCR (terj/lemma murni garbage) - hapus total.
DELETE_LEMMAS = {"by lean", "bigge' lakum", "menvapa", "pippe"}  # "pippe" = noise OCR "Groin = ... = sel', pippe"

# fragmen baris = entri kolom-geser tak terpulihkan ("Ar umat - ble Unte = Unta :"):
# lemma & terj dua-duanya rusak, skip sebelum parse agar tak nyasar ke entri lain.
DELETE_LINE_SUBSTR = {"ar umat", "betapaman-"}

# lemma yang harusnya ambil terjemahan kolom reverse, bukan forward
# (batch 4: "Afloat = terapung = ngapong, timbol" -> timbol = terapung).
REVERSE_WINS = {"timbol"}
# terjemahan murni bahasa English di kolom tengah -> padanan Indonesia.
# (kolom Indonesia hilang/tertimpa OCR, tersisa kolom English)
ENG_TERJ = {
    "slap at mouth": "Tampar mulut",
    "extinguish": "Padam",
    "lie, untrue": "Bohong",
    "the": "Teh",  # "Tea = the = atteh": mid asli "teh" kebaca "the"
    "crowded": "Padat",
    "trunk": "Belalai",
    "idiot": "Bodoh",
    "crazy": "Gila",
    "asleep": "Tertidur",
    "chatting": "Mengobrol",
    "swollen": "Bengkak",
    "invite": "Mengundang",
    "dissatisfied": "Kecewa",
    "payment": "Pembayaran",
    "scramble": "Diremas",
    "disorder": "Tidak beraturan",
    "went. varo'": "Goreng tanpa minyak",  # kolom geser OCR: "DIDI - went. VAro' = goreng tanpa minyak"
    "usut, mengusut": "Usut; mengusut",
    "too old": "",  # "Uzzor ae a || ne = too old" = entri kolom-geser rusak, buang
}
# kata Indonesia yang kebetulan masuk wordlist English - jangan di-strip dari ekor.
ID_WORDS = {
    "air", "lima", "sen", "galah", "dari", "orang", "enam", "tua", "masa", "allah",
    "apa", "lain", "kali", "dan", "di", "yang", "ada", "nama", "badan", "mata",
    "kopi", "ember", "atap",
}
ENTRY = re.compile(r"^(?P<left>[^=]+?)\s*=\s*(?P<mid>[^=]*?)(?:\s*=\s*(?P<right>.+?))?\s*$")


def clean_line(raw: str) -> str:
    line = raw.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    for k, v in OCR_LINE_FIXES.items():
        line = line.replace(k, v)
    line = line.replace("\u00bb", "")  # guillemet = noise scan
    line = NOISE.sub("", line.strip())
    return re.sub(r"\s{2,}", " ", line).strip()


JUNK_PREFIX = re.compile(r"^(?:\d+|[^A-Za-z0-9]+)(?=\s)")  # digit/noise non-alfanumerik di awal

_ENG_WORDS: set[str] | None = None


def eng_words() -> set[str]:
    # /usr/share/dict/words = wordlist English macOS. ponytail: ceiling =
    # kata Indonesia yang kebetulan english (air, mata) - mitigasi rasio 70%.
    global _ENG_WORDS
    if _ENG_WORDS is None:
        try:
            _ENG_WORDS = {w.strip().lower() for w in open("/usr/share/dict/words") if w.strip()}
        except OSError:
            _ENG_WORDS = set()
    return _ENG_WORDS


def is_english_fragment(line: str) -> bool:
    words = re.findall(r"[A-Za-z]{2,}", line)
    if len(words) < 2:
        return False
    eng = eng_words()
    if not eng:
        return False
    hits = sum(1 for w in words if w.lower() in eng)
    return hits / len(words) >= 0.7


JUNK_TOKENS = {"err", "myon", "es", "cekb", "aa", "nylon", "ts", "ss"}


def strip_junk_prefix(lemma: str) -> str:
    # buang noise OCR di awal lemma: digit/simbol, token blacklist, huruf tunggal,
    # dan token pendek (<=3) non-kapital diikuti kata berkapital = centang margin
    # scan (vy Boksen, wv leca', ae Karrat). Compound asli dicegah: hanya strip
    # bila token noise + token BERIKUTNYA berawalan kapital; kata kedua compound
    # asli selalu lowercase (ae rakse, ne uwan, ma iyong).
    # ponytail: blacklist manual; ceiling = token noise baru, upgrade = review + tambah.
    # tanda kutip ganda nyangkut di lemma selalu noise scan (apostrof asli pakai ' tunggal,
    # mis. "Bigge'"); tanpa dibuang di sini, lemma jadi invalid -> terjemahan nyasar ke
    # entri sebelumnya (bug "Birawe \"" / "Inda\"" bikin terj numpuk di entri sebelum).
    lemma = lemma.replace('"', "").strip()
    lemma = JUNK_PREFIX.sub("", lemma).strip()
    # tanda baca noise nyangkut di ekor lemma ("Cammas ;")
    lemma = lemma.strip(",;:").strip()
    # sisa simbol/digit/koma di awal ("1, Bedangngam", ", ,/Kuwai", ",/ Belampum")
    lemma = re.sub(r"^[^A-Za-z']+", "", lemma)
    # huruf noise nempel di depan kata: "vLullongan", "uBelinsa'", "VLullongan"
    lemma = re.sub(r"^(?:[a-z](?=[A-Z])|[A-Z](?=[A-Z][a-z]))", "", lemma)
    # token simbol murni ("|", "<") di antara noise prefix: buang dulu agar rule
    # token-caps di bawah lihat tetangga sebenarnya ("Pd | OA Ullut")
    parts = [p for p in lemma.split() if re.search(r"[A-Za-z0-9]", p)]
    # token caps 2-3 huruf + kata kapital = centang margin: "UI Killan", "KY Masjid", "VY Baddap"
    while len(parts) > 1 and re.fullmatch(r"[A-Z]{2,3}", parts[0]) and parts[1][:1].isupper():
        parts = parts[1:]
    # token mixed-case pendek ("Pd", "Ie") di depan kata kapital = noise margin
    while len(parts) > 1 and re.fullmatch(r"[A-Z][a-z]", parts[0]) and parts[1][:1].isupper():
        parts = parts[1:]
    # run noise multi-token di depan token kapital penuh: "Ippo Kf Ky Tipacul",
    # "ef to ren L Tiperedok" -> semua token pendek (<=4) sebelum token kapital
    # berlen >=5 = noise margin, buang. Lemma sah tak pernah berupa run pendek
    # + kata kapital (compound asli: "Napsu makan", "Ulu ile'" tak tertipu:
    # head-nya sendiri token panjang).
    for i, p in enumerate(parts):
        if len(p) >= 5 and p[:1].isupper():
            if i > 0 and all(len(q) <= 4 for q in parts[:i]) and parts[0].lower() not in {"di", "ka", "ke", "ta"}:
                parts = parts[i:]
            break
    while len(parts) > 1:
        head = parts[0].strip(".,|(")
        # run 2 token pendek noise + kata kapital: "OE ep Belacan", "Ie y Keminting"
        if len(parts) >= 3 and len(head) <= 3 and len(parts[1]) <= 3 and parts[2][:1].isupper():
            parts = parts[2:]
            continue
        if head.lower() in JUNK_TOKENS or re.fullmatch(r"[A-Za-z]|\d", head):
            parts = parts[1:]
            continue
        if (
            re.fullmatch(r"[a-z]{1,3}|[A-Za-z][a-z]([a-z])?", head)
            and head not in {"di", "ka", "ke", "ta"}
            and parts[1][0].isupper()
        ):
            parts = parts[1:]
            continue
        break
    lemma = " ".join(parts)
    # sisa lemma English pendek = OCR noise (mis. "Bar" dari "Myon bar"), buang
    if lemma.lower() in eng_words() and len(lemma) <= 3:
        return ""
    # comma mid-lemma: "ly lod, feng killas" -> "killas" (koma = pembatas 2 entri
    # OCR yang nyatu; lemma asli tak mengandung koma)
    if "," in lemma:
        tail = lemma.split(",")[-1].strip()
        ttoks = tail.split()
        while len(ttoks) > 1 and ttoks[0].islower() and len(ttoks[0]) <= 4:
            ttoks = ttoks[1:]
        if ttoks:
            lemma = " ".join(ttoks)
    toks = lemma.split()
    # token 1 huruf di tengah: "Mbulla' z Bohong" -> "Mbulla' Bohong"
    if len(toks) > 2:
        toks = [t for i, t in enumerate(toks) if not (0 < i < len(toks) - 1 and re.fullmatch(r"[A-Za-z]", t))]
        lemma = " ".join(toks)
    # suffix noise OCR: token <=2 char, atau <=3 char tanpa vokal
    # ("Cundong ity", "Dare i"); compound asli token terakhir selalu bervokal
    toks = lemma.split()
    if len(toks) > 1:
        last = toks[-1]
        if len(last) <= 2 or (len(last) == 3 and not re.search(r"[aeiou]", last.lower())):
            lemma = " ".join(toks[:-1])
    return lemma


def normalize_seps(line: str) -> str:
    """OCR sering salah baca '=' sebagai '-'. Bila total pemisah ' - ' + ' = '
    >= 2, anggap ' - ' juga pemisah kolom. ponytail: ceiling = terjemahan yang
    memang memakai ' - ' bisa salah konversi; jarang di kamus ini."""
    if " - " in line and line.count(" - ") + line.count(" = ") >= 2:
        return line.replace(" - ", " = ")
    return line


def strip_eng_tail(s: str) -> str:
    """Buang ekor kolom English yang bocor ke kolom Indonesia
    ("...kedua belah tangan palm hand", "...kemampuan. his ability !").
    Hanya strip bila >=2 token English berurutan di akhir DAN sisanya masih
    >=2 token. Blocklist = kata Indonesia yang kebetulan masuk wordlist English,
    strip berhenti sebelum kata itu.
    ponytail: ceiling = ekor English 1 token tidak terdeteksi; upgrade = daftar manual."""
    eng = eng_words()
    if not eng:
        return s
    toks = s.split()
    i = len(toks)
    while i > 0:
        w = toks[i - 1].strip(".,;!|'\"").lower()
        if w == "" or (w in eng and w not in ID_WORDS):
            i -= 1
        else:
            break
    if len(toks) - i >= 2 and i >= 1:
        return " ".join(toks[:i]).rstrip(" ,;-.|")
    return s


def clean_terj(s: str) -> str:
    s = s.replace("\u2014", "-").replace("\u2013", "-").replace("\u00bb", "").strip().strip(" ,;-").strip()
    s = ENG_TERJ.get(s.lower(), s)
    # noise simbol scan: "Bilas © Mereka Fi" -> "Bilas", "(Cair |" -> "Cair"
    s = re.split(r"\s*[\u00a9\u00ae\u2122]\s*", s)[0].strip()
    if s.count("(") != s.count(")"):  # kurung tak seimbang = artefak OCR
        s = s.replace("(", "").replace(")", "").strip()
    s = s.replace("|", " ")
    # titik orphan di tengah ("tidak . sesuai") + di ekor ("Usut, mengusut .")
    s = re.sub(r"\s+\.\s+", " ", s)
    s = re.sub(r"\s*\.\s*$", "", s)
    # leak kolom English bertanda kutip-digit ("Ayah "2 father") -> buang dari penanda ke akhir
    s = re.split(r'"\s*\d', s)[0].strip()
    # noise marker scan: "_", "*", "~", kutip ganda
    # ("Katak _", "Memerah *", "Cemas \"")
    s = re.sub(r"\s*[_*~\"]+", " ", s)
    # digit noise sendirian di ekor ("tidak pasti 5", "kolam 5")
    s = re.sub(r"\s\b\d+\b\s*$", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;-.|").strip()
    s = strip_eng_tail(s)
    # buang trailing OCR noise pendek: "kasar ry . i" -> "kasar",
    # "selubbong, selebong "3 sar ee" -> "selubbong, selebong"
    while True:
        m = re.search(r"\s+([A-Za-z]{1,2}|ry|sar|ee|EA)\s*[.]?\s*$", s)
        if not m:
            break
        s = s[: m.start()].rstrip(" ,;-\"|")
    s = ENG_TERJ.get(s.lower(), s)  # lookup kedua: pasca-simbol dibersihkan ("Usut, mengusut .")
    return s


def clean_lemma_side(s: str) -> str:
    """Kolom lemma reverse: ambil token berurutan yang valid di awal, buang
    trailing noise (':', 'EA "3', '|', 'TEA', 'goed', 'P3.'). ponytail:
    ceiling = lemma asli yang mengandung digit (tidak ada di sambas)."""
    out = []
    for tok in s.split():
        tok = tok.strip("|:,;\"")
        if not tok:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", tok):
            # token English/glue yang nempel di ekor kolom lemma reverse
            if out and tok.lower() in {"tea", "goed", "snl", "ane", "me", "ee", "eae", "p3", "pa", "aa", "sta", "he"}:
                break
            out.append(tok)
        elif out:  # token noise setelah token valid = berhenti
            break
    lemma = " ".join(out)
    # suffix noise OCR 3-char khusus yang lolos rule vokal
    if lemma.split()[-1:] and lemma.split()[-1].lower() in {"ity", "ahs", "sar", "eae"} and len(lemma.split()) > 1:
        lemma = " ".join(lemma.split()[:-1])
    return lemma


def valid_lemma(s: str) -> bool:
    # lemma sambas: huruf + apostrof + hyphen; bukan angka/murni noise OCR
    return bool(s) and len(s) <= 40 and re.match(r"^[A-Za-z][A-Za-z'\- ]*$", s) and not re.match(r"^[a-z]{1,2}$", s)


def looks_wordy(s: str) -> bool:
    """Terjemahan valid: ada huruf, bukan fragment noise."""
    return bool(s) and re.search(r"[A-Za-z]{2,}", s) and len(s) >= 3


def parse_page(text: str, reverse: bool):
    """Yield (lemma, terjemahan) dari satu halaman."""
    current = None  # [lemma, terjemahan]

    def flush():
        nonlocal current
        if current:
            current[1] = clean_terj(current[1])  # continuation belum dibersihkan
            current[1] = TERJ_OVERRIDES.get(norm_lemma(current[0]), current[1])  # terj rusak permanen -> paksa final
        if current and valid_lemma(current[0]) and looks_wordy(current[1]):
            yield current[0], current[1]
        current = None

    for raw in text.splitlines():
        line = clean_line(raw)
        if not line or len(line) < 3:
            continue
        line = normalize_seps(line)
        # baris kolom-geser rusak total: skip (jangan sampai jadi continuation)
        if any(sub in line.lower() for sub in DELETE_LINE_SUBSTR):
            continue
        # "=" nggantung di ekor ("Ngareh = Mencari sesuatu diantara ="):
        # kolom English kosong; strip agar jadi entri 2-kolom sah, bukan
        # continuation yang nyasar ke entri sebelumnya
        line = re.sub(r"=\s*$", "", line).rstrip()
        if line.startswith("="):
            # baris lanjutan sense: "= Tetapi = but ahs" -> kolom LEFT (sebelum
            # '=' kedua) = terjemahan Indonesia; kolom mid = english, dibuang
            if current:
                m2 = ENTRY.match(line[1:].strip())
                t = clean_terj((m2 and m2.group("left")) or "") if m2 else ""
                if t and not is_english_fragment(t):
                    current[1] += "; " + t
            continue
        m = ENTRY.match(line)
        if m:
            left, mid, right = m.group("left"), m.group("mid"), m.group("right")
            if reverse:
                if not right:  # tanpa kolom-3 = bukan entri reverse utuh, skip
                    continue
                lemmas = [strip_junk_prefix(clean_lemma_side(x)) for x in right.split(",")]
                terjs = [clean_terj(x) for x in mid.split(",")]
                lemmas = [l for l in lemmas if l]
                terjs = [t for t in terjs if t]
                if not lemmas or not terjs:
                    continue
                if len(lemmas) != 1 or len(terjs) != 1:
                    # "a = b1, b2 = c1, c2" -> pasangan per posisi (b1=c1, b2=c2);
                    # lemma lebih banyak -> semua dapat terj terakhir; terj lebih
                    # banyak -> sisa digabung ke lemma terakhir dgn "; "
                    if len(lemmas) > 1:
                        pairs = [(l, terjs[i] if i < len(terjs) else terjs[-1]) for i, l in enumerate(lemmas)]
                        if len(terjs) > len(lemmas):
                            l, t = pairs[-1]
                            pairs[-1] = (l, "; ".join([t] + terjs[len(lemmas):]))
                        yield from flush()  # jangan injak entri pending (mampu) dengan yield loop di bawah
                        for l, t in pairs[:-1]:
                            if valid_lemma(l) and looks_wordy(t):
                                yield l, t
                        lemma, terj = pairs[-1]
                    else:
                        lemma, terj = lemmas[0] if lemmas else "", "; ".join(terjs)
                else:
                    lemma, terj = strip_junk_prefix(clean_lemma_side(right)), clean_terj(mid)
            else:
                lemma, terj = strip_junk_prefix(OCR_FIXES.get(left.strip().lower(), left.strip())), clean_terj(mid)
            lemma = OCR_FIXES.get(lemma, OCR_FIXES.get(lemma.lower(), lemma))
            if not lemma:  # lemma musnah oleh strip noise = baris rusak, buang
                continue
            if norm_lemma(lemma) in DELETE_LEMMAS:  # tak terpulihkan: tutup entri aktif, buang
                yield from flush()
                continue
            if valid_lemma(lemma) and looks_wordy(terj):
                yield from flush()
                current = [lemma, terj]
            elif current and looks_wordy(terj) and not valid_lemma(lemma) and lemma:
                # sense tambahan milik entri aktif (lemma invalid = OCR noise);
                # lemma kosong = entri gagal, jangan tempel ke entri sebelumnya
                current[1] += "; " + terj
            else:
                continue
        else:
            # baris tanpa '=': lanjutan terjemahan; wajib ada kata >=3 huruf
            # (footer noise "ry . i" gagal sini); buang fragment English
            # noise margin: huruf/simbol tunggal di depan ("i sesuai", "$ bergantungan"), kutip/dash di ekor
            line = re.sub(r"\s+['\-]+$", "", re.sub(r"^[^A-Za-z]+[A-Za-z]?\s+|^[A-Za-z]\s+", "", line))
            # continuation 1-3 token murni English ("temper P ;", "his ability !")
            # = ekor kolom English yang patah ke baris baru, bukan terjemahan
            toks_l = [t for t in line.split() if re.search(r"[A-Za-z]", t)]
            if 0 < len(toks_l) <= 3 and all(
                t.strip(".,;!'\"|").lower() in eng_words() for t in toks_l if len(t.strip(".,;!'\"|")) > 1
            ):
                continue
            # continuation 1 token pendek non-kamus ("snl") = noise scan
            if len(toks_l) == 1 and len(toks_l[0]) <= 3 and toks_l[0].strip(".,;!'\"|").lower() not in eng_words():
                continue
            # "© Mereka Fi" = artefak scan header kolom, bukan continuation terj
            if line.startswith("\u00a9"):
                continue
            if current and re.search(r"[A-Za-z]{3,}", line) and not is_english_fragment(line):
                sep = " " if current[1][-1:].islower() or line[0].islower() else "; "
                current[1] += sep + line
    yield from flush()


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def norm_lemma(s: str) -> str:
    return s.lower().strip().replace("\u2019", "'")


def load_ocr() -> dict[int, str]:
    pages = {}
    for f in sorted(OCR_DIR.glob("p*.txt")):
        pages[int(re.sub(r"\D", "", f.stem))] = f.read_text(encoding="utf-8", errors="replace")
    return pages


def build():
    pages = load_ocr()
    rows, seen, eliminated = [], set(), []
    idx = {}  # norm_lemma -> posisi di rows (untuk REVERSE_WINS)
    for rng, rev in ((FORWARD, False), (REVERSE, True)):
        for p in rng:
            if p not in pages:
                continue
            for lemma, terj in parse_page(pages[p], rev):
                lemma = OCR_FIXES.get(lemma, OCR_FIXES.get(lemma.lower(), lemma))
                key = norm_lemma(lemma)
                if not terj.strip():
                    eliminated.append(lemma)
                    continue
                if key in seen:
                    if rev and key in REVERSE_WINS:
                        rows[idx[key]][1] = terj  # terjemahan reverse lebih tepat
                    continue
                seen.add(key)
                idx[key] = len(rows)
                rows.append([cap(lemma), terj, "", "", "", ""])
    return rows, eliminated


def write_csv(rows):
    header = [
        "# @format sambasku-dictionary",
        "# @version 2",
        "# @encoding UTF-8",
        "# @separator ,",
        "# @title Kamus dan Ensilopedia Melayu Sambas",
        "# @url",
        "# @required kata,terjemahan,penjelasan_arti,type,contoh,arti_contoh",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n")
        w = csv.writer(f)
        w.writerow(["kata", "terjemahan", "penjelasan_arti", "type", "contoh", "arti_contoh"])
        w.writerows(rows)


def selftest():
    fwd = "Abis = Habis/selesai = end, finish\nmengeluarkan air mata"
    got = list(parse_page(fwd, reverse=False))
    assert got == [("Abis", "Habis/selesai mengeluarkan air mata")], got
    rev = "Abandon = meninggalkan = ninggalkan\nSubsidy = bantuan = sokongan"
    got = list(parse_page(rev, reverse=True))
    assert got == [("ninggalkan", "meninggalkan"), ("sokongan", "bantuan")], got
    multi = "Verge = tepi, condong = tappi, cundong"
    got = list(parse_page(multi, reverse=True))
    assert got == [("tappi", "tepi"), ("cundong", "condong")], got
    one2many = "Vessel = kapal, bejana = tabong"
    got = list(parse_page(one2many, reverse=True))
    assert got == [("tabong", "kapal; bejana")], got
    # anomali batch ini
    assert list(parse_page("OE ep Belacan = Terasi = fish paste", reverse=False)) == [("Belacan", "Terasi")]
    # Binturun tidak boleh menyerap definisi Birawe (lemma Birawe punya quote nyangkut)
    birawe = (
        "| Binturun = Sejenis musang = sort of civet cat |\n"
        "h Birawe \u201c = Melakukan sesuatu yg tidak . = doing something out of |\n"
        "i sesuai kemampuan. his ability !"
    )
    got = list(parse_page(birawe, reverse=False))
    assert got == [
        ("Binturun", "Sejenis musang"),
        ("Birawe", "Melakukan sesuatu yg tidak sesuai kemampuan"),
    ], got
    assert list(parse_page("Incalap = Melap lantai = wash the floor\nInda\u201d = Tidak = ae", reverse=False)) == [
        ("Incalap", "Melap lantai"), ("Inda", "Tidak")
    ]
    assert list(parse_page("Gerammus = slap at mouth = stop speaking", reverse=False)) == [("Gerammus", "Tampar mulut")]
    assert list(parse_page("Billas = Bilas \u00a9 Mereka Fi = to rinse, wash off", reverse=False)) == [("Billas", "Bilas")]
    assert list(parse_page("Caer =(Cair | = liquid", reverse=False)) == [("Caer", "Cair")]
    assert list(parse_page("Cakkah = Membuka dgn menekankan kedua belah tangan palm hand", reverse=False)) == [
        ("Cakkah", "Membuka dgn menekankan kedua belah tangan")
    ]
    # anomali batch 2
    assert list(parse_page("' v Kelakonan = Perilaku = behaviour, character,\ntemper P ;", reverse=False)) == [
        ("Kelakonan", "Perilaku")
    ]
    killan = "| UI Killan - Jengkal - span\nly lod, feng killas = Bersisir = to comb"
    assert list(parse_page(killan, reverse=False)) == [("Killan", "Jengkal"), ("killas", "Bersisir")]
    assert list(parse_page("| Kirre - Mengira | = guess, Hunch . .", reverse=False)) == [("Kirre", "Mengira")]
    assert list(parse_page("iF ae = garuk = scratch ad", reverse=False)) == [("kissai", "garuk")]
    kuttong = (
        "$ Kuttong = Buntung = handicapped\n"
        ", ,/Kuwai = Biasanya diulang berarti = hanging down ;\n"
        "$ bergantungan\n"
        "' 1 Kuwawe = Sanggup = able, can, capable"
    )
    assert list(parse_page(kuttong, reverse=False)) == [
        ("Kuttong", "Buntung"),
        ("Kuwai", "Biasanya diulang berarti bergantungan"),
        ("Kuwawe", "Sanggup"),
    ]
    assert list(parse_page("\u201c vLullongan = Kuat daya tahan = strong stamina", reverse=False)) == [
        ("Lullongan", "Kuat daya tahan")
    ]
    assert list(parse_page("KY Masjid = Mesjid = mosque", reverse=False)) == [("Masjid", "Mesjid")]
    assert list(parse_page("| Mbulla' z Bohong = lie, untrue", reverse=False)) == [("Mbulla' Bohong", "Bohong")]
    assert list(parse_page("JS Ngelaik = mencuat = bent", reverse=False)) == [("Ngelaik", "mencuat")]
    assert list(parse_page("Memadamkan = extinguish", reverse=False)) == [("Memadamkan", "Padam")]
    assert list(parse_page("YV Rangngassan = Pemarah = hot tempered", reverse=False)) == [("Rangngassan", "Pemarah")]
    assert list(parse_page("ie if Sakat = Ganggu, goda = disturb", reverse=False)) == [("Sakat", "Ganggu, goda")]
    assert list(parse_page("Menvapa = say hallo", reverse=False)) == []
    # anomali batch 3
    assert list(parse_page("Park = taman, parkir = taman, parker\n| 197\nsnl |", reverse=True)) == [
        ("taman", "taman"), ("parker", "parkir")
    ]
    got = list(parse_page("Groin = lipat paha = sel', pippe", reverse=True))
    assert got == [("sel'", "lipat paha")], got  # OCR_FIXES sel'->Sela' di build()
    assert list(parse_page("Ayah : = Ayah \"2 father", reverse=False)) == [("Ayah", "Ayah")]
    assert list(parse_page("Marrah = Memerah *", reverse=False)) == [("Marrah", "Memerah")]
    assert list(parse_page("Nawar = Menawar harga _", reverse=False)) == [("Nawar", "Menawar harga")]
    assert list(parse_page("Cammas ; = Cemas \u201c= anxious", reverse=False)) == [("Cammas", "Cemas")]
    assert list(parse_page("TB Appetitte = nafsu makan = napsu makan TEA", reverse=True)) == [("napsu makan", "nafsu makan")]
    assert list(parse_page("we, Apt = cocok = patut goed :", reverse=True)) == [("patut", "cocok")]
    ngarau = "_, Ngarau = mengerjakan semua = too active\nNgareh = Mencari sesuatu diantara ="
    assert list(parse_page(ngarau, reverse=False)) == [
        ("Ngarau", "mengerjakan semua"), ("Ngareh", "Mencari sesuatu diantara")
    ]
    assert list(parse_page("P Anxious = cemas = cammas me Ane", reverse=True)) == [("cammas", "cemas")]
    dice = "\u2018Gg MP i dice = yang manapun juga = nang mane aja\u2019 ee eae ae"
    assert list(parse_page(dice, reverse=True)) == [("nang mane aja'", "yang manapun juga")]
assert list(parse_page("DIDI - went. VAro\u2019 = goreng tanpa minyak = non oil fry", reverse=False)) == [
    ("Aro'", "Goreng tanpa minyak")
]

# anomali batch 4
afford = "F Afford = sanggup memberikan = mampu :\nA 3 Afloat - terapung -.ngapong, timbol"
assert list(parse_page(afford, reverse=True)) == [
    ("mampu", "sanggup memberikan"),
    ("ngapong", "terapung"),
    ("timbol", "terapung"),
]
assert list(parse_page(" Agriculture _ = pertanian pak tgs = betapaman- |", reverse=True)) == []
assert list(parse_page("Ar umat - ble Unte = Unta : = camel", reverse=False)) == []
assert list(parse_page("Uzor = Uzur = enfeeble\nUzzor ae a || ne = too old", reverse=False)) == [
    ("Uzor", "Uzur")
]
assert list(parse_page("Ussut = Usut, mengusut » . = investigate t", reverse=False)) == [
    ("Ussut", "Usut; mengusut")
]
assert list(parse_page("ida \u201cadl = Untung = profit", reverse=False)) == [("Untong", "Untung")]
ullu = "Ullu = Hulu = down stream\nkutu. <p Ulu ile\u2019 = Hilir mudik = to and fro"
assert list(parse_page(ullu, reverse=False)) == [("Ullu", "Hulu"), ("Ulu ile'", "Hilir mudik")]
assert list(parse_page("Pd | OA Ullut = Lamban . = slow, as slow as leggard -", reverse=False)) == [
    ("Ullut", "Lamban")
]
assert list(parse_page("ef to ren L Tiperedok = Posisi duduk setelah jatuh = = seating position after", reverse=False)) == [
    ("Tiperedok", "Posisi duduk setelah jatuh")
]
assert list(parse_page("[> Tiong = Tiung/nama burung yg bisa - speaking birds", reverse=False)) == [
    ("Tiong", "Tiung/nama burung yg bisa bicara")
]
assert list(parse_page("Ippo Kf Ky Tipacul = Tiba-tiba muncul = encounter", reverse=False)) == [
    ("Tipacul", "Tiba-tiba muncul")
]
songko = "v Songko\u2019 = Kopiah = hat\ny\u00bb Sontok = Dalam keadaan sulit baik ke = dilemma, broke\nuangan maupun lainnya"
assert list(parse_page(songko, reverse=False)) == [
    ("Songko'", "Kopiah"),
    ("Sontoh", "Dalam keadaan sulit baik keuangan maupun lainnya"),
]
ryddu = "2 Ryddu = Maju terus = on ward no retreat\n3 Roger 2 Ral Reta \u00bb ;"
assert list(parse_page(ryddu, reverse=False)) == [("Ruddu", "Maju terus")]
assert list(parse_page("ial Roval = Boros = inefficient, uneconomic", reverse=False)) == [("Royal", "Boros")]
assert list(parse_page("Rovah = Koyak besar = big torn :", reverse=False)) == [("Royah", "Koyak besar")]
assert list(
    parse_page("5 Reli = Sepeda raleigh buatan Inggeris = femaous and expensive\nmerupakan sepeda termewah bycycle at that time.", reverse=False)
) == [("Reli", "Sepeda raleigh buatan Inggeris merupakan sepeda termewah dan termahal dizamannya :")]
assert "\u2014" not in list(parse_page("Xyzw = Ayam \u2014 Babi = c", reverse=False))[0][1]
assert "\u00bb" not in list(parse_page("Xyzw = Ayam \u00bb Babi = c", reverse=False))[0][1]
print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    rows, eliminated = build()
    write_csv(rows)
    print(f"rows={len(rows)} eliminated={len(eliminated)}")
    print(f"out={OUT}")


if __name__ == "__main__":
    main()
