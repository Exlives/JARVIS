#!/usr/bin/env python3
"""
JARVIS Windows - Gerçek zamanlı sesli yardımcı çekirdeği
Exlives
Windows ortamına uyarlanmış çalışma akışı
"""

import asyncio
import datetime
import threading
import traceback
import os
import re
import time
from pathlib import Path

import pyaudio  # type: ignore[reportMissingModuleSource]
from google import genai  # type: ignore[reportMissingImports]
from google.genai import types  # type: ignore[reportMissingImports]

from app_config import get_app_config_value
from ui import JarvisUI
from memory.memory_manager import load_memory, update_memory, delete_memory, format_memory_for_prompt
from actions.open_app import open_app
from actions.close_app import close_app
from actions.sys_info  import sys_info
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event
from actions.reminders import get_reminders, add_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media, stop_media
from actions.weather   import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.youtube_stats import get_youtube_channel_report
from actions.health import get_health_data, get_welcome_health_summary
from actions import tts as tts_actions

# Paths
BASE_DIR        = Path(__file__).resolve().parent
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"


CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# Model
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"

# Audio
FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE       = 1024
pya              = pyaudio.PyAudio()
AUDIO_IDLE_RESET_SECONDS = 0.35

# Tool tanımları
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Windows'ta bir uygulama açar. Spotify, Chrome, Terminal, Explorer, VS Code vb.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Uygulama adı (örnek: 'Spotify', 'Chrome', 'Terminal')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "close_app",
        "description": "Windows'ta bir uygulamayı kapatır. Örnek: hesap makinesi, Discord, Steam.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Uygulama adı (örnek: 'hesap makinesi', 'Discord')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "sys_info",
        "description": "Sistem bilgisi alır: pil durumu, CPU, RAM, disk, saat, tarih, ağ bağlantısı.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "battery | cpu | ram | disk | time | date | network | all"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": (
            "Anlık hava durumunu özetler. Varsayılan konum İstanbul'dur. "
            "Kullanıcı hava durumunu, sıcaklığı veya yağmur durumunu sorduğunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {
                    "type": "STRING",
                    "description": "Şehir veya konum. Boş bırakılırsa İstanbul kullanılır."
                }
            }
        }
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Apple Calendar takvimini okur. "
            "Bugün, yarın, sıradaki etkinlik veya yaklaşan ajandayı özetler. "
            "Kullanıcı toplantı, takvim, ajanda, etkinlik veya günlük programını sorduğunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "today | tomorrow | next | agenda | week veya dogal dilde "
                        "'onumuzdeki 30 gun', '2 hafta', 'bu ay', 'gelecek ay'"
                    )
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum etkinlik sayisi"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_calendar_event",
        "description": (
            "Apple Calendar takvimine yeni etkinlik ekler. "
            "Kullanıcı toplantı, randevu, takvime ekleme veya etkinlik oluşturma isterse kullan. "
            "Başlangıç tarihini gerçek tarih/saat olarak ver; bitiş verilmezse varsayılan süre kullanılır."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Etkinlik başlığı. Örnek: 'Dişçi Randevusu'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Başlangıç tarih/saat. ISO veya yyyy-MM-dd HH:mm formatında."
                },
                "end_iso": {
                    "type": "STRING",
                    "description": "Bitiş tarih/saat. Opsiyonel."
                },
                "location": {
                    "type": "STRING",
                    "description": "Etkinlik konumu. Opsiyonel."
                },
                "notes": {
                    "type": "STRING",
                    "description": "Etkinlik notları. Opsiyonel."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Eklenecek takvim adı. Opsiyonel."
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "true ise tüm gün etkinliği oluşturur."
                }
            },
            "required": ["title", "start_iso"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": (
            "Apple Calendar takviminden etkinlik siler. "
            "Kullanıcı bir toplantıyı, randevuyu veya takvim kaydını silmek istediğinde kullan. "
            "Aynı ada birden fazla etkinlik varsa doğru kaydı bulmak için başlangıç tarihini gerçek tarih/saat olarak ver."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Silinecek etkinlik başlığı. Örnek: 'Dişçi Randevusu'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Opsiyonel tarih/saat. Aynı isimli birden fazla etkinliği ayırt etmek için kullan."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Opsiyonel takvim adı"
                },
                "delete_all_matches": {
                    "type": "BOOLEAN",
                    "description": "true ise eşleşen tüm etkinlikleri siler"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_reminders",
        "description": (
            "Apple Animsaticilar listesini okur. "
            "Bugünkü, yaklaşan, geciken veya tüm açık anımsatıcıları özetler. "
            "Kullanıcı hatırlatma, anımsatıcı, reminder veya yapılacaklar listesini sorduğunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "today | upcoming | overdue | all | next"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum anımsatıcı sayısı"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "İstenirse belirli bir anımsatıcı listesi adı"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_reminder",
        "description": (
            "Apple Anımsatıcılar uygulamasına yeni bir anımsatıcı ekler. "
            "Kullanıcı 'hatırlat', 'anımsatıcı ekle', 'reminder kur' dediğinde kullan. "
            "Göreli zaman ifadelerini bugünkü tarih bağlamına göre due_iso alanına ISO formatında çevir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Anımsatıcı başlığı"
                },
                "due_iso": {
                    "type": "STRING",
                    "description": "Opsiyonel tarih/saat. Örnek: 2026-04-13T09:00 veya tüm gün için 2026-04-13"
                },
                "notes": {
                    "type": "STRING",
                    "description": "Opsiyonel not"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Opsiyonel anımsatıcı listesi"
                },
                "priority": {
                    "type": "STRING",
                    "description": "low | medium | high"
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "Tüm gün anımsatıcı ise true"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "browser_control",
        "description": "Tarayıcıda URL açar, Google'da arama yapar, YouTube'da ilk sonucu doğrudan oynatır veya YouTube Music araması açar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open_url | search | play_youtube | play_youtube_music"},
                "url":    {"type": "STRING", "description": "Açılacak URL (open_url için)"},
                "query":  {"type": "STRING", "description": "Arama sorgusu (search veya play_youtube için)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shell_run",
        "description": "Terminal komutu çalıştırır. Dosya işlemleri ve sistem yönetimi için kullanılır.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "Çalıştırılacak komut"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "play_media",
        "description": (
            "YouTube, Spotify veya Music uygulamasında şarkı, müzik veya video açar. "
            "Kullanıcı belirli bir platform söylerse onu kullan. "
            "Belirtmezse uygun olanı dene. "
            "Kullanıcı 'çal', 'oynat', 'aç' diyorsa autoplay=true kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Şarkı, sanatçı, albüm veya video arama ifadesi"
                },
                "provider": {
                    "type": "STRING",
                    "description": "auto | youtube | youtube_music | spotify | apple_music"
                },
                "autoplay": {
                    "type": "BOOLEAN",
                    "description": "true ise mümkünse doğrudan oynatır"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "stop_media",
        "description": "Calan medyayi durdurur/duraklatir veya tekrar devam ettirir (toggle) (YouTube, Spotify vb.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "provider": {
                    "type": "STRING",
                    "description": "auto | youtube | spotify | apple_music"
                }
            }
        }
    },
    {
        "name": "resume_media",
        "description": "Durdurulan medyayi devam ettirir (YouTube, Spotify vb.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "provider": {
                    "type": "STRING",
                    "description": "auto | youtube | spotify | apple_music"
                }
            }
        }
    },
    {
        "name": "get_youtube_channel_report",
        "description": (
            "YouTube kanalinin public istatistiklerini ve son videolarin performansini raporlar. "
            "Kullanıcı kanal istatistiklerini, abone sayısını, son videolarını, büyüme hızını "
            "veya YouTube analizini sordugunda kullan. Bu arac Studio yerine public YouTube Data API verisini kullanir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Doğal dilde analiz isteği. Örnek: "
                        "'YouTube istatistiklerim nasil', 'son videolarimi analiz et', "
                        "'kanal büyümemi özetle'"
                    )
                },
                "handle": {
                    "type": "STRING",
                    "description": (
                        "Opsiyonel kanal handle'i, kanal linki veya kanal ID'si. "
                        "Bos birakilirsa ayarlardaki youtube_channel_handle kullanilir."
                    )
                },
                "video_limit": {
                    "type": "NUMBER",
                    "description": "Analize dahil edilecek son video sayısı. Varsayılan 6."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_health_data",
        "description": (
            "Sağlık özetini getirir. Günlük sağlık verisi, uyku, adım, kalp, enerji veya benzeri "
            "sağlık sorularında kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "all | summary | sleep | steps | heart | energy veya doğal dil sorgusu"
                }
            }
        }
    },
    {
        "name": "analyze_screen",
        "description": (
            "Aktif pencerenin ekran goruntusunu alip Gemini vision ile analiz eder. "
            "Kullanıcı ekranda ne olduğunu, bir hatayı, görünen metni, butonları veya pencere içeriğini sorduğunda kullan. "
            "Bu surum yalnizca aktif pencereyi destekler."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Kullanıcının ekranla ilgili sorusu. Örnek: 'Bu hatayı oku', 'Ekranda ne var?'"
                },
                "target": {
                    "type": "STRING",
                    "description": "Su an sadece active_window desteklenir."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_memory",
        "description": "Kullanıcı hakkında önemli bilgiyi kalıcı belleğe kaydeder. İsim, tercihler ve projeler için kullanılır.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "identity | preferences | projects | notes"
                },
                "key":   {"type": "STRING", "description": "Kısa anahtar (örnek: 'name')"},
                "value": {"type": "STRING", "description": "Değer"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "delete_memory",
        "description": (
            "Kalıcı hafızadaki bir kaydı siler. "
            "Kullanıcı 'bunu hafızandan kaldır', 'unut', 'sil' gibi bir şey derse kullan. "
            "Mümkünse category ve key ile sil; emin değilsen match_text ile ilgili kaydı bulup kaldır."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Kaydın kategorisi. Örnek: notes | identity | preferences | projects"
                },
                "key": {
                    "type": "STRING",
                    "description": "Silinecek anahtar. Örnek: claude_limit_refresh"
                },
                "match_text": {
                    "type": "STRING",
                    "description": "Kaydı bulmak için kullanılacak doğal dil parçası. Örnek: 'claude ai limit yenilenmesi'"
                }
            }
        }
    },
    {
        "name": "send_whatsapp_message",
        "description": (
            "WhatsApp Desktop veya WhatsApp Web üzerinden mesaj taslağı açar veya mesajı gönderir. "
            "Kişi adı veya telefon numarasıyla çalışabilir. "
            "Telefon numarası verilmemişse kişi adını önce kayıtlı WhatsApp kişileri ve içe aktarılan telefon rehberinde ara. "
            "Kullanıcı 'gönder', 'yolla', 'ile', 'hemen gönder' gibi açık bir gönderme niyeti söylerse "
            "ekstra onay istemeden send_now=true kullan. "
            "Yalnızca 'hazırla', 'taslak aç', 'yaz ama gönderme' diyorsa send_now=false kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient_name": {
                    "type": "STRING",
                    "description": "Kişi adı. Örnek: 'Anne', 'Ahmet', 'Ece'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "Uluslararası telefon numarası. Örnek: +905551112233"
                },
                "message": {
                    "type": "STRING",
                    "description": "Gönderilecek mesaj içeriği"
                },
                "app_target": {
                    "type": "STRING",
                    "description": "desktop | web | auto. Varsayılan auto, tercihen desktop."
                },
                "send_now": {
                    "type": "BOOLEAN",
                    "description": "true ise sohbet açıldıktan sonra mesajı otomatik gönderir"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "save_whatsapp_contact",
        "description": (
            "Sık kullanılan bir WhatsApp kişisini adı ve telefon numarasıyla kalıcı belleğe kaydeder. "
            "Kullanıcı bir kişiyi 'annem', 'Ahmet', 'iş ortağım' gibi tekrar kullanılacak şekilde tanımladığında kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "display_name": {
                    "type": "STRING",
                    "description": "Kaydedilecek kişi adı. Örnek: 'Annem', 'Ahmet'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "Uluslararası telefon numarası. Örnek: +905551112233"
                },
                "aliases": {
                    "type": "STRING",
                    "description": "Virgülle ayrılmış alternatif hitaplar. Örnek: 'anne, annem, mom'"
                }
            },
            "required": ["display_name", "phone_number"]
        }
    }
]


