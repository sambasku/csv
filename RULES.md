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
# @version 1
# @encoding UTF-8
# @separator ,
# @title <nama website>
# @url <domain utama>
# @required kata,terjemahan,penjelasan_arti,contoh
```

- `@title` diisi dari nama website (input baris 1), `@url` dari alamat website (input baris 2, domain utama saja - aturan sama dengan penamaan file). Jika tidak disediakan, tulis kuncinya tetap dengan nilai kosong (`# @title`); nanti app di browser atau runner/action yang mengisinya.
- Direktif lain (`@format`, `@version`, `@encoding`, `@separator`, `@required`) selalu ditulis tetap dengan nilai seperti contoh; `@required` wajib cocok dengan header template.
- Baris `#` tambahan (tanpa `@`) boleh sebagai catatan bebas.
- Sisi pembaca (app/runner): abaikan semua baris `#` di awal file. File CSV normal tanpa blok ini tetap valid - baris pertama langsung header.

## Struktur kolom (header wajib sama dengan template)

```
kata,terjemahan,penjelasan_arti,contoh
```

| Kolom               | Isi                                                                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kata`            | Kata bahasa Sambas, huruf pertama kapital, sisanya persis seperti sumber (termasuk apostrof:`Abe'`, `Dise'`)                                                                         |
| `terjemahan`      | Arti bahasa Indonesia. Multi-arti digabung dengan`; ` (ganti koma pemisah arti menjadi `; `)                                                                                         |
| `penjelasan_arti` | Kelas kata`(kb)`/`(kk)`/`(ks)`/`(kt)` + bentuk turunan, format: `kata kerja (kk). Turunan: ambekkkan (ambilkan); ngambek (mengambil)`. Kosongkan jika sumber tidak menyediakan |
| `contoh`          | Kalimat contoh beserta terjemahan:`'contoh sambas' (terjemahan indonesia)`. Kosongkan jika tidak ada                                                                                   |

## Aturan CSV

- Field yang mengandung koma **wajib** dibungkus kutip ganda `"..."` (berlaku paling sering di kolom contoh).
- Apostrof `'` tidak perlu di-escape.
- Pertahankan urutan baris sesuai sumber - jangan sortir ulang.
- Entri dengan `terjemahan` kosong **tidak ditulis ke file** (dihapus/dieliminasi). Kata tanpa arti tidak layak masuk kamus. Catat entri yang dieliminasi di laporan akhir (jumlah + daftar katanya).
- Typo kecil di sumber boleh dibersihkan (kapitalisasi, spasi), tapi jangan mengubah makna.

## Validasi wajib setelah menulis

Parse file hasil dengan Python `csv.reader` (lewati baris yang diawali `#`), pastikan **setiap baris data tepat 4 kolom** dan **tidak ada baris dengan `terjemahan` kosong** (yang kosong sudah harus tereliminasi sebelum penulisan). Laporan akhir: nama file, jumlah baris data, jumlah entri dengan terjemahan kosong (wajib `0`), daftar entri yang dieliminasi.
