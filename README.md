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

## 📦 Changelog

### v12.0 (Latest)
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
