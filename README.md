# JARVIS (Windows) - Exlives

Gerçek zamanlı sesli asistan arayüzü ve araç seti.

## Özellikler
- Canlı sesli konuşma (Gemini Live API)
- Türkçe odaklı JARVIS arayüzü
- Uygulama açma, sistem bilgisi, hava durumu
- Takvim / anımsatıcı işlemleri
- Tarayıcı ve medya komutları
- WhatsApp mesaj ve kişi kaydı
- Ekran analizi (vision)

## Gereksinimler
- Python 3.11+ (önerilen: 3.12)
- Windows
- Mikrofon

## Kurulum
```powershell
cd C:\Users\mkava\OneDrive\Masaüstü\jarvis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## API Ayarları
İlk açılışta arayüzden API key girebilirsin.  
İstersen örnek dosyadan da ilerleyebilirsin:

```powershell
copy config\api_keys.example.json config\api_keys.json
```

`config/api_keys.json` içinde:
- `gemini_api_key`
- (opsiyonel) `youtube_api_key`
- (opsiyonel) `youtube_channel_handle`

## Çalıştırma
```powershell
python main.py
```

## Proje Yapısı
- `main.py`: canlı oturum ve asistan akışı
- `ui.py`: arayüz
- `actions/`: araç fonksiyonları
- `memory/`: kalıcı bellek yardımcıları
- `core/prompt.txt`: sistem promptu
- `config/`: yapılandırma

## Notlar
- `venv/`, `.venv/`, `__pycache__/`, `*.pyc` repoya dahil edilmez.
- Kişisel dosyalar (`config/api_keys.json`, `memory/*.json`) `.gitignore` ile korunur.
