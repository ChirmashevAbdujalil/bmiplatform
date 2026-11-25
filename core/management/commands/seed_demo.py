"""Platformani sinash uchun demo ma’lumotlar.

    python manage.py seed_demo          # demo ma’lumot qo‘shish
    python manage.py seed_demo --reset  # avval barcha ma’lumotlarni tozalash
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import StudentProfile, TeacherProfile, User
from core.models import AuditLog, Department, Direction, Faculty, Notification
from research.models import Criterion, Evaluation, EvaluationScore, ScientificWork
from research.services import ensure_default_criteria
from theses import services as thesis_services
from theses.models import Decision, Thesis

PASSWORD = "demo12345"

STRUCTURE = [
    ("Axborot texnologiyalari fakulteti", "ATF", [
        ("Dasturiy injiniring kafedrasi", "DI", ("60610500", "Dasturiy injiniring")),
        ("Axborot tizimlari va texnologiyalari kafedrasi", "ATT", ("60610300", "Axborot tizimlari va texnologiyalari")),
    ]),
    ("Iqtisodiyot fakulteti", "IQF", [
        ("Raqamli iqtisodiyot kafedrasi", "RI", ("60410100", "Iqtisodiyot (raqamli iqtisodiyot)")),
    ]),
]

LAST = ["Karimov", "Rahimov", "Toshpulatov", "Yusupov", "Abdullayev", "Nazarov", "Ergashev", "Sobirov", "Qodirov",
        "Mirzayev", "Xolmatov", "Saidov", "Jo‘rayev", "Hasanov", "Ismoilov", "Usmonov", "Normatov", "Aliyev"]
FIRST_M = ["Akmal", "Jasur", "Bekzod", "Sardor", "Otabek", "Diyorbek", "Javohir", "Shohruh", "Ulug‘bek", "Azizbek"]
FIRST_F = ["Dilnoza", "Madina", "Nilufar", "Sevara", "Zarina", "Gulnoza", "Kamola", "Shahnoza", "Malika", "Mohira"]
FATHER = ["Bahodir", "Anvar", "Olim", "Rustam", "Shavkat", "Ilhom", "Farhod", "Komil", "Sherzod", "Abdulla"]

TOPICS = {
    "DI": [
        "Oliy ta’lim muassasasida hujjat aylanishini avtomatlashtiruvchi veb-platforma ishlab chiqish",
        "Mashinaviy o‘qitish asosida talabalar o‘zlashtirishini bashorat qilish tizimi",
        "Mikroservis arxitekturasida onlayn to‘lov tizimini loyihalash",
        "Mobil ilova orqali shahar transporti harakatini monitoring qilish",
        "O‘zbek tilidagi matnlarni avtomatik tasniflash algoritmlarini tadqiq etish",
        "Bulutli texnologiyalar asosida masofaviy laboratoriya tizimini yaratish",
        "Kompyuter ko‘rish yordamida qishloq xo‘jaligi ekinlari kasalliklarini aniqlash",
        "Veb-ilovalar xavfsizligini avtomatik testlash vositasini ishlab chiqish",
    ],
    "ATT": [
        "Tibbiyot muassasasi uchun elektron navbat va qabul axborot tizimi",
        "Korxona ombor hisobini yurituvchi axborot tizimini ishlab chiqish",
        "Katta hajmdagi ma’lumotlarni vizuallashtirish dashboardini yaratish",
        "IoT qurilmalari yordamida xonadon energiya sarfini nazorat qilish tizimi",
        "Raqamli kutubxona uchun semantik qidiruv modulini ishlab chiqish",
        "Ta’lim muassasalarida davomatni yuzni tanish orqali qayd etish tizimi",
    ],
    "RI": [
        "Raqamli iqtisodiyot sharoitida kichik biznes subyektlarining elektron tijoratga o‘tishi",
        "Hududiy iqtisodiy rivojlanishni ekonometrik modellashtirish",
        "Bank sohasida masofaviy xizmatlar samaradorligini baholash",
        "Soliq ma’murchiligini raqamlashtirishning iqtisodiy samarasi",
        "Agroklasterlar faoliyatida raqamli texnologiyalarni joriy etish",
    ],
}

WORK_TITLES = [
    ("Ta’lim jarayonida sun’iy intellekt vositalaridan foydalanish istiqbollari", "article", "oak", "“Muhammad al-Xorazmiy avlodlari” ilmiy jurnali"),
    ("Veb-ilovalarda foydalanuvchi tajribasini baholash usullari", "thesis", "republic", "Respublika ilmiy-amaliy konferensiyasi"),
    ("Deep learning approaches for Uzbek text classification", "article", "scopus", "AIP Conference Proceedings"),
    ("Raqamli platformalarda ma’lumotlar xavfsizligini ta’minlash", "thesis", "international", "International Conference on Information Science"),
    ("Kichik biznesda elektron tijoratni rivojlantirish omillari", "article", "oak", "“Iqtisodiyot va ta’lim” jurnali"),
    ("Mobil ilovalar uchun REST API loyihalash bo‘yicha uslubiy qo‘llanma", "manual", "local", "OTM nashriyoti"),
    ("Talabalar davomatini avtomatik qayd etish dasturi", "patent", "republic", "Intellektual mulk agentligi (DGU)"),
    ("Ekonometrik modellar yordamida hududiy prognozlash", "thesis", "republic", "Yosh olimlar konferensiyasi"),
    ("IoT-based smart energy monitoring for households", "article", "international", "International Journal of Advanced Research"),
    ("Kompyuter ko‘rish texnologiyalarining agrar sohadagi tatbiqi", "article", "oak", "“Axborot texnologiyalari” jurnali"),
]


class Command(BaseCommand):
    help = "Demo ma’lumotlar bilan platformani to‘ldiradi"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Avval mavjud ma’lumotlarni o‘chirish")

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(42)
        if opts["reset"]:
            for model in (EvaluationScore, Evaluation, ScientificWork, Thesis, Notification, AuditLog,
                          StudentProfile, TeacherProfile, Direction, Department, Faculty):
                model.objects.all().delete()
            User.objects.all().delete()
        ensure_default_criteria()
        self.used_names = set()

        admin = self._user("admin", User.Role.ADMIN, "Tizim", "Administrator", superuser=True)
        sifat = self._user("sifat", User.Role.SIFAT, "Ergasheva", "Gulnora", middle="Akramovna")
        dekanats, kafedras, teachers_by_dept, students_by_dept = {}, {}, {}, {}

        sid = 3112300100
        for f_name, f_short, depts in STRUCTURE:
            faculty, _ = Faculty.objects.get_or_create(name=f_name, defaults={"short_name": f_short})
            dekanats[faculty] = self._user(f"dekanat_{f_short.lower()}", User.Role.DEKANAT, "Sultonov", "Bobur",
                                           middle="Ravshanovich", faculty=faculty)
            for d_name, d_short, (code, dir_name) in depts:
                dept, _ = Department.objects.get_or_create(faculty=faculty, name=d_name, defaults={"short_name": d_short})
                direction, _ = Direction.objects.get_or_create(
                    faculty=faculty, code=code, defaults={"name": dir_name, "department": dept})
                ln, fn, mn = self._name()
                kafedras[dept] = self._user(f"kafedra_{d_short.lower()}", User.Role.KAFEDRA, ln, fn, middle=mn,
                                            faculty=faculty, department=dept)
                teachers = []
                for i in range(4):
                    ln, fn, mn = self._name()
                    t = self._user(f"{d_short.lower()}.teacher{i + 1}", User.Role.TEACHER, ln, fn, middle=mn,
                                   faculty=faculty, department=dept)
                    TeacherProfile.objects.update_or_create(user=t, defaults={
                        "position": random.choice(["Dotsent", "Katta o‘qituvchi", "Professor", "Assistent"]),
                        "degree": random.choice(["PhD", "DSc", "", "PhD"]),
                        "academic_title": random.choice(["Dotsent", "", "Professor", ""]),
                        "max_students": 8,
                    })
                    teachers.append(t)
                teachers_by_dept[dept] = teachers
                students = []
                for i in range(len(TOPICS[d_short]) + 3):
                    sid += 1
                    ln, fn, mn = self._name(female=i % 3 == 0)
                    s = self._user(str(sid), User.Role.STUDENT, ln, fn, middle=mn, faculty=faculty, department=dept)
                    StudentProfile.objects.update_or_create(user=s, defaults={
                        "student_id": str(sid), "direction": direction, "course": 4,
                        "group_name": f"{d_short}-4{1 + i % 2}-22",
                    })
                    students.append(s)
                students_by_dept[dept] = students

        # BMI mavzulari: turli holatlarda
        for dept, students in students_by_dept.items():
            kafedra = kafedras[dept]
            dekanat = dekanats[dept.faculty]
            topics = TOPICS[dept.short_name]
            for i, (student, topic) in enumerate(zip(students, topics)):
                if Thesis.objects.filter(student=student).exists():
                    continue
                thesis = Thesis.objects.create(student=student, topic=topic, department=dept, created_by=kafedra,
                                               supervisor=teachers_by_dept[dept][i % 4])
                thesis_services._log(thesis, kafedra, "Mavzu va ilmiy rahbar biriktirildi")
                stage = i % 5
                if stage == 0:
                    continue  # loyiha
                thesis_services.send_for_approval(thesis, kafedra)
                if stage == 1:
                    continue  # kelishuvda
                if stage == 4:
                    thesis_services.decide(thesis, dekanat, Decision.RETURNED,
                                           "Mavzu nomini aniqlashtiring va yo‘nalish standartiga moslang.")
                    continue
                thesis_services.decide(thesis, dekanat, Decision.APPROVED, "")
                thesis_services.decide(thesis, sifat, Decision.APPROVED, "")

        # Ilmiy ishlar va baholar
        criteria = list(Criterion.objects.filter(is_active=True))
        now = timezone.now()
        for dept, teachers in teachers_by_dept.items():
            for t_idx, teacher in enumerate(teachers):
                supervised = list(User.objects.filter(thesis__supervisor=teacher))
                for k in range(random.randint(1, 4)):
                    title, wtype, level, pub = random.choice(WORK_TITLES)
                    work = ScientificWork(
                        teacher=teacher, title=title, work_type=wtype, level=level, publication=pub,
                        publication_date=date.today() - timedelta(days=random.randint(10, 330)),
                        annotation="Ushbu ishda mavzuning dolzarbligi asoslab berilgan va amaliy tavsiyalar ishlab chiqilgan.",
                    )
                    work.file.save(f"demo_{teacher.username}_{k}.pdf", ContentFile(b"%PDF-1.4\n% demo\n"), save=False)
                    work.save()
                    ScientificWork.objects.filter(pk=work.pk).update(
                        submitted_at=now - timedelta(days=random.randint(5, 330)))
                    if supervised:
                        work.students.set(random.sample(supervised, min(len(supervised), random.randint(1, 2))))
                    roll = random.random()
                    if roll < 0.2:
                        continue  # baholashda (hech kim baholamagan)
                    evaluators = [("kafedra", kafedras[dept]), ("dekanat", dekanats[dept.faculty]), ("sifat", sifat)]
                    if roll < 0.35:
                        evaluators = evaluators[:random.randint(1, 2)]
                    base = {"scopus": .9, "international": .8, "oak": .75, "republic": .65, "local": .55}[level]
                    for role, user in evaluators:
                        returned = roll > 0.93 and role == "dekanat"
                        ev = Evaluation.objects.create(
                            work=work, role=role, evaluator=user,
                            decision=Evaluation.Decision.RETURNED if returned else Evaluation.Decision.APPROVED,
                            comment="Nashr tasdiqlovchi sahifa ilova qilinmagan." if returned else "")
                        total = Decimal("0")
                        for c in criteria:
                            score = Decimal(str(round(c.max_score * min(1, base + random.uniform(-.12, .12)) * 2) / 2))
                            EvaluationScore.objects.create(evaluation=ev, criterion=c, score=score)
                            total += score
                        ev.total = total
                        ev.save()
                    work.recompute()

        AuditLog.objects.create(user=admin, action="Demo ma’lumotlar yaratildi")
        self.stdout.write(self.style.SUCCESS("Demo ma’lumotlar tayyor. Barcha hisoblar paroli: " + PASSWORD))
        self.stdout.write("  admin        — administrator")
        self.stdout.write("  sifat        — ta’lim sifati bo‘limi")
        self.stdout.write("  dekanat_atf  — Axborot texnologiyalari fakulteti dekanati")
        self.stdout.write("  dekanat_iqf  — Iqtisodiyot fakulteti dekanati")
        self.stdout.write("  kafedra_di   — Dasturiy injiniring kafedrasi")
        self.stdout.write("  kafedra_att  — Axborot tizimlari kafedrasi")
        self.stdout.write("  di.teacher1  — o‘qituvchi")
        self.stdout.write("  3112300101   — talaba (login = HEMIS ID)")

    def _name(self, female=False):
        for _ in range(200):
            last = random.choice(LAST)
            first = random.choice(FIRST_F if female else FIRST_M)
            father = random.choice(FATHER)
            if female:
                last = last + "a"
                middle = father + " qizi"
            else:
                middle = father + "ovich" if not father.endswith(("a", "o")) else father + "yevich"
            if (last, first) not in self.used_names:
                self.used_names.add((last, first))
                return last, first, middle
        return last, first, middle

    def _user(self, username, role, last, first, middle="", faculty=None, department=None, superuser=False):
        user, _ = User.objects.get_or_create(username=username)
        user.role = role
        user.last_name, user.first_name, user.middle_name = last, first, middle
        user.faculty, user.department = faculty, department
        user.is_staff = user.is_superuser = superuser
        user.must_change_password = False
        user.set_password(PASSWORD)
        user.save()
        return user
