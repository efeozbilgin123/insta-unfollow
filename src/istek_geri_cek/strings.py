"""Kullanıcının gördüğü bütün metinler."""

TITLE = "İstek Geri Çek — sürüm {version}"

WELCOME_TITLE = "Takip isteklerini geri çek"
WELCOME_BODY = ("Bu program, Instagram'da gönderdiğin ama kabul edilmemiş takip isteklerini geri çeker.\n\n"
                "Kabul edilmiş takiplere dokunmaz. Şifreni programa yazmazsın.")
BTN_HAVE_ZIP = "Instagram verimi zaten indirdim (ZIP dosyam var)"
BTN_NEED_GUIDE = "Henüz indirmedim, nasıl yapılır göster"
RESUME_Q = "Yarım kalan bir işin var: {done} / {total}.\nKaldığın yerden devam edelim mi?"
BTN_RESUME = "Evet, devam et"
BTN_NEW = "Hayır, baştan başla"

GUIDE_TITLE = "Instagram verini indir"
GUIDE_STEPS = [
    "Aşağıdaki büyük butona bas. Instagram'ın \"Bilgilerini indir\" sayfası açılır (gerekirse giriş yap).",
    "\"Bilgilerini indir veya aktar\" → \"Bilgilerinin bir kısmı\" seç.",
    "Listeden YALNIZCA \"Takipçiler ve takip edilenler\" kutusunu işaretle.",
    "\"Cihaza indir\" seç. Ayarlarda:  Tarih aralığı = TÜM ZAMANLAR,  Biçim = JSON.",
    "\"Dosya oluştur\"a bas. Hazır olunca e-postana link gelir (birkaç dakika – birkaç saat).",
    "Linkten ZIP dosyasını indir (açma, olduğu gibi kalsın). Sonra bu programı tekrar aç.",
]
BTN_OPEN_DYI = "Bilgilerini indir sayfasını aç"
DYI_URL = "https://accountscenter.instagram.com/info_and_permissions/dyi/"
BTN_BACK = "Geri"
BTN_CLOSE = "Kapat"

PICK_TITLE = "ZIP dosyanı seç"
PICK_BODY = "Instagram'dan indirdiğin ZIP dosyasını seç. Açmana gerek yok."
PICK_FOUND = "İndirilenler klasöründe bunu buldum:\n{name}"
BTN_USE_FOUND = "Bu dosyayı kullan"
BTN_BROWSE = "Başka dosya seç…"
EXPORT_ERRORS = {
    "not_zip": "Bu bir ZIP dosyası değil ya da bozuk. Instagram'dan gelen ZIP'i olduğu gibi seç.",
    "no_requests": ("Bu dosyada takip istekleri yok.\nİndirirken \"Takipçiler ve takip edilenler\"i "
                    "seçtiğinden emin ol."),
    "empty": "Bu dosyaya göre bekleyen takip isteğin yok. Yapılacak bir şey kalmadı. 🎉",
}

LOGIN_TITLE = "Instagram'a giriş yap"
LOGIN_BODY = ("Açılan Edge penceresinde Instagram'a her zamanki gibi giriş yap.\n\n"
              "Giriş yapınca bu pencere kendiliğinden devam eder.")
OPENING = "Edge açılıyor…"
EDGE_MISSING = ("Bu bilgisayarda Microsoft Edge bulunamadı.\n"
                "Edge'i yükleyip programı tekrar aç:\nhttps://www.microsoft.com/edge")

CHECKING = "Kontrol ediliyor… {done} / {total}\n(Henüz hiçbir şey değişmiyor.)"

CONFIRM_ACCOUNT = "Giriş yapılan hesap:  @{account}\nBu senin hesabın mı?"
CONFIRM_COUNTS = ("{pending} kişiye bekleyen istek bulundu.\n"
                  "{accepted} kişi isteğini zaten kabul etmiş (dokunulmayacak).\n"
                  "{not_found} hesap artık yok.\n\n"
                  "Bu işlem yaklaşık {hours} sürebilir. Bilgisayar açık ve internete bağlı kalmalı.")
