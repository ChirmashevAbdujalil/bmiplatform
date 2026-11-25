# BMI Platforma

**Bitiruv malakaviy ishlari (BMI) va ilmiy faoliyatni raqamlashtirish tizimi** — Python / Django.

Talabalarga diplom ishi mavzusi va ilmiy rahbarni biriktirish, kafedra → dekanat → ta’lim sifati bo‘limi
o‘rtasidagi elektron kelishuv, QR-kodli tasdiqlangan hujjatlar, o‘qituvchilarning talabalar bilan
hammualliflikdagi ilmiy ishlarini markazlashgan holda baholash va statistikani bitta platformada jamlaydi.

## Ishga tushirish

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # ixtiyoriy: demo ma’lumotlar (parol: demo12345)
python manage.py runserver
```

Brauzerda: <http://127.0.0.1:8000>. Haqiqiy ishga tushirish uchun `python manage.py createsuperuser`
bilan administrator yarating va **Tuzilma** bo‘limida fakultet/kafedralarni kiriting.

Testlar: `python manage.py test`

### Demo hisoblar (`seed_demo` dan so‘ng, parol `demo12345`)

| Login | Rol |
|---|---|
| `admin` | Administrator (tuzilma, boshqaruv hisoblari, admin panel) |
| `sifat` | Ta’lim sifati bo‘limi |
| `dekanat_atf`, `dekanat_iqf` | Dekanat |
| `kafedra_di`, `kafedra_att`, `kafedra_ri` | Kafedra (mudir) |
| `di.teacher1` … `di.teacher4` | O‘qituvchi |
| `3112300101` … | Talaba (login = HEMIS ID) |

## Rollar va imkoniyatlar

| Rol | Nima qiladi |
|---|---|
| **Administrator** | Fakultet, kafedra, yo‘nalishlarni va kafedra/dekanat/sifat hisoblarini yaratadi |
| **Kafedra** | O‘qituvchilarni Word orqali biriktiradi; talabalarga mavzu va ilmiy rahbarni (qo‘lda yoki Word orqali) biriktiradi va kelishuvga yuboradi; kafedra o‘qituvchilarining ilmiy ishlarini baholaydi |
| **Dekanat** | Talabalarni Word orqali biriktiradi; fakultet bo‘yicha mavzularni kelishadi/qaytaradi; ilmiy ishlarni baholaydi |
| **Ta’lim sifati bo‘limi** | Barcha mavzularni kelishadi/qaytaradi; ilmiy ishlarni baholaydi; baholash mezonlarini boshqaradi; harakatlar jurnali |
| **O‘qituvchi** | Profilida biriktirilgan talabalari; talabalar bilan birgalikdagi maqola, tezis va boshqa ishlarini yuklaydi; markazlashgan umumiy ballini, reytingini ko‘radi; ilmiy faoliyat ma’lumotnomasini (Word) yuklab oladi |
| **Talaba** | Profilida ilmiy rahbari, mavzusi va tasdiqlangan hujjati; hammualliflikdagi tasdiqlangan ilmiy ishlari va ballari |

## Asosiy jarayonlar

**BMI mavzusi:** `Loyiha` → (kafedra yuboradi) → `Kelishuvda` → dekanat **va** ta’lim sifati bo‘limi kelishadi →
`Tasdiqlangan` (QR-kodli Word hujjat shakllanadi, talaba profilida paydo bo‘ladi).
Biror tomon izoh bilan qaytarsa → `Qaytarilgan` → kafedra tuzatib qayta yuboradi.
Ro‘yxatda ommaviy belgilab yuborish/kelishish mumkin.

**Ilmiy ish:** o‘qituvchi yuklaydi → kafedra mudiri, dekanat va ta’lim sifati bo‘limi mezonlar bo‘yicha
alohida ball qo‘yadi → uchalasi kelishgach yakuniy ball = o‘rtacha ball; ish tasdiqlanadi va ball o‘qituvchi hamda
hammuallif talabalar profilida ko‘rinadi. Qaytarilsa — o‘qituvchi tuzatib qayta yuboradi (baholar yangidan).

**Yuklab olish:** tasdiqlangan mavzular ro‘yxati **fakultet / kafedra / yo‘nalish / kurs / guruh / ilmiy rahbar /
o‘quv yili** kesimida Word (rasmiy ro‘yxat) yoki Excel ko‘rinishida. Talabalar ro‘yxati ham Excel’ga eksport qilinadi.

**Hujjatni tekshirish:** `/tekshirish/<kod>/` — ochiq sahifa, QR-kod shu manzilga olib boradi.
Hujjatdagi manzil `BMI_SITE_URL` muhit o‘zgaruvchisidan olinadi.

## Word import formatlari

Har bir importda jadvalning birinchi qatori sarlavha; ustunlar **sarlavhadagi so‘zlar bo‘yicha** aniqlanadi
(tartib muhim emas). Namuna shablonlarni import sahifasidan yuklab olish mumkin.

| Import | Kim | Ustunlar |
|---|---|---|
| O‘qituvchilar | Kafedra | №, F.I.Sh., Lavozimi, Ilmiy darajasi, Ilmiy unvoni, Telefon, E-mail, Login (ixtiyoriy) |
| Talabalar | Dekanat | №, F.I.Sh., Talaba ID (HEMIS), Yo‘nalish shifri, Yo‘nalish nomi, Kurs, Guruh, Kafedra, Ta’lim shakli, Telefon |
| BMI mavzulari | Kafedra | №, Talaba F.I.Sh., Talaba ID, BMI mavzusi, Ilmiy rahbar F.I.Sh. |

Qayta import yozuvlarni takrorlamaydi — yangilaydi. Yangi hisoblar uchun login-parollar ekranda ko‘rsatiladi va
Word faylda yuklab olinadi; foydalanuvchi birinchi kirishda parolni almashtirishi shart.

## Sozlamalar (muhit o‘zgaruvchilari)

| O‘zgaruvchi | Ma’nosi |
|---|---|
| `BMI_UNIVERSITY_NAME` | Hujjatlar va sarlavhalardagi OTM nomi |
| `BMI_SITE_URL` | QR-kod uchun platforma manzili (masalan `https://bmi.univ.uz`) |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Django sozlamalari |

Barcha front-end kutubxonalar (Bootstrap 5.3, Bootstrap Icons, Chart.js, Inter shrifti) `static/vendor` ichida —
platforma internetga ulanmagan ichki tarmoqda ham to‘liq ishlaydi.

## Loyiha tuzilmasi

```
config/      — Django sozlamalari, URL’lar
core/        — tuzilma (fakultet/kafedra/yo‘nalish), bosh sahifa, statistika, bildirishnomalar,
               ruxsatlar (permissions.py), Word import (word_import.py), hujjatlar (documents.py)
accounts/    — foydalanuvchi, o‘qituvchi/talaba profillari, importlar
theses/      — BMI mavzulari va kelishuv jarayoni
research/    — ilmiy ishlar, baholash mezonlari, markazlashgan baholash
templates/   — sahifalar;  static/ — dizayn (css/main.css)
```
