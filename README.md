# Yuukaa Browser 🌐

**Yuukaa Browser** adalah proyek peramban web (*web browser*) modern yang dirancang khusus dengan filosofi **"Minimalis Namun Sangat Fungsional"**. 

Proyek ini dibangun dari nol dan diperuntukkan khusus bagi para programmer, developer, atau *power user* yang menginginkan pengalaman berselancar di internet murni tanpa gangguan. Kami percaya bahwa sebuah browser seharusnya tidak mengonsumsi memori (RAM) secara membabi buta hanya untuk menjalankan animasi atau fitur-fitur berlebihan (*bloatware*) yang jarang digunakan.

## 🌟 Mengapa Yuukaa Browser?
- **Sangat Hemat RAM & CPU:** Dirancang dengan arsitektur inti yang ringan, Yuukaa membebaskan sumber daya komputer Anda untuk menjalankan IDE, server lokal, atau tugas berat lainnya.
- **Tanpa Pernak-pernik Basa-basi:** Tampilan antarmuka (*User Interface*) yang sangat bersih, elegan, dan langsung pada intinya (mendukung mode Gelap/Dark Mode permanen).
- **Fungsionalitas Kelas Berat:** Dibalik kesederhanaannya, Yuukaa dipersenjatai dengan mesin *render* modern, pencegat iklan (AdBlocker) bawaan dengan puluhan ribu daftar blokir, dan mode *Incognito* sejati.
- **Auto-Updater Cerdas:** Sistem *installer* (Inno Setup) dirancang setara dengan standar industri modern yang secara cerdas mendeteksi dan menimpa versi usang tanpa meninggalkan "sampah" di *storage* Anda.

## 🛠️ Teknologi Inti
- **Bahasa Utama:** Python
- **Engine Render:** QtWebEngine / Wry WebView2
- **Desain UI/UX:** 100% Vanilla CSS (Tanpa ketergantungan pada kerangka kerja eksternal yang berat)
- **Distribusi:** PyInstaller & Inno Setup

## 🔖 Changelog

### v13.1 — Refactor & Polish (Latest)
- **Refactor Arsitektur:** Memecah `main.py` yang semula berukuran ~1.535 baris menjadi 4 modul terpisah dalam folder `utility/`:
  - `utility/utils.py` — Fungsi utilitas global: config, path resolver, adblock loader, Windows Keyboard Hook
  - `utility/workers.py` — Background threads: `DownloadWorker` & `SuggestWorker` (QThread)
  - `utility/ui_components.py` — Semua widget UI kustom: `BrowserTab`, `AddressBar`, `URLPopupList`, `BookmarkDialog`, `SafeQtWebViewWidget`
  - `main.py` — Hanya berisi `YuukaaBrowser` (MainWindow), kini hanya ~450 baris
- **Fix Icon Taskbar Windows:** Menambahkan `SetCurrentProcessExplicitAppUserModelID` agar ikon browser muncul dengan benar di Windows Taskbar (bukan fallback huruf "Y" Python).
- **Upgrade Icon:** Mengonversi `icon.png` ke format `icon.ico` resolusi 256×256 berkualitas tinggi untuk menggantikan ikon sebelumnya.
- **Build Terbaru:** File `dist/YuukaaBrowser/YuukaaBrowser.exe` sudah di-*rebuild* dengan ikon dan AppUserModelID yang diperbarui.

### v13.0 — Major Update: Auto-Suggest & Developer Experience
- **Auto-Suggest URL Bar (Backend):** Migrasi API *autocomplete* dari Google (yang diblokir 403) ke **DuckDuckGo Autocomplete API** untuk hasil yang stabil dan cepat.
- **Auto-Suggest Beranda (Frontend):** Mengimplementasikan **Bing JSONP Autocomplete API** pada *search box* halaman beranda untuk melewati batasan CORS pada WebView lokal.
- **Inline Text Autocomplete:** Mengetik sebagian nama domain (misal: `face`) otomatis melengkapi sisa teks (`book.com`) berdasarkan riwayat *bookmark* pengguna.
- **Smart Suggestion UI:** Dropdown *auto-suggest* dirancang ulang sepenuhnya dengan gaya Chrome-like (dark, borderless, rounded corner). Hasil lokal (⭐ bookmark) muncul di urutan teratas, diikuti hasil dari DuckDuckGo (🔍).
- **Navigasi Localhost Pintar:** Memperbaiki bug di mana URL `localhost:3000` atau `127.0.0.1:8080` diarahkan ke mesin pencari. Kini langsung dibuka sebagai URL lokal dengan prefix `http://`.
- **Pembersihan Codebase:** Menghapus 12 file usang dan eksperimen lawas (`main_backup.py`, `toy_browser.py`, `browser_ui.html`, dll.) untuk meringankan repositori.
- **Upgrade Versi:** Seluruh referensi "Yuukaa Search V12" diperbarui menjadi "Yuukaa Search V13" pada title bar aplikasi.
- **Konfigurasi Build:** Memperbarui `YuukaaBrowser.spec` dan `installer.iss` ke versi 13.0.

### v12.0
- **New Feature:** Ditambahkan *Custom Download Manager* (Python-Native) untuk menangani file biner (seperti `.mp4`, `.zip`, `.exe`).
- **New Feature:** Ditambahkan fitur pengaturan folder unduhan secara kustom di menu Settings.
- **Bug Fix:** Memperbaiki kebuntuan (*deadlock*) antara WebView2 dan Python saat mengekstrak *cookie* secara sinkron.
- **Optimization:** *Auto-close* pada tab kosong yang terbuat secara tidak sengaja oleh mesin download, dan penundaan render tab baru agar mencegah *race condition*.

### v11.0 (Initial Release)
- **Stabilitas Inti:** Rilis produksi pertama dengan fokus pada keringanan pemakaian RAM dan CPU.
- **Sistem Installer Dinamis:** Inno Setup *auto-updater* via `AppId` cerdas.
- **Bug Fix:** Mengatasi kebuntuan (*poison bypass*) pada *minimize/restore* WebView2.
- **Navigasi Terpusat:** Tab *Hijacking* untuk memaksa *New Window* dibuka sebagai *New Tab* untuk kerapian *desktop*.

## 🧑‍💻 Penulis
Dikembangkan dengan penuh dedikasi oleh **Azis Maulana (Yuukaa)**.

---
*"Kesederhanaan adalah puncak dari kecanggihan."*
