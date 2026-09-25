# RULES — Generator CSV Import Kosakata Sambas

File ini adalah default prompt untuk mengubah input kosakata bahasa Sambas menjadi file CSV siap impor. Berlaku untuk semua file di folder `csv/`.

## Input

```
<baris 1> nama website (sumber kosakata)
<baris 2> alamat website (boleh full URL; yang disimpan hanya domain utama — buang scheme, path, dan www. Contoh: `https://www.kamussambas.com/p/a` → `kamussambas.com`)
<baris 3+> kosakata: daftar kata berarti, atau pasangan `kata = arti` (arti boleh bernomor 1. 2. 3.)
```

## Nama file output

1. Scan file `<NNN>-...csv` di folder ini, ambil `NNN` terbesar, tambah 1 (pad jadi 3 digit, mulai dari `001`).
2. Pattern: `<NNN>-<nama_website>:<alamat_website>.csv` — contoh `003-kamus sambas:kamussambas.com.csv`.
3. Selalu buat file baru. Jangan pernah menimpa, mengubah, atau menghapus file batch lama maupun `000-templat-import-kata.csv`.

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
- Pertahankan urutan baris sesuai sumber — jangan sortir ulang.
- Entri yang artinya kosong/tidak lengkap di sumber tetap ditulis dengan kolom kosong (agar bisa dilengkapi nanti); catat entri tersebut di laporan akhir.
- Typo kecil di sumber boleh dibersihkan (kapitalisasi, spasi), tapi jangan mengubah makna.

## Validasi wajib setelah menulis

Parse file hasil dengan Python `csv.reader`, pastikan **setiap baris tepat 4 kolom**. Laporan akhir: nama file, jumlah baris data, jumlah entri dengan terjemahan kosong.
