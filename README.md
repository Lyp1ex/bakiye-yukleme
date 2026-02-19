# Telegram Bakiye Yükleme Botu (Türkçe MVP)

Bu proje Telegram üzerinde çalışan, tamamen **admin onaylı** bakiye yükleme botudur.

## Özellikler

- Kullanıcıdan bakiye yükleme tutarı alma
- Kural kontrolü:
  - Minimum: `15.000`
  - Maksimum: `250.000`
  - Ödenecek tutar: `%20` (ör. 50.000 bakiye için 10.000 TL)
- IBAN gösterme + dekont yükletme
- **Otomatik bakiye ekleme yok**
- Admin onayı sonrası bakiye ekleme
- Admin panelinden:
  - Bekleyen banka talepleri
  - Bekleyen kripto talepleri
  - Kullanıcı arama
  - Manuel bakiye ekleme/çıkarma
  - Metin şablonlarını düzenleme
- Web metin paneli: `/admin-panel?token=...`

## Kullanıcı Akışı

`/start` menüsü:

- `Bakiyem`
- `Bakiye Yükleme İşlemi`
- `Geçmişim`

`Bakiye Yükleme İşlemi`:

1. Kullanıcı yüklemek istediği bakiyeyi yazar.
2. Bot `%20` ödeme tutarını hesaplar.
3. Bot IBAN bilgisini gösterir.
4. Kullanıcı dekont gönderir.
5. Admin onaylarsa bakiye eklenir.

## 1) Kod Nereye Konur?

Bu klasörde proje zaten hazır:

`/Users/yasindemirci/Documents/AI`

Terminal açınca önce bu klasöre geç:

```bash
cd /Users/yasindemirci/Documents/AI
```

## 2) Python Kurulumu (Sıfırdan)

1. [python.org/downloads](https://www.python.org/downloads/) adresine git.
2. Python `3.11` veya üzerini kur.
3. Kurulumu kontrol et:

```bash
python3 --version
```

## 3) Gerekli Paketleri Kur

```bash
cd /Users/yasindemirci/Documents/AI
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) `.env` Dosyası Oluştur

Örnek dosyadan kopyala:

```bash
cp .env.example .env
```

`.env` içine şu alanları doldur:

```env
BOT_TOKEN=
ADMIN_IDS=
ADMIN_PANEL_TOKEN=
IBAN_TEXT=IBAN: TR690006701000000041067977 | Alıcı: Mehmet Can Yıldırım
TRON_RPC_URL=https://api.trongrid.io
TRON_WALLET_ADDRESS=
TRON_PRIVATE_KEY=
CRYPTO_AUTO_APPROVE=false
DATABASE_URL=sqlite:///./bot.db
LOG_LEVEL=INFO
TRON_CHECK_INTERVAL_SEC=45
MIN_BALANCE_AMOUNT=15000
MAX_BALANCE_AMOUNT=250000
BALANCE_PAYMENT_RATE=0.20
```

## 5) Bot Token Nasıl Alınır?

1. Telegram’da `@BotFather` aç.
2. `/newbot` yaz.
3. İsim ve kullanıcı adı ver.
4. Verilen token’ı alıp `.env` içindeki `BOT_TOKEN=` kısmına yapıştır.

## 6) Telegram Admin ID Nasıl Bulunur?

1. Telegram’da `@userinfobot` veya `@myidbot` aç.
2. `start` yaz.
3. Gelen sayısal ID’yi `.env` içinde `ADMIN_IDS=` alanına yaz.

## 7) Botu Lokal Çalıştır

```bash
cd /Users/yasindemirci/Documents/AI
source .venv/bin/activate
alembic upgrade head
python -m bot.main
```

Kontrol:

1. Telegram’dan botta `/start` yaz.
2. Admin hesabınla `/admin` yaz.
3. Metin paneli için: `http://localhost:10000/admin-panel?token=SENIN_TOKEN`
   - Lokal testte `PORT` yoksa web panel açılmaz; Render’da otomatik açılır.

## Render Üzerinde Ücretsiz Yayına Alma (24/7)

Proje `render.yaml` içerir.

1. GitHub repo’ya kodu push et.
2. [render.com](https://render.com) hesabına gir.
3. `New` -> `Blueprint` seç.
4. GitHub repo’yu bağla.
5. Render `render.yaml` dosyasını otomatik okur.
6. Ortam değişkenlerini doldur:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `ADMIN_PANEL_TOKEN`
   - `IBAN_TEXT`
   - `TRON_WALLET_ADDRESS` (opsiyonel)
   - `TRON_PRIVATE_KEY` (opsiyonel)
7. Deploy başlat.
8. Deploy sonrası kontrol:
   - `https://SENIN_RENDER_URL/health` -> `ok` dönmeli

### Uyumayı Engelleme (Ücretsiz planda)

Render free servisler boşta uyuyabilir. Sürekli açık kalması için:

1. [UptimeRobot](https://uptimerobot.com) aç.
2. Yeni HTTP monitor oluştur.
3. URL: `https://SENIN_RENDER_URL/health`
4. 5 dakikada bir ping ayarla.

## Metinleri Kod Yazmadan Düzenleme

Deploy sonrası:

`https://SENIN_RENDER_URL/admin-panel?token=SENIN_ADMIN_PANEL_TOKEN`

Buradan:

- Tüm aktif bot metinlerini düzenleyebilirsin.
- Kaydedince anında veritabanına yazılır.

## Sonradan Güncelleme

1. Kodda değişiklik yap.
2. Lokal test et:

```bash
alembic upgrade head
python -m bot.main
```

3. GitHub’a push et.
4. Render otomatik yeni deploy alır.

## Güvenlik Notu

- Bot token gizlidir, kimseyle paylaşma.
- Token sızdıysa `@BotFather -> /revoke` ile yenile.
- `CRYPTO_AUTO_APPROVE=false` kalmalı.