CONFIRM_FAILED = "{failed} kişi kontrol edilemedi (bunlara dokunulmayacak)."
CONFIRM_NONE = "Bekleyen isteğin yok. Yapılacak bir şey kalmadı. 🎉"
BTN_START = "Evet, başlat"
BTN_NO = "Hayır"
WRONG_ACCOUNT = ("Edge penceresinde Instagram'dan çıkış yap, doğru hesapla giriş yap,\n"
                 "sonra programı kapatıp tekrar aç.")

PROGRESS_TITLE = "İstekler geri çekiliyor"
PROGRESS_LINE = "{done} / {total}"
PROGRESS_USER = "Şu an: @{username}"
PROGRESS_LEFT = "Tahmini kalan süre: {left}"
PROGRESS_NOTE = "Bilgisayarı kapatma. Kapatırsan, programı tekrar açınca kaldığı yerden devam eder."
TRIAL_OK = "İlk istek başarıyla geri çekildi ve doğrulandı. Diğerlerine geçiliyor."
WAITING = "Instagram'ı yormamak için kısa bir mola: {left}"
BTN_STOP = "Durdur"

DONE_TITLE = "Bitti!"
DONE_SUMMARY = ("{cancelled} istek geri çekildi.\n"
                "{accepted} kişi seni zaten kabul etmişti (dokunulmadı).\n"
                "{not_found} hesap artık yok.\n"
                "{failed} istek geri çekilemedi.")
BTN_SHOW_LIST = "Listeyi göster"
BTN_SAVE_REPORT = "Raporu kaydet"
REPORT_SAVED = "Rapor kaydedildi:\n{path}"
BTN_RETRY = "Tekrar dene"

STOP_MESSAGES = {
    "rate_limited": "Instagram biraz yavaşlamanı istedi. Programı yarın tekrar aç, kaldığı yerden devam eder.",
    "login": "Instagram oturumun kapandı. Edge penceresinde tekrar giriş yap, program kendiliğinden devam eder.",
    "network": "İnternet bağlantısı koptu. Bağlantını kontrol edip \"Tekrar dene\"ye bas.",
    "user": "Durduruldu. Programı tekrar açınca kaldığı yerden devam eder.",
    "unexpected": ("Instagram beklenmeyen bir yanıt verdi, güvenlik için durduruldu. Hiçbir şey bozulmadı.\n"
                   "Lütfen \"Raporu kaydet\"e bas ve raporu programı sana verene gönder."),
    "trial_failed": ("İlk deneme isteği geri çekilemedi, bu yüzden hiçbir şeye devam edilmedi.\n"
                     "Lütfen \"Raporu kaydet\"e bas ve raporu programı sana verene gönder."),
}
BROWSER_CLOSED = "Edge penceresi kapandı. Programı kapatıp tekrar aç; kaldığı yerden devam eder."
ALREADY_RUNNING = "Program zaten açık. Diğer pencereyi kullan (görev çubuğuna bak)."
UNEXPECTED = ("Beklenmeyen bir sorun oldu. Programı kapatıp tekrar aç; kaldığı yerden devam eder.\n"
              "Tekrar olursa \"Raporu kaydet\"e bas ve raporu programı sana verene gönder.")

OUTCOME_LABELS = {
    "CANCELLED": "Geri çekildi",
    "ACCEPTED": "Kabul etmiş (dokunulmadı)",
    "NO_REQUEST": "Bekleyen istek yoktu",
    "NOT_FOUND": "Hesap artık yok",
    "FAILED": "Başarısız",
}


def duration(seconds: float) -> str:
    m = max(1, int(round(seconds / 60)))
    if m < 60:
        return f"{m} dakika"
    h, m = divmod(m, 60)
    return f"{h} saat {m} dakika" if m else f"{h} saat"
