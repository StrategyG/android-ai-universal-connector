# Android AI Universal Connector

Fondasi konektor AI multi-model yang dirancang agar berbagai assistant dapat berinteraksi dengan layanan digital dan perangkat Android melalui antarmuka standar, kontrol kebijakan, dan persetujuan manusia.

> **Status saat ini: P0 foundation, belum menjadi plugin mobile yang siap produksi.** Branch ini menambahkan server MCP lokal berbasis stdio, registry konektor, policy allowlist, task draft, approval request, audit event, dan unit test. Belum ada konektor Gmail/YouTube/Meta/TikTok/Shopee yang melakukan panggilan API nyata, belum ada OAuth flow, belum ada aplikasi Android, dan belum ada remote MCP deployment.

## Prinsip arsitektur

`AI client → MCP host/adapter → policy engine → platform connector → official API`

MCP menstandarkan cara host AI menemukan dan memanggil tools; MCP tidak otomatis memberikan dukungan kepada semua model, akses akun, OAuth consent, ataupun izin API platform. Setiap AI client perlu diuji secara terpisah. P0 memakai transport stdio lokal; endpoint internet/HTTPS belum diaktifkan.

## Cakupan P0 yang ada di branch ini

| Komponen | Status P0 |
|---|---|
| MCP server memakai SDK Python resmi | Implementasi awal, perlu CI verification |
| `connector.list`, `connector.status`, `connector.permissions` | Terimplementasi; seluruh konektor tetap `NOT_CONFIGURED` |
| `task.create`, `task.status`, `task.cancel` | Terimplementasi untuk task draft; tidak mengeksekusi aksi eksternal |
| `approval.request` | Membuat permintaan review untuk tindakan sensitif; bukan persetujuan dan bukan eksekusi |
| `audit.query` | Terimplementasi dengan event tersanitasi |
| Policy engine | Allowlist, deny-by-default untuk aksi yang tidak dikenal, tindakan sensitif memerlukan approval |
| OAuth dan token storage | Belum dibuat |
| Konektor platform dan Android agent | Belum dibuat |
| Remote MCP/HTTPS, autentikasi jarak jauh | Belum dibuat; jangan diekspos ke internet |
| State persistence | P0 memakai memori proses; restart akan menghapus task dan audit |

## Persyaratan

- Python 3.11+
- Koneksi internet saat memasang dependency Python
- GitHub Codespaces atau Python environment lokal
- Tidak memerlukan OpenAI API key untuk menjalankan fondasi P0

## Menjalankan tes

Dari root repository:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

GitHub Actions menjalankan unit test dan compile check pada Python 3.11 dan 3.12.

## Menjalankan server MCP lokal

Setelah dependency terpasang:

```bash
aic-connector
```

Atau:

```bash
python -m aic_connector.server
```

Server berjalan lewat **stdio** untuk digunakan oleh MCP host yang dapat meluncurkan proses lokal. Server tidak membuat URL publik dan tidak boleh dianggap dapat dijangkau langsung oleh ChatGPT mobile hanya karena repository berada di GitHub Codespaces.

## Tool MCP yang tersedia

- `connector.list` — daftar konektor dan status konfigurasi.
- `connector.status` — status satu atau seluruh konektor.
- `connector.permissions` — daftar scope/izin yang dibutuhkan tanpa menampilkan kredensial.
- `task.create` — membuat task draft yang hash payload-nya tersimpan; tidak menyimpan isi payload mentah.
- `task.status` — membaca status task.
- `task.cancel` — membatalkan task yang belum selesai.
- `approval.request` — menambahkan permintaan review yang terikat pada tindakan, target, dan hash payload.
- `audit.query` — membaca event audit yang telah disanitasi.

Tindakan yang belum terdaftar di allowlist ditolak. Tindakan sensitif seperti mengirim email, memublikasikan konten, mengubah produk, dan eksekusi Accessibility memerlukan approval. Pada P0, bahkan tindakan yang mendapat keputusan `ALLOW` hanya dapat dibuat sebagai **draft**; belum ada executor yang menjalankan tindakan platform.

## Keamanan dan batasan

- Jangan masukkan token, password, OAuth client secret, ataupun refresh token ke repository, file contoh, prompt, atau log.
- Semua konektor saat ini `NOT_CONFIGURED`; belum ada akun yang dihubungkan atau API yang diverifikasi.
- Approval request bukan approval final. P0 tidak menyediakan mekanisme untuk model menyetujui permintaannya sendiri.
- Store dan audit P0 berada di memori proses dan belum cocok sebagai audit trail produksi.
- Sebelum remote deployment, implementasikan autentikasi dan otorisasi, HTTPS, validasi Origin/Host, rate limit, persistensi aman, pemisahan pengguna, dan pengujian keamanan.
- Sebelum koneksi platform, periksa dokumentasi resmi, OAuth scopes, izin aplikasi, kuota, dan proses review aktual.

## Roadmap

1. **P0:** fondasi MCP, policy engine, task planning, approval requests, audit events, CI.
2. **P1:** Google identity dan Gmail OAuth dengan scope minimum.
3. **P2:** aplikasi Android dan device bridge dengan izin jelas.
4. **P3:** YouTube API.
5. **P4:** Meta/Instagram dan TikTok sesuai akses API resmi.
6. **P5:** Shopee Open Platform jika akses developer tersedia.
7. **Remote integration:** deployment aman dan pengujian dengan minimal dua klien MCP yang kompatibel.

## Status klaim

Keberhasilan build, test, koneksi akun, dan kompatibilitas klien harus didukung hasil aktual. Kode yang ada belum membuktikan integrasi eksternal. Lihat branch `feat/p0-mcp-foundation` untuk implementasi P0 yang sedang diuji.
