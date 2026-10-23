# Android AI Universal Connector

Fondasi konektor AI multi-model yang dirancang agar berbagai assistant dapat berinteraksi dengan layanan digital dan perangkat Android melalui antarmuka standar, kontrol kebijakan, dan persetujuan manusia.

> **Status saat ini: P0 lulus CI; gateway remote masih prototipe dan belum dideploy.** Branch ini menyediakan server MCP lokal berbasis stdio, registry konektor, policy allowlist, task draft, approval request, audit event, serta prototipe gateway Streamable HTTP yang memvalidasi bearer token melalui OAuth token introspection. Belum ada konektor Gmail/YouTube/Meta/TikTok/Shopee yang melakukan panggilan API nyata, belum ada konfigurasi identity provider nyata, belum ada aplikasi Android, dan belum ada deployment staging/production.

## Prinsip arsitektur

`AI client → MCP host/adapter → policy engine → platform connector → official API`

MCP menstandarkan cara host AI menemukan dan memanggil tools; MCP tidak otomatis memberikan dukungan kepada semua model, akses akun, OAuth consent, ataupun izin API platform. Setiap AI client perlu diuji secara terpisah. P0 memakai transport stdio lokal; endpoint internet/HTTPS belum diaktifkan.

## Cakupan P0 yang ada

| Komponen | Status P0 |
|---|---|
| MCP server dengan SDK Python resmi | Implementasi awal; CI menjalankan import, unit test, dan compile check |
| Tool discovery melalui MCP client | Diuji oleh integration test pada branch perbaikan ini |
| `connector.list`, `connector.status`, `connector.permissions` | Terimplementasi; seluruh konektor tetap `NOT_CONFIGURED` |
| `task.create`, `task.status`, `task.cancel` | Terimplementasi untuk task draft; tidak mengeksekusi aksi eksternal |
| `approval.request` | Membuat permintaan review untuk tindakan sensitif; bukan persetujuan dan bukan eksekusi |
| `audit.query` | Terimplementasi dengan event tersanitasi |
| OAuth dan token storage | Belum dibuat |
| Konektor platform dan Android agent | Belum dibuat |
| Remote MCP/HTTPS | Prototipe Streamable HTTP ada di `aic_connector.gateway`; belum dideploy dan belum diuji dengan identity provider nyata |
| OAuth resource-server auth | Token introspection RFC 7662 dengan fail-closed checks; konfigurasi issuer/audience/secret masih wajib |
| Persistensi produksi | Belum dibuat; gateway memakai state in-memory dan belum cocok untuk multi-user/production |
| State persistence | P0 memakai memori proses; restart akan menghapus task dan audit |

## Persyaratan

- Python 3.11+
- Koneksi internet saat memasang dependency Python
- GitHub Codespaces atau Python environment lokal
- Tidak memerlukan OpenAI API key untuk menjalankan fondasi P0

## Instalasi dan pengujian

Jalankan perintah dari **root repository**, yaitu direktori yang berisi `pyproject.toml`:

