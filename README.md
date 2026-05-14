# JARVIS (Windows) - Exlives

Gerçek zamanlı sesli asistan arayüzü ve araç seti.

## Özellikler
- Gemini Live ile gerçek zamanlı sesli sohbet
- Türkçe odaklı JARVIS arayüzü
- Uygulama açma (Windows)
- Sistem bilgisi ve hava durumu
- Tarayıcı / YouTube / YouTube Music / medya kontrolü
- Takvim ve anımsatıcı işlemleri
- WhatsApp mesaj taslağı / gönderimi
- Ekran analizi (vision)
- Kalıcı hafıza (tercihler, notlar, uygulama yolları)

## Gereksinimler
- Windows 10/11
- Python 3.11+ (önerilen: 3.12)
- Mikrofon

## Kurulum
```powershell
cd C:\Users\mkava\OneDrive\Masaüstü\jarvis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Çalıştırma
```powershell
python main.py
```

## API Ayarları
İlk açılışta uygulama içi ayar penceresinden API anahtarını girebilirsin.

İstersen dosya üzerinden:
```powershell
copy config\api_keys.example.json config\api_keys.json
```

`config/api_keys.json`:
- `gemini_api_key` (zorunlu)
- `youtube_api_key` (opsiyonel)
- `youtube_channel_handle` (opsiyonel)

## Proje Yapısı
- `main.py`: canlı oturum ve asistan akışı
- `ui.py`: arayüz
- `actions/`: yardımcı araçlar
- `memory/`: kalıcı hafıza
- `core/prompt.txt`: sistem promptu
- `config/`: uygulama yapılandırmaları
- `legacy_macos/`: Windows sürümünde aktif olmayan eski macOS yardımcıları

## Notlar
- Kişisel dosyalar (`config/api_keys.json`, `memory/*.json`) repoya dahil edilmez.
- `venv/`, `.venv/`, `__pycache__/`, `*.pyc` repoya dahil edilmez.
- Sağlık kartı artık sol paneli kaplamaz; özet bilgi kart içinde güncellenir.
