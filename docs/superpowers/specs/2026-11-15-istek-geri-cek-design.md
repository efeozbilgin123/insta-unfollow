# Bekleyen Instagram takip isteklerini geri çeken Windows uygulaması — Tasarım

## Amaç ve neden

Kullanıcının Instagram hesabından gönderdiği ama henüz kabul edilmemiş **tüm** takip isteklerini
geri çeken bir program. Program, bilgisayar bilgisi çok az olan bir arkadaşa dağıtılacak.
Bu yüzden en önemli ölçüt **kafa karıştırmaması**: indir → çift tıkla → Instagram'a gir → onayla → bekle.

## Hedefler

- Windows 10/11'de tek bir `.exe` dosyası. Kurulum yok, ayar yok.
- Tek pencere, tüm metinler Türkçe ve sade.
- Şifre programa hiç girilmez. Giriş Instagram'ın kendi sayfasında, kullanıcının kendisi tarafından yapılır.
- Kesintiye dayanıklı: kapatılırsa ya da Instagram yavaşla derse, tekrar açılınca kaldığı yerden devam eder.
- Kabul edilmiş bir takibi **asla** bozmaz (gerçek bir arkadaşı takipten çıkarmaz).

## Hedef dışı

- macOS veya Linux desteği.
- Takipten çıkma, takipçi temizleme gibi başka özellikler.
- Birden fazla hesabı aynı anda yönetmek.
- Chrome mağazası veya kod imzalama sertifikası.

## Başarısızlık sayılan durumlar (çalışsa bile)

- Kullanıcıdan terminal, konsol veya ayar dosyası kullanmasını istemek.
- Hesabın Instagram tarafından kilitlenmesine ya da uzun süre engellenmesine yol açacak hızda çalışmak.
- Kabul edilmiş bir takibi bozmak.
- Hata olduğunda İngilizce veya teknik bir mesajla kapanmak.

## Kısıtlar

- Instagram'ın bekleyen giden istekleri listeleyen resmi bir API'si yok.
  Güvenilir tek kaynak "Bilgilerini indir" verisi. İçinde `pending_follow_requests` ve
  `recent_follow_requests` dosyaları var.
- Bu verinin hazırlanması Instagram tarafında dakikalar ile saatler sürebiliyor ve indirme linki e-postayla geliyor.
  Bu adımı program yapamaz, kullanıcıya rehberlik eder.
- Instagram hızlı işlem yapan hesapları geçici olarak engelliyor. İşlem yavaş ve rastgele aralıklarla yapılmalı.
- Geliştirme ortamında gerçek bir Instagram hesabı yok. Instagram'a özgü ayrıntılar (endpoint, header)
  ilk gerçek denemede doğrulanacak.

## Değerlendirilen yaklaşımlar

1. **Çift tıklanan masaüstü uygulaması (seçilen).** Program bilgisayardaki Microsoft Edge'i kendi profiliyle açar.
   Kullanıcı Instagram'a normal giriş yapar, işlemler o oturumla yapılır.
   Artıları: kurulum yok, şifre programa girmez. Eksileri: imzasız `.exe` için Windows "Bilinmeyen yayıncı"
   uyarısı çıkar, bir kez "Ek bilgi → Yine de çalıştır" denmesi gerekir.
2. **Tarayıcı eklentisi.** Mağaza dışından kurulum geliştirici modu ister, mağaza ise ücretli ve incelemeli.
   Hedef kullanıcı için fazla karmaşık.
3. **Konsola kod yapıştırma.** Chrome'un yapıştırma uyarıları ve konsol hedef kullanıcıyı takar.

Kullanıcı 1'i seçti. Arkadaşın bilgisayarı Windows.

## Kullanıcının karar verdiği kısımlar

- Masaüstü uygulaması, yalnızca Windows.

## Tasarım (benim kararlarım — itiraz edilebilir)

### Akış (kullanıcının gördüğü)

1. **Hoş geldin ekranı.** "Bu program, Instagram'da gönderdiğin ama kabul edilmemiş takip isteklerini geri çeker."
   Altında iki büyük buton:
   - "Instagram verimi zaten indirdim (ZIP dosyam var)"
   - "Henüz indirmedim, nasıl yapılır göster"
2. **Rehber ekranı (indirmediyse).** Resimli ve numaralı adımlar. Edge'de doğru sayfayı açan bir buton
   ("Bilgilerini indir" sayfası). Vurgulanan üç seçenek: **Biçim: JSON**, **Tarih aralığı: Tüm zamanlar**,
   **Bilgi türü: yalnızca "Takipçiler ve takip edilenler"** (dosya küçük olsun, çabuk gelsin).
   Son satır: "E-postana gelen linkten ZIP'i indir, sonra bu programı tekrar aç."
