<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Menautkan aplikasi-aplikasi suite omega satu sama lain, di satu mesin maupun di seluruh jaringan**

> Dibuat oleh [kraynux](https://github.com/kraynux) untuk [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Halaman resmi: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/id/) &nbsp; Pratinjau: [Tangkapan layar](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Antarmuka tersedia dalam **17 bahasa** — lihat [Bahasa antarmuka](#bahasa-antarmuka).  
**Bahasa:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** adalah penghubung suite `omega-`: ia menemukan aplikasi omega yang terpasang (omega-serv, omega-fire, omega-jail…) di mesin ini dan di mesin-mesin jaringan Anda, menunjukkan apa yang sudah tertaut satu sama lain dan apa yang belum, lalu memulihkan apa yang kurang — selalu dengan menunjukkan terlebih dahulu apa yang akan dilakukannya. Setelah tertaut, aplikasi-aplikasi saling menemukan tanpa perlu menjalankan omega-connect.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/omega-connect/D.png" width="24%" />
</p>

## 1. Visi dan cakupan

Aplikasi omega dibuat untuk bekerja sama: log omega-serv dibaca oleh jail omega-jail, blokir fail2ban masuk ke daftar hitam omega-serv, dan omega-fire menampilkan semua itu. Namun berkas-berkasnya harus berada di tempat yang benar, dengan izin yang benar, dan setiap aplikasi harus tahu di mana aplikasi lainnya berada. Omega-connect menangani hal itu.

### Yang dilakukan Omega-connect

- Menemukan aplikasi omega di mesin ini (folder pribadi, layanan systemd, OpenRC atau runit, `/srv`, registri instans omega-serv) dan di mesin lain, yang dijangkau melalui SSH dengan kunci Anda.
- Menyimpan **registri** semua aplikasi di semua mesin, beserta versi dan statusnya.
- Memeriksa setiap **tautan** antaraplikasi (log yang dibaca jail, jembatan ke daftar hitam, daftar terlindungi, berkas omega-jail di fail2ban, kartu identitas, ruang bersama) dan memberi tahu apa yang bermasalah.
- **Menyinkronkan**: membuat kartu identitas yang belum ada dan menyiapkan **ruang bersama** tempat aplikasi-aplikasi saling menemukan.
- **Memperbaiki**: meminta aplikasi pemilik berkas untuk membereskan setiap ketidaksesuaian; omega-connect tidak pernah melakukannya sendiri.
- **Memperbarui atau memasang ulang** aplikasi yang terlalu lama atau terpasang dengan salah di mesin jaringan, dari Release GitHub-nya (sidik jari diverifikasi).
- Bertindak pada mesin jaringan **dari komputer Anda**: tidak ada yang perlu diketik di sana, kata sandinya diminta sekali, oleh mesin itu sendiri.
- Menghasilkan **laporan** lengkap (teks, JSON, atau halaman HTML).

### Yang tidak dilakukan Omega-connect

- Ia tidak menggantikan aplikasi mana pun: fail2ban, omega-fire, omega-jail, dan omega-serv tetap menjalankan perannya masing-masing.
- Ia tidak pernah menulis ulang berkas milik aplikasi lain.
- Ia tidak memasang apa pun secara permanen di mesin jaringan untuk memindainya, dan tidak meninggalkan layanan yang tetap berjalan.
- Ia tidak pernah meminta kata sandi SSH, dan tidak pernah melihat kata sandi administrator Anda.

## 2. Instalasi

### Prasyarat

- Linux, Python 3.10+.
- Untuk mesin jaringan: akses SSH dengan kunci, dan Python 3.10+ di mesin-mesin tersebut.
- Koneksi Internet untuk dependensi (dan untuk pembaruan dari GitHub).

### Instalasi

Dari folder tempat arsip berada:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Membuat lingkungan virtual `.venv` (`.venv` yang tidak lengkap disisihkan lalu dibuat ulang).
2. Memasang omega-lib (pustaka suite, disertakan dalam arsip) dan omega-connect.
3. Membuat `omega-connect.sh` dan `install.sh` dapat dieksekusi.
4. Menambahkan alias `connect` ke `~/.bashrc` dan `~/.zshrc` (tanpa duplikat).

Tidak ada langkah yang memerlukan hak administrator.

### Pembaruan

Dari folder yang BERISI `omega-connect/` (jangan pernah dari dalamnya: `tar` akan membuat folder bertingkat), ekstrak arsip baru di atasnya, lalu jalankan kembali `install.sh`. Arsip tidak berisi data lokal apa pun (`var/`: registri mesin, pengaturan, ekspor): tidak ada yang sudah ada yang ditimpa.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Penggunaan

### Mode interaktif (TUI)

```bash
./omega-connect.sh
```

atau, jika alias sudah dibuat, `connect`.

Menu utama memiliki dua kolom:

| Pengelolaan | Pemeliharaan |
|---|---|
| **Registri** — semua aplikasi di semua mesin, versi dan statusnya | **Perbaiki** — daftar semua yang bermasalah, dan Anda yang memilih |
| **Pindai** — mesin ini, dan penambahan mesin jaringan | **Laporan** — dokumen lengkap, untuk diekspor |
| **Tautan** — apa yang tertaut atau belum, beserta statusnya | **Pengaturan** — bahasa, tema, folder, pembersihan |
| **Sinkronisasi** — menautkan aplikasi, di semua mesin | **Bantuan** — setiap menu, fungsinya, dan detailnya |
| **Dasbor** — gambaran umum | **Keluar** |

Alur umum: **Pindai** (mesin ini, lalu mesin Anda yang lain, yang diusulkan berdasarkan profil Unison, `~/.ssh/config`, dan `known_hosts` Anda) → **Registri** (perbarui atau pasang ulang aplikasi yang lama) → **Sinkronisasi** (centang, lalu sinkronkan) → **Tautan** dan **Dasbor** untuk melihat hasilnya → **Perbaiki** jika masih ada ketidaksesuaian.

Setiap tindakan menampilkan rencananya terlebih dahulu; tidak ada yang dijalankan sebelum Anda setuju. Untuk mesin jaringan, antarmuka memberi tempat bagi terminal selama tindakan berlangsung: mesin itu sendiri yang meminta kata sandinya, sekali.

#### Pintasan keyboard

| Tombol | Tindakan |
|---|---|
| `↑` / `↓` | Berpindah dari satu elemen ke elemen lain |
| `Tab` / `Shift+Tab` | Berpindah dari satu area layar ke area lain |
| `Enter` / `Spasi` | Mengaktifkan; mencentang baris (Sinkronisasi) |
| `Esc` | Kembali ke layar sebelumnya |
| `a` | Bantuan |
| `s` | Pengaturan |
| `t` | Tema berikutnya |
| `r` | Gambar ulang layar |
| `q` | Keluar (dengan konfirmasi) |
| `Ctrl+P` | Perintah: tema, tangkapan layar, keluar |

### Status

| Aplikasi | Tautan |
|---|---|
| ● Tertaut — ada di ruang bersama, mutakhir | OK |
| ◐ Terdaftar — punya kartu identitas, belum ada di ruang bersama | perlu diperbaiki |
| ○ Terdeteksi — tanpa kartu identitas | perlu diperbaiki (memblokir) |
| ▲ Perlu diperbaiki — ada ketidaksesuaian | tidak ada — tidak ada yang perlu ditautkan |
| ◌ Versi lama — perlu diperbarui | tidak dapat diperiksa |
| ◇ Instalasi belum selesai — perlu dipasang ulang | |
| ✕ Tidak terjangkau — mesin tidak lagi merespons | |

### Bahasa antarmuka

Antarmuka tersedia dalam 17 bahasa: Prancis, Inggris, Spanyol, Portugis (Brasil), Italia, Jerman, Belanda, Polandia, Rusia, Tionghoa Sederhana, Vietnam, Thai, Indonesia, Jepang, Korea, Hindi, dan Arab. Bahasa dipilih di Pengaturan (« Langue / Language », label yang tidak pernah diterjemahkan) dan berlaku setelah antarmuka dimulai ulang; variabel `OMEGA_CONNECT_LANG` (misalnya `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) memaksakan satu bahasa selama satu sesi. Di konsol teks Linux (TTY), bahasa dengan aksara non-Latin ditampilkan dalam bahasa Inggris untuk sesi tersebut. Baris perintah tetap dalam bahasa Prancis.

### Kontak dan dukungan

Bantuan (tombol `a`) menyediakan layar **Kontak dan dukungan**: *Traktir kopi* (halaman PayPal pengembang), *Hubungi dukungan* (alamat surel dan formulir kontak situs, ditampilkan apa adanya), *Daftarkan saya sebagai pengguna (anonim)*, dan *Periksa pembaruan*. Pendaftaran bersifat sukarela, nonaktif secara bawaan, dan dikirim hanya sekali: gunanya hanya untuk menghitung pengguna dan, jika Anda mau, benua atau negara mereka (daftar tertutup, tidak pernah teks bebas). Yang dikirim hanyalah kunci acak, nama perangkat lunak (`omega-connect`), dan versinya; tidak pernah nama, nama mesin, alamat, atau pengaturan. Alamat IP tidak dicatat dalam pendaftaran, tetapi, seperti setiap kunjungan, melewati pemeriksaan keamanan dan log server penerima. Penarikan diri dapat dilakukan kapan saja dari layar yang sama. Pemeriksaan pembaruan hanya membaca daftar versi yang telah dirilis, dan tidak pernah tanpa klik.

### Mode skrip (CLI)

Perintah apa pun memicu mode baris perintah:

```bash
# Aplikasi di mesin ini, atau di mesin jaringan (SSH dengan kunci Anda)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Menautkan aplikasi di mesin ini, atau di mesin jaringan
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Memperbarui aplikasi yang terlalu lama di mesin jaringan (Release GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Perbaiki: mesin ini, atau mesin jaringan
./omega-connect.sh reparer --machine moi@192.168.1.109

# Status setiap tautan, dan laporan lengkap
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` menampilkan rencana tanpa menjalankan apa pun; `--oui` menjalankan tanpa bertanya; `--toutes-machines` memproses semua mesin yang dikenal secara berurutan, satu per satu.

## 4. Mesin jaringan

- **Koneksi:** hanya SSH dengan kunci Anda; `~/.ssh/config` dihormati (alias, port, pengguna). Kunci yang dilindungi frasa sandi harus dimuat di agen SSH.
- **Koneksi pertama:** sidik jari kunci mesin ditampilkan sebelum apa pun; kunci yang berubah ditolak.
- **Pemindaian:** sebuah program dikirim ke memori, hanya baca; tidak ada yang dipasang atau ditulis, dan tidak ada kata sandi yang diminta.
- **Tindakan** (sinkronisasi, perbaikan, pembaruan): sebuah folder privat sementara menerima program dan, bila perlu, arsip; folder itu dihapus di akhir. Kata sandi administrator diminta oleh mesin itu sendiri, sekali.
- **Identitas:** sebuah mesin dikenali dari sidik jari pengenal sistemnya, bukan dari alamatnya: meski dijangkau melalui dua jaringan, ia tetap satu mesin.
- **Pembaruan:** dari Release GitHub setiap aplikasi; sidik jari arsip diverifikasi dengan `sha.txt` sebelum dikirim, lalu sekali lagi di mesin tujuan. Setiap aplikasi dipasang sesuai bagian “Pembaruan” di README-nya.

## 5. Kartu identitas dan ruang bersama

- **Kartu identitas:** saat dipasang, setiap aplikasi omega menulis sebuah berkas kecil yang menyatakan siapa dirinya (aplikasi, versi, pengenal, mesin). Dapat dibaca semua orang, tidak pernah dapat diubah oleh akun lain.
- **Ruang bersama:** `/var/lib/omega-synchro`, khusus untuk grup `omega-synchro`, tempat hanya administrator yang menulis. Omega-connect menyalin ke sana kartu identitas dan deskripsi setiap aplikasi; aplikasi-aplikasi saling menemukan di sana, bahkan saat omega-connect tidak dijalankan.
- **Registri ruang bersama:** semua yang dibuat omega-connect dicatat di sana; penghapusan hanya membatalkan apa yang tercatat, dan berkas yang tidak dikenal tidak pernah dihapus.

## 6. Keamanan

- Tanpa peningkatan hak saat dijalankan: omega-connect berjalan di bawah akun Anda; sudo diminta per tindakan, dengan perintah ditampilkan terlebih dahulu.
- Perbaikan dilakukan oleh aplikasi pemilik berkas (omega-jail untuk apa yang ia pasang di fail2ban, omega-serv untuk izin `var/`-nya, setiap aplikasi untuk kartu identitasnya).
- Tidak ada aplikasi yang dijalankan jika berisiko meminta kata sandi tanpa terminal.
- Pencarian tidak pernah mengikuti tautan simbolik, tidak berpindah sistem berkas, dan mengabaikan mount jaringan.
- Pembersihan folder ekspor dan tangkapan layar menolak folder sistem, folder pribadi, dan folder omega-connect.

## 7. Ekspor

- **Laporan**: ringkasan semua mesin, daftar rinci apa yang masih harus dilakukan, registri, mesin jaringan, tautan setiap mesin, ruang bersama. Teks, JSON, atau halaman HTML (tema dapat dipilih).
- **Bantuan**: dapat diekspor sebagai halaman HTML.
- **Tangkapan layar**: `Ctrl+P` → “Tangkapan layar” (SVG).
- Folder bawaan: `var/exports/` dan `var/screenshots/` di folder omega-connect, dapat diubah di Pengaturan.

## 8. Arsitektur

Clean Architecture, seperti bagian lain suite: `domain/` (aturan murni), `application/` (kasus penggunaan), `ports/`, `infrastructure/` (SSH, berkas, GitHub, papan klip), `interfaces/` (baris perintah dan antarmuka Textual), `app/` (perakitan). Dependensi selalu mengarah ke dalam, diverifikasi oleh `import-linter`. Kontrak yang dibagi antaraplikasi (kartu identitas, deskripsi, ruang bersama) berada di `omega-lib`.

## 9. Pengujian

```bash
source .venv/bin/activate
lint-imports        # memeriksa aturan dependensi
pytest -q
ruff check src tests
mypy src
```

Pengujian tidak pernah menyentuh `var/` yang sebenarnya, jaringan, maupun sudo: SSH palsu yang dijalankan secara lokal, GitHub palsu, folder sementara.

## 10. Di luar cakupan

- Menggantikan fail2ban, omega-fire, atau omega-jail.
- Pemantauan terus-menerus (tidak ada layanan permanen).
- Memasang aplikasi omega untuk pertama kalinya di mesin jaringan.
- Dasbor web.

## Lisensi

MIT — lihat [LICENSE](../../../LICENSE).

---

> Omega-connect — Temukan, tautkan, perbaiki.
> Aplikasi omega saling berbicara; omega-connect memastikan mereka bisa.
