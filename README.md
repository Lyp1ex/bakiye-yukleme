# Telegram Bakiye Yükleme + Çekim Botu (Türkçe MVP)

Bu proje Telegram üzerinde çalışan, tamamen **admin onaylı** bakiye yükleme ve çekim botudur.

## Özellikler

- Kullanıcıdan bakiye yükleme tutarı alma
- Kural kontrolü:
  - Minimum: `15.000`
  - Maksimum: `250.000`
  - Ödenecek tutar: `%20` (ör. 50.000 bakiye için 10.000 TL)
- IBAN gösterme + dekont yükletme
- **Otomatik bakiye ekleme yok**
- Admin onayı sonrası bakiye ekleme
- Tam bakiye çekim talebi:
  - Kullanıcıdan sırasıyla `Ad Soyad` -> `IBAN` -> `Banka Adı` alınır
  - Tutar seçimi yok, kullanıcı bakiyesinin tamamı çekim talebine gider
  - Admin onay/red yapar (red olursa bakiye iade)
  - Onay sonrası kullanıcıdan ekran görüntüsü (SS) toplanır
- Destek butonu: `t.me/donsalvatoree`
- Talep kodu formatı: `DS-#ID`
- Talep Durumu ekranı (son banka/kripto/çekim adımları + sıradaki adım)
- Canlı Talep Kartı (tek mesajda anlık durum + zaman çizelgesi + yenile/itiraz)
- SLA gecikme motoru (15/30/60 dk seviyeli otomatik uyarı)
- Sıra + tahmini süre gösterimi (kullanıcı taleplerinde)
- Otomatik hatırlatma (bekleyen taleplerde kullanıcı + admin)
- Risk/anti-suistimal engeli (yüksek riskli hesap blokajı, hız limiti, mükerrer dekont blokajı)
- Kurallar ve SSS menüleri
- İtiraz sistemi (reddedilen taleplere kullanıcıdan itiraz)
- AI dekont kontrolü (opsiyonel):
  - Sağlayıcı: Gemini
  - Dekont görselinden belge türü/tutar/tarih kontrolü
  - Alıcı IBAN eşleşmesi + risk skoru
  - Aynı dekont hash tekrar tespiti
  - İstenirse strict modda otomatik red
- Admin panelinden:
  - Bekleyen banka talepleri
  - Bekleyen kripto talepleri
  - Bekleyen çekim talepleri
  - Günlük finans raporu
  - CSV dışa aktar
  - KPI paneli
  - Toplu duyuru
  - İtiraz kayıt yönetimi
  - Şüpheli kullanıcı bayrakları
  - SLA geciken talepleri izleme
  - Denetim kayıtları (kim, ne zaman, ne yaptı)
  - Manuel yedek alma
  - Kullanıcı arama
  - Manuel bakiye ekleme/çıkarma
  - Metin şablonlarını düzenleme
- Günlük otomatik veritabanı yedeği (adminlere gönderim)
- Web metin paneli: `/admin-panel?token=...`

## Kullanıcı Akışı

`/start` menüsü:

- `Bakiyem`
- `Bakiye Yükleme İşlemi`
- `Çekim Talebi`
- `Talep Durumu`
- `İtiraz / Destek Kaydı`
- `Geçmişim`
- `Kurallar`
- `SSS`
- `Soru Sor / Destek`

`Bakiye Yükleme İşlemi`:

1. Kullanıcı yüklemek istediği bakiyeyi yazar.
2. Bot `%20` ödeme tutarını hesaplar.
3. Bot IBAN bilgisini gösterir.
4. Kullanıcı dekont gönderir.
5. Admin onaylarsa bakiye eklenir.

`Çekim Talebi`:

1. Kullanıcı ad-soyad yazar.
2. Bot IBAN ister.
3. Bot banka adı ister.
4. Kullanıcı `Çekim Talebi Gönder` ile onaylar.
5. Bot kullanıcının mevcut bakiyesinin tamamını çekim talebine çevirir.
6. Admin onay/red verir.

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
SUPPORT_USERNAME=donsalvatoree
APP_LAST_UPDATED=19.02.2026
TRON_RPC_URL=https://api.trongrid.io
TRON_WALLET_ADDRESS=
TRON_PRIVATE_KEY=
CRYPTO_AUTO_APPROVE=false
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest
RECEIPT_AI_ENABLED=false
RECEIPT_AI_STRICT=false
RECEIPT_AMOUNT_TOLERANCE_TRY=5.00
RECEIPT_DATE_MAX_DIFF_DAYS=3
RECEIPT_HASH_CHECK_ENABLED=true
RECEIPT_RISK_REJECT_THRESHOLD=70
RISK_FLAG_THRESHOLD=40
RISK_BLOCK_THRESHOLD=80
BANK_REQUEST_RATE_LIMIT_COUNT=3
BANK_REQUEST_RATE_LIMIT_WINDOW_MINUTES=30
DATABASE_URL=sqlite:///./bot.db
LOG_LEVEL=INFO
TRON_CHECK_INTERVAL_SEC=45
MIN_BALANCE_AMOUNT=15000
MAX_BALANCE_AMOUNT=250000
BALANCE_PAYMENT_RATE=0.20
BANK_QUEUE_ETA_MIN_PER_REQUEST=7
CRYPTO_QUEUE_ETA_MIN_PER_REQUEST=5
WITHDRAW_QUEUE_ETA_MIN_PER_REQUEST=12
REMINDER_ENABLED=true
REMINDER_INTERVAL_SEC=1800
REMINDER_MIN_AGE_MINUTES=20
REMINDER_COOLDOWN_MINUTES=60
SLA_WATCHDOG_ENABLED=true
SLA_WATCHDOG_INTERVAL_SEC=300
SLA_LEVEL1_MINUTES=15
SLA_LEVEL2_MINUTES=30
SLA_LEVEL3_MINUTES=60
SELF_PING_ENABLED=true
SELF_PING_INTERVAL_SEC=240
SELF_PING_URL=
AUTO_BACKUP_ENABLED=true
BACKUP_HOUR_UTC=3
BACKUP_MINUTE_UTC=15
BACKUP_RETENTION_DAYS=14
BACKUP_DIR=./backups
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
   - `SUPPORT_USERNAME`
   - `APP_LAST_UPDATED`
   - `TRON_WALLET_ADDRESS` (opsiyonel)
   - `TRON_PRIVATE_KEY` (opsiyonel)
   - `GEMINI_API_KEY` (AI dekont kontrolü için)
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

## Profil Görseli (BotFather)

- Hazır görsel dosyası: `assets/ds_bot_kapak.svg`
- Telegram bot profil fotoğrafını BotFather üzerinden manuel güncelleyebilirsin.
- Adımlar:
1. `@BotFather` aç
2. `/mybots` -> botunu seç
3. Edit Bot -> Edit Botpic
4. `assets/ds_bot_kapak.svg` dosyasını PNG/JPG formatına çevirip yükle

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