3. **Dosya seçme.** "ZIP dosyanı seç" butonu (Windows dosya seçici). İndirilenler klasöründe adı uyan bir ZIP
   varsa, program onu kendisi önerir. ZIP'i açmak gerekmez.
4. **Giriş.** Edge penceresi Instagram'ı açar. Program penceresinde
   "Açılan pencerede Instagram'a giriş yap, sonra buraya dön" yazar. Giriş algılanınca kendiliğinden ilerler.
   Profil kalıcı olduğundan sonraki açılışlarda tekrar giriş gerekmez.
   *(Benim kararım)* ZIP'in hangi hesaba ait olduğu güvenilir şekilde anlaşılamıyor
   (yalnızca "Takipçiler ve takip edilenler" seçilince profil bilgisi gelmiyor). Bu yüzden otomatik eşleştirme yok.
   Onay ekranında giriş yapılan hesap büyük harfle gösterilir ve kullanıcıya sorulur (bkz. 5).
5. **Onay.** "Giriş yapılan hesap: **@kullaniciadi**. Bu senin hesabın mı?" sorusu, ardından "128 kişiye bekleyen istek bulundu. Geri çekilsin mi? Bu işlem yaklaşık 3 saat sürebilir,
   bilgisayar açık kalmalı." Butonlar: "Evet, başlat" / "Hayır".
6. **İlerleme.** Büyük ilerleme çubuğu ("37 / 128"), o anda işlenen kullanıcı adı, tahmini kalan süre
   ve "Durdur" butonu. Kapatılırsa kaldığı yer kaydedilir.
7. **Bitiş.** Özet: "120 istek geri çekildi. 5 kişi seni zaten kabul etmişti (dokunulmadı).
   3 hesap artık yok." Detay listesi isteyen için "Listeyi göster".

Tek bir program penceresi var (konsol yok). Edge penceresi yalnızca giriş ve işlem için kullanılıyor.

### Liste kaynağı ve okuma

- ZIP içinde adında `follow_requests` geçen tüm dosyalar aranır (`pending_follow_requests.*`,
  `recent_follow_requests.*`). Hem **JSON hem HTML** biçimi okunur. Kullanıcı HTML seçtiyse de çalışsın.
- Kullanıcı adı alanları savunmacı okunur: `string_list_data[].value` → `title` → `href`'in son parçası.
- Kullanıcı adları birleştirilir ve tekrarlar ayıklanır. Bu güvenli, çünkü her biri işlemden önce yeniden kontrol edilir.
- ZIP'te bu dosya yoksa: "Bu dosyada takip istekleri yok. İndirirken 'Takipçiler ve takip edilenler'i
  seçtiğinden emin ol" mesajı ve rehbere dönüş.

### Her kullanıcı için güvenlik kontrolü (en kritik kural)

ZIP bir anlık görüntü. Bazı istekler o arada kabul edilmiş olabilir. Her kullanıcı adı için:

1. Profili sorgula. Kullanıcı yoksa (404) "hesap yok" olarak işaretle ve geç.
2. İlişki durumuna bak. **Yalnızca "istek bekliyor" ise** geri çek.
   Takip ediliyorsa (kabul edilmiş) veya hiçbir ilişki yoksa dokunma.
3. Geri çektikten sonra durumu yeniden kontrol et. Gerçekten iptal olmadıysa "başarısız" olarak işaretle.

Bu kontrol aynı zamanda gerçek hesap olmadan doğrulamanın yolu: program her işlemin gerçekten tuttuğunu kendisi görür.

*(Benim kararım)* Instagram'da istek geri çekme büyük olasılıkla takipten çıkmayla aynı çağrı. Kontrol ile çağrı arasında
istek kabul edilirse (saniyeler içinde, çok düşük olasılık) kişi takipten çıkmış olur. Bu pencere, kontrol çağrıdan
hemen önce yapılarak en aza indirilir. Bu durum sonradan güvenilir şekilde ayırt edilemez (her iki durumda da
sonuç "takip yok"), bu yüzden ayrı bir kategori yok. Geri çekme sonrası kişi hâlâ takip ediliyor görünürse sonuç
"başarısız" olur ve otomatik yeniden deneme veya yeniden takip yapılmaz.

### Hız ve engellenme

- İşlemler arasında rastgele bekleme (başlangıç değeri 40–90 sn) ve saatlik üst sınır (başlangıç değeri 60).
  Kesin değerler ayar modülünde tutulur.