def get_api_key() -> str:
    return str(get_app_config_value("gemini_api_key", "") or "")


def load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "Sen JARVIS'sin. Windows'ta çalışan kişisel AI asistansın. "
            "Türkçe konuş. Kısa ve net yanıtlar ver. "
            "Araçları kullanarak görevleri tamamla, taklit etme."
        )


class JarvisLive:
    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()

        self.ui.on_text_command  = self._on_text_command
        self.ui.on_pause_toggle  = self._on_pause_toggle
        self.ui.on_voice_change  = self._on_voice_change
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._paused             = False
        self._suppress_next_disconnect_error = False
        self._pending_voice_announcement = ""
        self._awaiting_response = False
        self._awaiting_since = 0.0
        self._watchdog_reconnect_inflight = False
        self._pending_app_alias_for_path = ""
        self._last_media_action_ts = 0.0
        self._last_media_provider = "auto"

    def _on_pause_toggle(self, paused: bool):
        self._paused = paused

    def _on_effects_state_change(self, enabled: bool):
        pass

    def _on_voice_change(self, voice: str):
        selected = str(voice or "").strip() or "Charon"
        self.ui.write_log(f"SYS: Ses değiştirildi: {selected}")
        self._suppress_next_disconnect_error = True
        self._pending_voice_announcement = selected
        try:
            tts_actions.VOICE = selected
        except Exception:
            pass
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._reconnect_session_for_voice(), self._loop)

    async def _reconnect_session_for_voice(self):
        try:
            await self._interrupt_audio()
            if self.session and hasattr(self.session, "close"):
                maybe = self.session.close()
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            pass

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        if tool_name == "sys_info":
            query = str(args.get("query", "")).strip().lower()
            if query in {"time", "saat", "zaman", "date", "tarih"}:
                self.ui.focus_panel("time", duration_ms=5200)
            else:
                self.ui.focus_panel("system", duration_ms=5200)
        elif tool_name == "get_weather":
            self.ui.focus_panel("weather", duration_ms=5600)

    def _infer_media_provider_from_text(self, lowered_text: str) -> str:
        text = lowered_text or ""
        if any(k in text for k in ("youtube music", "youtube müzik", "yt music", "ytmusic")):
            return "youtube_music"
        if any(k in text for k in ("youtube", "youtu be", "yt")):
            return "youtube"
        if "spotify" in text:
            return "spotify"
        return self._last_media_provider or "auto"

    def _on_text_command(self, text: str):
        if self._paused:
            return
        self.ui.write_log(f"Siz: {text}")
        lowered = self._normalize_turkish_transcript(text).lower()
        dense = lowered.replace(" ", "")
        if ("hesap makinesi" in lowered or "calculator" in lowered or "hesapmakinesi" in dense):
            if any(k in lowered for k in ("kapat", "kapa")) or "kapat" in dense:
                result = close_app("hesap makinesi")
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                return
            if any(k in lowered for k in ("aç", "ac")) or "ac" in dense:
                result = open_app("hesap makinesi")
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                return
        # Tek kelimelik/çok kısa medya kontrol komutlarını doğrudan yakala.
        compact = " ".join(lowered.split())
        hard_pause_cmds = {"durdur", "duraklat", "müziği durdur", "muzigi durdur", "müziği kapat", "muzigi kapat"}
        hard_resume_cmds = {"devam et", "devam", "müziği devam ettir", "muzigi devam ettir", "müziği tekrar aç", "muzigi tekrar ac"}
        if compact in hard_pause_cmds or compact in hard_resume_cmds:
            try:
                provider = self._last_media_provider or "auto"
                result = stop_media(provider)
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                self._last_media_action_ts = time.time()
                return
            except Exception as e:
                self.ui.write_log(f"ERR: Medya kontrolü başarısız - {e}")
                self.ui.set_state("ERROR")
                return

        # Cümle içinde dağınık/bozuk gelse bile "durdur/devam" niyetini zorla media toggle'a bağla.
        media_context = any(k in lowered for k in ("müzik", "muzik", "şarkı", "sarki", "youtube", "spotify", "yt"))
        has_resume_intent = any(k in lowered for k in ("devam et", "devam ettir", "tekrar aç", "yeniden aç"))
        has_pause_intent = any(k in lowered for k in ("durdur", "duraklat", "kapat"))
        # Bozuk boşluklu halleri için yoğun metin kontrolü
        has_resume_dense = any(k in dense for k in ("devamet", "devamettir", "tekraraç", "yenidenaç"))
        has_pause_dense = any(k in dense for k in ("durdur", "duraklat", "kapat"))
        recent_media_context = (time.time() - self._last_media_action_ts) <= 90.0
        if (media_context or recent_media_context) and (has_resume_intent or has_pause_intent or has_resume_dense or has_pause_dense):
            try:
                provider = self._infer_media_provider_from_text(lowered)
                result = stop_media(provider)
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                self._last_media_action_ts = time.time()
                return
            except Exception as e:
                self.ui.write_log(f"ERR: Medya kontrolü başarısız - {e}")
                self.ui.set_state("ERROR")
                return
        ytm_tokens = ("youtube music", "youtube müzik", "yt music", "ytmusic", "müzikte", "muzikte")
        play_tokens = ("aç", "ac", "çal", "cal", "oynat")
        if any(tok in lowered for tok in ytm_tokens) and any(tok in lowered for tok in play_tokens):
            query = lowered
            for tok in (
                "youtube music",
                "youtube müzik",
                "yt music",
                "ytmusic",
                "youtube",
                "müzikte",
                "muzikte",
                "müzik",
                "muzik",
                "açar mısın",
                "acar misin",
                "aç",
                "ac",
                "çal",
                "cal",
                "oynat",
            ):
                query = query.replace(tok, " ")
            query = " ".join(query.split()).strip(" .,!?:;")
            if not query:
                query = "mix"
            try:
                result = play_media(query=query, provider="youtube_music", autoplay=True)
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                self._last_media_action_ts = time.time()
                self._last_media_provider = "youtube_music"
                return
            except Exception as e:
                self.ui.write_log(f"ERR: YouTube Music açılamadı - {e}")
                self.ui.set_state("ERROR")
                return
        quick_media_resume_phrases = (
            "müziği tekrar aç",
            "muzigi tekrar ac",
            "müziği aç",
            "muzigi ac",
            "müziği devam ettir",
            "muzigi devam ettir",
            "devam et",
            "devam",
            "devam etsin",
            "şarkıyı devam ettir",
            "sarkiyi devam ettir",
        )
        quick_media_pause_phrases = (
            "müziği durdur",
            "muzigi durdur",
            "müziği kapat",
            "muzigi kapat",
            "müziği duraklat",
            "muzigi duraklat",
        )
        if any(p in lowered for p in quick_media_resume_phrases):
            try:
                provider = self._infer_media_provider_from_text(lowered)
                result = stop_media(provider)
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                self._last_media_action_ts = time.time()
                return
            except Exception as e:
                self.ui.write_log(f"ERR: Medya devam ettirilemedi - {e}")
                self.ui.set_state("ERROR")
                return
        if any(p in lowered for p in quick_media_pause_phrases):
            try:
                provider = self._infer_media_provider_from_text(lowered)
                result = stop_media(provider)
                self.ui.write_log(f"JARVIS: {result}")
                self.ui.set_state("LISTENING")
                self._last_media_action_ts = time.time()
                return
            except Exception as e:
                self.ui.write_log(f"ERR: Medya durdurulamadı - {e}")
                self.ui.set_state("ERROR")
                return
        if not self._loop or not self.session:
            self.ui.write_log("ERR: JARVIS bağlantısı henüz hazır değil.")
            return
        self._awaiting_response = True
        self._awaiting_since = time.time()
        self.ui.set_state("THINKING")
        fut = asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )
        def _on_done(f):
            try:
                f.result()
            except Exception as e:
                self._awaiting_response = False
                self.ui.write_log(f"ERR: Komut gönderilemedi - {e}")
                self.ui.set_state("ERROR")
        fut.add_done_callback(_on_done)

    async def _watchdog(self):
        while True:
            await asyncio.sleep(2.0)
            if self._paused or not self._awaiting_response:
                continue
            if (time.time() - self._awaiting_since) < 18.0:
                continue
            if self._watchdog_reconnect_inflight:
                continue
            self._watchdog_reconnect_inflight = True
            self._suppress_next_disconnect_error = True
            self.ui.write_log("SYS: Yanıt gecikti, bağlantı yenileniyor...")
            self.ui.set_state("THINKING")
            try:
                await self._interrupt_audio()
                if self.session and hasattr(self.session, "close"):
                    maybe = self.session.close()
                    if asyncio.iscoroutine(maybe):
                        await maybe
            except Exception:
                pass
            finally:
                self._awaiting_response = False
                self._watchdog_reconnect_inflight = False

    async def _interrupt_audio(self):
        try:
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except Exception:
                        break
            if self.session:
                await self.session.send_realtime_input(audio_stream_end=True)
            self.set_speaking(False)
        except Exception:
            pass


    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        else:
            self.ui.set_state("LISTENING")

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} - {short}")
        self.ui.write_debug(f"{tool_name}: {short}", level="ERROR")
        self.ui.set_state("ERROR")

    @staticmethod
    def _result_looks_like_error(result) -> bool:
        text = str(result or "").strip().lower()
        if not text:
            return False
        error_markers = (
            "hata",
            "error",
            "alınamadı",
            "alinamadi",
            "bulunamadı",
            "bulunamadi",
            "açılamadı",
            "acilamadi",
            "tamamlanamadı",
            "tamamlanamadi",
            "geçersiz",
            "gecersiz",
            "izin gerekiyor",
            "izin gerekli",
            "bağlantı",
            "bağlantı",
            "gerekli.",
        )
        return any(marker in text for marker in error_markers)

    @staticmethod
    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:
        action_tools = {
            "open_app",
            "add_calendar_event",
            "add_reminder",
            "delete_calendar_event",
            "remove_calendar_event",
        }
        if tool_name in action_tools:
            return True

        if tool_name == "send_whatsapp_message":
            text = str(result or "").lower()
            if bool(args.get("send_now", False)):
                return "gönderildi" in text or "gonderildi" in text
            return False

        return False

    @staticmethod
    def _clean_transcript_text(text: str) -> tuple[str, bool]:
        raw = str(text or "")
        had_noise = False
        if CONTROL_TOKEN_RE.search(raw):
            had_noise = True
            raw = CONTROL_TOKEN_RE.sub(" ", raw)
        cleaned = []
        for ch in raw:
            if ch in "\n\r\t" or ord(ch) >= 32:
                cleaned.append(ch)
            else:
                had_noise = True
        normalized = " ".join("".join(cleaned).split())
        return normalized.strip(), had_noise

    @staticmethod
    def _normalize_turkish_transcript(text: str) -> str:
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            return cleaned
        # Sık görülen parçalanmış Türkçe kelimeleri toparla.
        replacements = {
            "pe ki": "peki",
            "gör üntü": "görüntü",
            "gör üntüsü": "görüntüsü",
            "ek ran": "ekran",
            "uy gulama": "uygulama",
            "a ç": "aç",
            "he sap": "hesap",
            "maki nesi": "makinesi",
            "kapa t": "kapat",
            "te krar": "tekrar",
            "ha yır": "hayır",
        }
        low = cleaned.lower()
        for src, dst in replacements.items():
            if src in low:
                low = low.replace(src, dst)
        # İlk harf büyükse korumaya çalış.
        if cleaned and cleaned[0].isupper() and low:
            low = low[0].upper() + low[1:]
        return low

    @staticmethod
    def _looks_like_launch_command(text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        return (
            ":\\" in t
            or t.startswith(".\\")
            or t.startswith("\\\\")
            or ".exe" in t
            or "--processstart" in t
            or t.startswith("start ")
        )

    def _build_config(self) -> types.LiveConnectConfig:
        memory  = load_memory()
        mem_str = format_memory_for_prompt(memory)
        sys_p   = load_system_prompt()
        now     = datetime.datetime.now()
        time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y - %H:%M')}\n\n"

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str + "\n\n")
        parts.append(sys_p)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=str(get_app_config_value("voice", "Charon") or "Charon")
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[JARVIS] TOOL {name} {args}")
        self.ui.set_state("THINKING")

        loop   = asyncio.get_event_loop()
        result = "Tamam."
        had_exception = False

        try:
            if name == "save_memory":
                cat = args.get("category", "notes")
                key = args.get("key", "")
                val = args.get("value", "")
                if key and val:
                    update_memory({cat: {key: {"value": val}}})
                    print(f"[Memory] SAVE {cat}/{key} = {val}")
                result = "ok"

            elif name == "delete_memory":
                result = delete_memory(
                    args.get("category", ""),
                    args.get("key", ""),
                    args.get("match_text", ""),
                )

            elif name == "open_app":
                requested = str(args.get("app_name", "") or "").strip()
                r = await loop.run_in_executor(
                    None, lambda: open_app(requested))
                result = r or f"{requested} açıldı."
                low_result = str(result or "").lower()
                is_success = ("açıldı" in low_result) or ("acildi" in low_result)
                is_fail = ("bulunamadı" in low_result) or ("bulunamadi" in low_result) or ("açılamadı" in low_result) or ("acilamadi" in low_result)

                # Önceki uygulama adı bulunamadıysa, kullanıcı sonrasında yol verdiğinde eşleyip hafızaya al.
                if is_fail and requested and not self._looks_like_launch_command(requested):
                    self._pending_app_alias_for_path = requested.lower()
                elif is_success and self._looks_like_launch_command(requested) and self._pending_app_alias_for_path:
                    alias = self._pending_app_alias_for_path
                    update_memory({"app_launch_commands": {alias: {"value": requested}}})
                    self._pending_app_alias_for_path = ""
                    result = f"{result} Yol kaydedildi: '{alias}' artık bu komutla açılacak."
                elif is_success and requested and not self._looks_like_launch_command(requested):
                    # başarılıysa bekleyen eşlemeyi temizle
                    if self._pending_app_alias_for_path == requested.lower():
                        self._pending_app_alias_for_path = ""

            elif name == "close_app":
                requested = str(args.get("app_name", "") or "").strip()
                r = await loop.run_in_executor(
                    None, lambda: close_app(requested)
                )
                result = r or f"{requested} kapatıldı."

            elif name == "sys_info":
                self._focus_ui_section_for_tool(name, args)
                r = await loop.run_in_executor(
                    None, lambda: sys_info(args.get("query", "all")))
                result = r or "Bilgi alındı."

            elif name == "get_weather":
                self._focus_ui_section_for_tool(name, args)
                r = await loop.run_in_executor(
                    None, lambda: get_weather_summary(args.get("location") or None))
                result = r or "Hava durumu bilgisi alındı."

            elif name == "get_calendar_events":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_calendar_events(
                        args.get("query", "today"),
                        int(args.get("limit", 6) or 6),
                    ),
                )
                result = r or "Takvim bilgisi alındı."

            elif name == "add_calendar_event":
                r = await loop.run_in_executor(
                    None,
                    lambda: add_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("end_iso", ""),
                        args.get("notes", ""),
                        args.get("location", ""),
                        args.get("calendar_name", ""),
                        bool(args.get("all_day", False)),
                    ),
                )
                result = r or "Takvim etkinliği eklendi."

            elif name == "delete_calendar_event":
                r = await loop.run_in_executor(
                    None,
                    lambda: delete_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("calendar_name", ""),
                        bool(args.get("delete_all_matches", False)),
                    ),
                )
                result = r or "Takvim etkinliği silindi."

            elif name == "get_reminders":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_reminders(
                        args.get("query", "upcoming"),
                        int(args.get("limit", 8) or 8),
                        args.get("list_name", ""),
                    ),
                )
                result = r or "Anımsatıcı bilgisi alındı."

            elif name == "add_reminder":
                r = await loop.run_in_executor(
                    None,
                    lambda: add_reminder(
                        args.get("title", ""),
                        args.get("due_iso", ""),
                        args.get("notes", ""),
                        args.get("list_name", ""),
                        args.get("priority", ""),
                        bool(args.get("all_day", False)),
                    ),
                )
                result = r or "Anımsatıcı eklendi."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(
                        args.get("action"),
                        args.get("url"),
                        args.get("query")
                    ))
                result = r or "Tamam."

            elif name == "shell_run":
                cmd = str(args.get("command", "") or "").strip()
                r = await loop.run_in_executor(
                    None, lambda: shell_run(cmd))
                result = r or "Komut çalıştırıldı."
                low_result = str(result or "").lower()
                is_shell_success = "hata:" not in low_result and "cannot find" not in low_result and "not found" not in low_result
                if (
                    is_shell_success
                    and self._pending_app_alias_for_path
                    and self._looks_like_launch_command(cmd)
                ):
                    alias = self._pending_app_alias_for_path
                    update_memory({"app_launch_commands": {alias: {"value": cmd}}})
                    self._pending_app_alias_for_path = ""
                    result = f"{result}\nYol kaydedildi: '{alias}' artık bu komutla açılacak."

            elif name == "play_media":
                provider = str(args.get("provider", "auto") or "auto").strip().lower()
                r = await loop.run_in_executor(
                    None,
                    lambda: play_media(
                        args.get("query", ""),
                        provider,
                        bool(args.get("autoplay", True)),
                    ),
                )
                result = r or "Medya oynatma başlatıldı."
                self._last_media_action_ts = time.time()
                if provider and provider != "auto":
                    self._last_media_provider = provider

            elif name == "stop_media":
                provider = str(args.get("provider", "auto") or "auto").strip().lower()
                r = await loop.run_in_executor(
                    None,
                    lambda: stop_media(provider),
                )
                result = r or "Medya durdurma komutu gönderildi."
                self._last_media_action_ts = time.time()

            elif name == "resume_media":
                provider = str(args.get("provider", "auto") or "auto").strip().lower()
                r = await loop.run_in_executor(
                    None,
                    lambda: stop_media(provider),
                )
                result = r or "Medya devam ettirme komutu gönderildi."
                self._last_media_action_ts = time.time()

            elif name == "get_youtube_channel_report":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_youtube_channel_report(
                        args.get("query", "overview"),
                        args.get("handle", ""),
                        int(args.get("video_limit", 6) or 6),
                    ),
                )
                result = r or "YouTube kanal raporu alındı."

            elif name == "analyze_screen":
                r = await loop.run_in_executor(
                    None,
                    lambda: analyze_screen(
                        args.get("query", "Ekranda ne var?"),
                        args.get("target", "active_window"),
                    ),
                )
                result = r or "Ekran analizi tamamlandı."

            elif name == "get_health_data":
                query = str(args.get("query", "all") or "all")
                r = await loop.run_in_executor(
                    None,
                    lambda: get_health_data(query),
                )
                result = r or "Sağlık verisi alınamadı."
                try:
                    self.ui.update_health_card(result, focus_ms=6000)
                except Exception:
                    pass

            elif name == "send_whatsapp_message":
                r = await loop.run_in_executor(
                    None,
                    lambda: send_whatsapp_message(
                        args.get("message", ""),
                        args.get("phone_number", ""),
                        args.get("recipient_name", ""),
                        bool(args.get("send_now", False)),
                        args.get("app_target", "auto"),
                    ),
                )
                result = r or "WhatsApp işlemi tamamlandı."

            elif name == "save_whatsapp_contact":
                r = await loop.run_in_executor(
                    None,
                    lambda: save_whatsapp_contact(
                        args.get("display_name", ""),
                        args.get("phone_number", ""),
                        args.get("aliases", ""),
                    ),
                )
                result = r or "WhatsApp kişisi kaydedildi."

            else:
                result = f"Bilinmeyen araç: {name}"

        except Exception as e:
            result = f"Hata: {e}"
            had_exception = True
            traceback.print_exc()
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        if not tool_failed and not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] RESULT {name} -> {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] Mikrofon başladı")
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT, channels=CHANNELS,
            rate=SEND_SAMPLE_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        try:
            while True:
                data = await asyncio.to_thread(
                    stream.read, CHUNK_SIZE, exception_on_overflow=False)
                try:
                    gain = self.ui.get_mic_input_gain()
                    if abs(gain - 1.0) > 0.001:
                        pcm = bytearray(data)
                        pcm_samples = memoryview(pcm).cast("h")
                        for i in range(len(pcm_samples)):
                            v = int(pcm_samples[i] * gain)
                            if v > 32767:
                                v = 32767
                            elif v < -32768:
                                v = -32768
                            pcm_samples[i] = v
                        data = bytes(pcm)

                    samples = memoryview(data).cast("h")
                    peak = max((abs(int(s)) for s in samples), default=0)
                    mic_level = min(1.0, peak / 32767.0)
                    self.ui.set_mic_level(mic_level)
                except Exception:
                    self.ui.set_mic_level(0.0)
                with self._speaking_lock:
                    jarvis_speaking = self._is_speaking
                if not jarvis_speaking and not self.ui.muted and not self._paused:
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
        except Exception as e:
            print(f"[JARVIS] Mikrofon hatası: {e}")
            raise
        finally:
            stream.close()

    async def _receive_audio(self):
        print("[JARVIS] Veri alımı başladı")
        out_buf, in_buf = [], []
        output_noise = False
        output_noise_samples = []
        try:
            while True:
                async for response in self.session.receive():
                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)
                        self._awaiting_response = False

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            raw_txt = sc.output_transcription.text.strip()
                            if raw_txt:
                                txt, had_noise = self._clean_transcript_text(raw_txt)
                                if had_noise:
                                    output_noise = True
                                    if len(output_noise_samples) < 4:
                                        output_noise_samples.append(raw_txt)
                                if txt:
                                    out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                txt = self._normalize_turkish_transcript(txt)
                                in_buf.append(txt)
                                self.ui.mark_user_activity(True)
                                self._awaiting_response = False

                        if sc.turn_complete:
                            self.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                full_in = self._normalize_turkish_transcript(full_in)
                                self.ui.write_log(f"Siz: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"JARVIS: {full_out}")
                                self._awaiting_response = False
                                if output_noise_samples:
                                    self.ui.write_debug(
                                        "Kısmen filtrelenen ses transkripti: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                            elif output_noise:
                                fallback_msg = "Anlayamadım, tekrar eder misiniz?"
                                self.ui.write_log(f"JARVIS: {fallback_msg}")
                                if not self.ui.muted:
                                    try:
                                        tts_actions.speak_text(fallback_msg)
                                    except Exception:
                                        pass
                                if output_noise_samples:
                                    self.ui.write_debug(
                                        "Filtrelenen ham transcript: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                                self.ui.set_state("LISTENING")
                            out_buf = []
                            output_noise = False
                            output_noise_samples = []

                    if response.tool_call:
                        self._awaiting_response = False
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] CALL {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses)

        except Exception as e:
            msg = str(e or "")
            benign_close = (
                ("1000 None" in msg)
                or ("ConnectionClosedOK" in msg)
                or ("1011 None" in msg)
                or ("Internal error encountered" in msg)
            )
            if benign_close:
                print("[JARVIS] Alım akışı geçici olarak kapandı. Yeniden bağlanılacak.")
                raise RuntimeError("SESSION_CLOSED_OK")
            print(f"[JARVIS] Alım hatası: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] Ses çalma başladı")
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT, channels=CHANNELS,
            rate=RECV_SAMPLE_RATE, output=True,
        )
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=AUDIO_IDLE_RESET_SECONDS,
                    )
                except asyncio.TimeoutError:
                    # Ses çıkışı durduysa speaking state'ini sıfırla ki mikrofon tekrar açılsın.
                    self.set_speaking(False)
                    continue
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] Ses hatası: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=get_api_key(),
            http_options={"api_version": "v1alpha"}
        )

        while True:
            # Duraklatılmışsa bağlanma, bekle
            if self._paused:
                await asyncio.sleep(1)
                continue

            try:
                print("[JARVIS] Bağlanıyor...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)

                    print("[JARVIS] Bağlandı.")
                    self.ui.set_state("LISTENING")
                    self._awaiting_response = False
                    self._watchdog_reconnect_inflight = False
                    self.ui.write_log("SYS: JARVIS hazır. Dinliyorum...")
                    try:
                        summary = await asyncio.get_event_loop().run_in_executor(
                            None, get_welcome_health_summary
                        )
                        if summary:
                            self.ui.update_health_card(summary, focus_ms=4500)
                    except Exception:
                        pass
                    if self._pending_voice_announcement:
                        announce_voice = self._pending_voice_announcement
                        self._pending_voice_announcement = ""
                        await self.session.send_client_content(
                            turns={
                                "parts": [
                                    {
                                        "text": (
                                            f"Sadece tek bir kısa cümle söyle: "
                                            f"'Ses değiştirildi. Aktif ses: {announce_voice}.' "
                                            "Bunun dışında hiçbir şey söyleme."
                                        )
                                    }
                                ]
                            },
                            turn_complete=True,
                        )

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._watchdog())

            except Exception as e:
                err_msg = str(e or "")
                benign_close = (
                    "SESSION_CLOSED_OK" in err_msg
                    or "1000 None" in err_msg
                    or "ConnectionClosedOK" in err_msg
                    or "1011 None" in err_msg
                    or "Internal error encountered" in err_msg
                )
                print(f"[JARVIS] Hata: {e}")
                if not benign_close:
                    traceback.print_exc()
                self.set_speaking(False)
                if benign_close:
                    self.ui.write_log("SYS: Oturum yenileniyor...")
                    self.ui.set_state("THINKING")
                elif self._suppress_next_disconnect_error:
                    self._suppress_next_disconnect_error = False
                    self.ui.write_log("SYS: Ses profili güncellendi. Yeniden bağlanıyor...")
                    self.ui.set_state("THINKING")
                else:
                    self.ui.write_log(f"ERR: JARVIS bağlantısı kesildi veya internete ulaşılamıyor - {e}")
                    self.ui.set_state("ERROR")
                self._awaiting_response = False
                self._watchdog_reconnect_inflight = False
                print("[JARVIS] 3 saniye sonra yeniden bağlanıyor...")
                await asyncio.sleep(3)


def main():
    if os.environ.get("TERM_PROGRAM") == "vscode":
        print("[JARVIS] VS Code içinden başlatıldı.")

    ui = JarvisUI()

    def runner():
        ui.wait_for_api_key()
        try:
            tts_actions.VOICE = str(get_app_config_value("voice", "Charon") or "Charon")
        except Exception:
            pass
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\nKapatılıyor...")

    threading.Thread(target=runner, daemon=True).start()
    try:
        ui.root.mainloop()
    finally:
        print("[JARVIS] UI mainloop sonlandı.")


if __name__ == "__main__":
    main()