```bash
python --version
python -m pip --version
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip show android-ai-universal-connector
python -m pip show mcp
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Setelah perubahan instalasi, jika shell masih tidak menemukan command, muat ulang terminal Codespaces lalu periksa lokasi executable:

```python
python -c "import aic_connector; print(aic_connector.__file__)"
python -c "from aic_connector.server import main; print('server import OK')"
python -m pip show -f android-ai-universal-connector
```

## Pemecahan masalah instalasi

### `Package not found` atau `pip install -e .` gagal

1. Pastikan Codespaces membuka repository ini dan berada di root-nya:

   ```bash
   pwd
   ls -la
   ```

2. Pastikan `pyproject.toml` terlihat pada output `ls`. Jika tidak, pindah ke direktori repository yang benar sebelum memasang package.
3. Jalankan `python -m pip install -e .` dari direktori tersebut. Jangan memakai `pip install android-ai-universal-connector` sebagai pengganti instalasi editable lokal; package ini dikembangkan dari repository.
4. Jika gagal, salin **pesan error non-rahasia lengkap** mulai dari baris error pertama sampai akhir. Jangan kirim token, password, atau environment secrets.

### `aic-connector: command not found`

1. Pastikan instalasi editable berhasil dengan `python -m pip show android-ai-universal-connector`.
2. Jalankan `python -m pip show -f android-ai-universal-connector` untuk melihat file yang dipasang.
3. Muat ulang terminal setelah instalasi, lalu coba `aic-connector` lagi.
4. Jalankan fallback berikut untuk memisahkan masalah PATH dari masalah import:

   ```bash
   python -m aic_connector.server
   ```

5. Jika fallback berhasil tetapi command belum ditemukan, kemungkinan executable berada di direktori Scripts/bin yang tidak ada di PATH shell. Jika import juga gagal, gunakan error import sebagai petunjuk root cause berikutnya.

## Menjalankan server MCP lokal

Setelah dependency terpasang:

```bash
aic-connector
```

Atau:

```bash
python -m aic_connector.server
```

Server lokal berjalan lewat **stdio** untuk MCP host yang dapat meluncurkan proses lokal. Server lokal tidak membuat URL publik dan tidak otomatis dapat dijangkau ChatGPT Android hanya karena repository berada di GitHub Codespaces.

## Prototipe gateway remote (belum untuk production)

Branch ini juga menyediakan `aic-gateway`, server MCP **Streamable HTTP** terpisah dengan OAuth resource-server authentication. Token opaque diverifikasi melalui endpoint introspection RFC 7662. Server menolak konfigurasi yang belum lengkap; verifier menerima token hanya jika introspection menyatakan aktif dan issuer, audience, expiry, client ID, serta scopes lolos validasi.

Konfigurasikan environment variables melalui secret manager/platform environment, bukan melalui chat atau Git:

- `AIC_MCP_ISSUER_URL` — issuer OAuth yang dipercaya.
- `AIC_MCP_RESOURCE_URL` — URL publik endpoint MCP yang tepat, biasanya `https://mcp.example.com/mcp`.
- `AIC_OAUTH_INTROSPECTION_URL` — endpoint introspection resmi dari identity provider.
- `AIC_OAUTH_CLIENT_ID` dan `AIC_OAUTH_CLIENT_SECRET` — kredensial confidential client untuk introspection.
- `AIC_MCP_REQUIRED_SCOPES` — daftar scope dipisahkan spasi; default `aic:read`.
- `AIC_MCP_ALLOWED_ORIGINS` — origin browser yang diizinkan, dipisahkan koma; kosong berarti tidak ada origin browser yang diizinkan.
- `AIC_MCP_BIND_HOST` dan `AIC_MCP_PORT` — bind address dan port; default hanya `127.0.0.1:8000`.

Jalankan hanya setelah identity provider memberikan konfigurasi valid:

```bash
aic-gateway
```

Untuk staging di container, bind ke interface internal container dan tempatkan server di belakang reverse proxy TLS yang tepercaya. Jangan expose port HTTP mentah ke internet. URL issuer, resource, introspection, dan audience harus sesuai persis dengan kebijakan identity provider. Contoh `.env.example` tidak berisi kredensial nyata.

**Status gateway: prototipe kode saja.** Belum ada staging host, HTTPS certificate, OAuth provider yang dikonfigurasi, database persisten, multi-user isolation, rate limiting, backup/recovery, atau tes ChatGPT/Claude aktual. Jangan nyatakan STAGING READY sampai semua hal tersebut diuji.

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
- File `.env`, credential file umum, private key, dan direktori secret diabaikan oleh Git; periksa file yang sudah pernah di-commit secara terpisah karena `.gitignore` tidak menghapusnya dari riwayat.
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

Keberhasilan build, test, koneksi akun, dan kompatibilitas klien harus didukung hasil aktual. CI hijau membuktikan job CI lulus; itu tidak membuktikan koneksi OAuth provider, remote deployment, atau kompatibilitas ChatGPT/Claude. Branch ini menambahkan diagnostik instalasi, perlindungan secret lokal, tes tool discovery, serta prototipe gateway terautentikasi.