- 429, `feedback_required`, `checkpoint` veya benzeri bir yanıtta işlem hemen durur.
  "Instagram biraz yavaşlamanı istedi. Programı yarın tekrar aç, kaldığı yerden devam eder."
  Agresif yeniden deneme yok.
- Oturum düşerse giriş adımına geri dönülür.

### Kalıcılık

- `%LOCALAPPDATA%\IstekGeriCek\` klasörü: Edge profili, ilerleme dosyası (kullanıcı adı → durum) ve günlük dosyası.
- Program yeniden açıldığında yarım iş varsa "Kaldığın yerden devam edelim mi? (37 / 128)" diye sorar.
  ZIP'in tekrar seçilmesi gerekmez.

### Teknik seçimler

- Python, arayüz Tkinter (paketlemesi kolay, tek pencere), tarayıcı Playwright ile
  `channel="msedge"` (Windows'ta Edge hazır, Chromium paketlenmez, dosya küçük kalır)
  ve kalıcı profil (`launch_persistent_context`).
- Instagram çağrıları sayfa içinden `fetch` ile yapılır, böylece oturum çerezleri ve CSRF doğal olarak kullanılır.
- **Instagram'a özgü her şey tek bir modülde** (`instagram_api`): profil sorgusu, ilişki durumu, geri çekme
  endpoint'i, header'lar, app id ve hata kodu yorumlama. Bunlar hafızadan geliyor ve
  **ilk gerçek denemede doğrulanacak**. Düzeltme tek yerden yapılır.
- Paketleme: GitHub Actions'ta `windows-latest` üzerinde PyInstaller ile tek dosya, `--noconsole`.
  Repo herkese açık. Çıktı GitHub Release olarak yayınlanır, arkadaşa giriş gerektirmeyen tek bir indirme linki verilir.
- CI'da duman testi: derlenen `.exe` test modunda çalıştırılır. Edge açılır, bir sayfa yüklenir, kapanır.
  Bu, Playwright'ın gerçekten pakete girdiğini kanıtlar.
- Testler: ZIP okuyucu için JSON ve HTML örnek verileriyle birim testleri, akış mantığı için
  sahte (mock) Instagram katmanıyla testler.

### Dağıtım için kısa kılavuz

`.exe` ile birlikte tek sayfalık, resimli ve Türkçe bir "Nasıl kullanılır" belgesi.
Windows'un "Bilgisayarınız korundu" uyarısında "Ek bilgi → Yine de çalıştır" adımı ekran görüntüsüyle anlatılır.

## Test ve güvenli ilk çalıştırma (kullanıcıyla kararlaştırıldı)

- **Deneme hesaplarıyla test:** Kullanıcı iki deneme hesabı açacak. Hesap A istek gönderir, Hesap B gizli hesaptır
  ve isteklerden birini kabul eder. Program arkadaşa verilmeden önce bu hesaplarla adım adım denenir.
  Hata çıkarsa kullanıcı rapor dosyasını iletir, düzeltilmiş sürüm çıkarılır.
- **Güvenli ilk çalıştırma (her zaman var):** Bir hesapta ilk çalıştırmada program önce hiçbir şeyi
  değiştirmeden yalnızca kontrol eder ("128 bekleyen, 5 kabul edilmiş, 3 hesap yok"). Sonra tek bir isteği geri çeker
  ve tuttuğunu doğrular. Ancak ondan sonra tümüne geçer. Kullanıcıya bu tek bir "Başlat" gibi görünür,
  ara adımlar ilerleme ekranında yazıyla gösterilir.
- **Raporlama:** Bitiş ve hata ekranlarında "Raporu kaydet" butonu, Masaüstüne tek bir metin dosyası yazar
  (şifre ya da çerez içermez). Pencerede sürüm numarası görünür.

## Geliştiriciye bırakılanlar

- Modül yapısı, dosya adları ve test çatısı.
- Bekleme süreleri ile saatlik sınırın ince ayarı (yukarıdaki değerler başlangıç noktası).
- Arayüzün görsel detayları (yazı tipleri, renkler), yukarıdaki akışa uyduğu sürece.
- Edge'in bulunamadığı nadir durumda gösterilecek mesaj (Edge'i yükleme linki).

## İlk gerçek denemede doğrulanacaklar

- Geri çekme, profil sorgusu ve ilişki durumu endpoint'leri ile gerekli header'lar.
- Veri indirme ZIP'indeki dosya adları ve JSON/HTML yapısı.
- Engellenme yanıtlarının tam biçimi.
