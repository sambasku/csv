# RULES - Generator CSV Import Kosakata Sambas

File ini adalah default prompt untuk mengubah input kosakata bahasa Sambas menjadi file CSV siap impor. Berlaku untuk semua file di folder `csv/`.

## Input

```
<baris 1> nama website (sumber kosakata)
<baris 2> alamat website (boleh full URL; yang disimpan hanya domain utama - buang scheme, path, dan www. Contoh: `https://www.kamussambas.com/p/a` → `kamussambas.com`)
<baris 3+> kosakata: daftar kata berarti, atau pasangan `kata = arti` (arti boleh bernomor 1. 2. 3.)
```

## Nama file output

1. Scan file `<NNN>-...csv` di folder ini, ambil `NNN` terbesar, tambah 1 (pad jadi 3 digit, mulai dari `001`).
2. Pattern: `<NNN>-<nama_website>:<alamat_website>.csv` - contoh `003-kamus sambas:kamussambas.com.csv`.
3. Selalu buat file baru. Jangan pernah menimpa, mengubah, atau menghapus file batch lama maupun `000-templat-import-kata.csv`.

## Metadata header (sebelum header CSV)

File output diawali blok komentar `#` dengan direktif `@` sebagai identifier - bukan bagian data CSV:

```
# @format sambasku-dictionary
# @version 2
# @encoding UTF-8
# @separator ,
# @title <nama website>
# @url <domain utama>
# @required kata,terjemahan,penjelasan_arti,type,contoh,arti_contoh
```

- `@title` diisi dari nama website (input baris 1), `@url` dari alamat website (input baris 2, domain utama saja - aturan sama dengan penamaan file). Jika tidak disediakan, tulis kuncinya tetap dengan nilai kosong (`# @title`); nanti app di browser atau runner/action yang mengisinya.
- Direktif lain (`@format`, `@version`, `@encoding`, `@separator`, `@required`) selalu ditulis tetap dengan nilai seperti contoh; `@required` wajib cocok dengan header template.
- Baris `#` tambahan (tanpa `@`) boleh sebagai catatan bebas.
- Sisi pembaca (app/runner): abaikan semua baris `#` di awal file. File CSV normal tanpa blok ini tetap valid - baris pertama langsung header.

## Struktur kolom (header wajib sama dengan template)

```
kata,terjemahan,penjelasan_arti,type,contoh,arti_contoh
```

| Kolom               | Isi                                                                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kata`            | Kata bahasa Sambas, huruf pertama kapital, sisanya persis seperti sumber (termasuk apostrof:`Abe'`, `Dise'`)                                                                         |
| `terjemahan`      | Arti bahasa Indonesia. Multi-arti digabung dengan`; ` (ganti koma pemisah arti menjadi `; `)                                                                                         |
| `penjelasan_arti` | Penjelasan arti + bentuk turunan. **Kelas kata dipindah ke kolom `type`**. Kosongkan jika sumber tidak menyediakan                                                                    |
| `type`            | **Kode kelas kata singkat: `kb` (nomina), `kk` (verba), `ks` (adjektiva), `kt` (adverbia), `kd` (preposisi), kosong (default `umum`). Opsional.**                                           |
| `contoh`          | Kalimat contoh bahasa Sambas saja (tanpa terjemahan). Contoh: `die abangku`. Kosongkan jika tidak ada.                                                                                 |
| `arti_contoh`     | Terjemahan contoh ke bahasa Indonesia. Contoh: `dia saudara laki-lakiku`. Kosongkan jika tidak ada.                                                                                    |

## Aturan CSV

- Field yang mengandung koma **wajib** dibungkus kutip ganda `"..."` (berlaku paling sering di kolom contoh).
- Apostrof `'` tidak perlu di-escape.
- Pertahankan urutan baris sesuai sumber - jangan sortir ulang.
- Entri dengan `terjemahan` kosong **tidak ditulis ke file** (dihapus/dieliminasi). Kata tanpa arti tidak layak masuk kamus. Catat entri yang dieliminasi di laporan akhir (jumlah + daftar katanya).
- Typo kecil di sumber boleh dibersihkan (kapitalisasi, spasi), tapi jangan mengubah makna.
- Kolom `type` opsional. Jika ada, harus salah satu dari: `kb`, `kk`, `ks`, `kt`, `kd`. Jika kosong, gunakan default `umum`.
- Kolom `contoh` dan `arti_contoh` berpasangan. Jika `contoh` diisi, `arti_contoh` wajib diisi, dan sebaliknya.

## Varian input: pasangan `<sambas> : <indonesia>`

Sebagian sumber sudah berbentuk pasangan siap pakai, satu entri per baris,
tanpa header nama/URL website (contoh: `csv/a-23-10-2025.txt`). Untuk format
ini, aturan tambahan berikut berlaku **hanya** untuk file tersebut:

1. **Pemisah = titik dua pertama.** `<sambas> : <indonesia>`; `split(':', 1)`
   supaya titik dua di sisi arti tetap utuh
   (`andang dah : suatu ungkapan yang bermakna : memang seperti itu`).
2. **Indonesia kosong -> file terpisah.** Baris yang artinya kosong (setelah
   `:` hanya spasi/`;`) tidak ditulis ke CSV. Lemma-nya ditampung ke
   `<nama sumber>:tanpa-terjemahan.txt` (satu lemma per baris,
   `<nomor baris sumber><TAB><lemma>`) untuk dilengkapi manual.
3. **Titik koma di sisi Indonesia = baris baru.** Setiap segmen arti jadi baris
   CSV sendiri dengan lemma yang sama. Titik koma di ujung dibuang, bukan jadi
   segmen kosong (`gulli : kelereng;` -> satu baris).
4. **Sisi Sambas dipecah `/`, `,`, `;`.** Tiap varian jadi lemma terpisah
   dengan arti yang sama (`entayap/intayap`, `geye, goye, giye`,
   `simpakl;simper`). Garis miring di sisi Indonesia **tidak** dipecah
   (`jannat : almarhum/almarhumah` tetap satu arti).
5. **Baris `=` = dua lemma Sambas tanpa arti.** `<sambas> = <sambas>`
   (`antang = anggan`, `intemek = ngerepek`, `mer = semorengan`): kedua sisi
   masuk file tanpa terjemahan, tidak ada yang dianggap arti.

Parser: `python3 csv/scripts/parse_pasangan_kata.py csv/<sumber>.txt`
(bisa `--selftest`). Sisanya (penomoran file, blok `#`, header kolom, escape
koma, validasi 6 kolom) tetap mengikuti aturan umum di atas.

## Validasi wajib setelah menulis

Parse file hasil dengan Python `csv.reader` (lewati baris yang diawali `#`), pastikan **setiap baris data tepat 6 kolom** dan **tidak ada baris dengan `terjemahan` kosong** (yang kosong sudah harus tereliminasi sebelum penulisan). Laporan akhir: nama file, jumlah baris data, jumlah entri dengan terjemahan kosong (wajib `0`), daftar entri yang dieliminasi.