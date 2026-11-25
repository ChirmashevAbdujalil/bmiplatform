import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from docx import Document

from accounts.models import User
from research.models import Criterion, ScientificWork
from theses.models import Thesis


def make_docx(headers, rows):
    doc = Document()
    table = doc.add_table(rows=1, cols=len(headers))
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = v
    buf = io.BytesIO()
    doc.save(buf)
    return SimpleUploadedFile("data.docx", buf.getvalue())


class PlatformTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0, stdout=io.StringIO())

    def login(self, username):
        self.client.force_login(User.objects.get(username=username))

    def test_pages_render_for_every_role(self):
        thesis = Thesis.objects.filter(status=Thesis.Status.APPROVED, department__short_name="DI").first()
        work = ScientificWork.objects.filter(teacher__department__short_name="DI").first()
        teacher = User.objects.get(username="di.teacher1")
        student = thesis.student
        common = [reverse("research:list"), reverse("accounts:my_profile"), reverse("core:notifications"),
                  reverse("accounts:password_change")]
        manager = common + [
            reverse("core:dashboard"), reverse("core:statistics"), reverse("accounts:teacher_list"),
            reverse("accounts:student_list"), reverse("accounts:student_list") + "?export=xlsx",
            reverse("theses:list"), reverse("theses:detail", args=[thesis.pk]),
            reverse("theses:document", args=[thesis.pk]), reverse("theses:export") + "?format=docx",
            reverse("theses:export") + "?format=xlsx", reverse("research:detail", args=[work.pk]),
            reverse("accounts:teacher_detail", args=[teacher.pk]),
            reverse("accounts:teacher_report", args=[teacher.pk]),
            reverse("accounts:student_detail", args=[student.pk]),
        ]
        pages = {
            "admin": manager + [reverse("core:structure"), reverse("core:staff"), reverse("core:audit"),
                                reverse("research:criteria")],
            "sifat": manager + [reverse("research:criteria"), reverse("core:audit")],
            "dekanat_atf": manager + [reverse("accounts:student_import"), reverse("accounts:student_create")],
            "kafedra_di": manager + [reverse("accounts:teacher_import"), reverse("theses:import"),
                                     reverse("theses:create"), reverse("accounts:teacher_create")],
            "di.teacher1": common + [reverse("theses:list"), reverse("research:create"),
                                     reverse("accounts:teacher_detail", args=[teacher.pk])],
            student.username: common + [reverse("accounts:student_detail", args=[student.pk]),
                                        reverse("theses:document", args=[thesis.pk])],
        }
        for username, urls in pages.items():
            self.login(username)
            for url in urls:
                resp = self.client.get(url, follow=True)
                self.assertEqual(resp.status_code, 200, f"{username} -> {url}")
        self.client.logout()
        resp = self.client.get(reverse("core:verify", args=[thesis.verification_code]))
        self.assertContains(resp, "Hujjat haqiqiy")

    def test_scope_isolation(self):
        other = Thesis.objects.filter(department__short_name="RI").first()
        self.login("kafedra_di")
        self.assertEqual(self.client.get(reverse("theses:detail", args=[other.pk])).status_code, 404)
        self.login("dekanat_atf")
        self.assertEqual(self.client.get(reverse("theses:detail", args=[other.pk])).status_code, 404)
        self.login("di.teacher1")
        self.assertEqual(self.client.get(reverse("accounts:teacher_list")).status_code, 403)

    def test_word_imports_and_full_thesis_workflow(self):
        # 1) Kafedra o‘qituvchini import qiladi
        self.login("kafedra_di")
        f = make_docx(["№", "F.I.Sh.", "Lavozimi", "Ilmiy darajasi"], [["1", "Qosimov Anvar Ilhomovich", "Dotsent", "PhD"]])
        resp = self.client.post(reverse("accounts:teacher_import"), {"file": f})
        self.assertContains(resp, "Qosimov Anvar Ilhomovich")
        teacher = User.objects.get(last_name="Qosimov", role=User.Role.TEACHER)
        self.assertEqual(teacher.department.short_name, "DI")
        self.assertTrue(teacher.must_change_password)
        self.assertEqual(self.client.get(reverse("accounts:credentials_download")).status_code, 200)

        # 2) Dekanat talabani import qiladi (ustunlar tartibi boshqacha)
        self.login("dekanat_atf")
        f = make_docx(["Guruh", "Talaba ID (HEMIS)", "F.I.Sh.", "Kurs", "Kafedra", "Yo‘nalish shifri"],
                      [["DI-41-22", "999000111", "Valiyev Sanjar Komilovich", "4", "Dasturiy injiniring", "60610500"]])
        self.client.post(reverse("accounts:student_import"), {"file": f})
        student = User.objects.get(username="999000111")
        self.assertEqual(student.department.short_name, "DI")
        self.assertEqual(student.student_profile.group_name, "DI-41-22")

        # 3) Kafedra mavzu va rahbarni Word orqali biriktiradi
        self.login("kafedra_di")
        f = make_docx(["№", "Talaba F.I.Sh.", "Talaba ID", "BMI mavzusi", "Ilmiy rahbar F.I.Sh."],
                      [["1", "Valiyev Sanjar", "999000111", "Yangi test mavzusi", "Qosimov Anvar"]])
        self.client.post(reverse("theses:import"), {"file": f})
        thesis = Thesis.objects.get(student=student)
        self.assertEqual(thesis.supervisor, teacher)
        self.assertEqual(thesis.status, Thesis.Status.DRAFT)

        # Dekanat loyihani ko‘rmaydi
        self.login("dekanat_atf")
        self.assertEqual(self.client.get(reverse("theses:detail", args=[thesis.pk])).status_code, 404)

        # 4) Kelishuvga yuborish (ommaviy)
        self.login("kafedra_di")
        self.client.post(reverse("theses:bulk"), {"action": "send", "ids": [thesis.pk]})
        thesis.refresh_from_db()
        self.assertEqual(thesis.status, Thesis.Status.PENDING)

        # 5) Dekanat qaytaradi -> kafedra qayta yuboradi -> ikkalasi kelishadi
        self.login("dekanat_atf")
        self.client.post(reverse("theses:decide", args=[thesis.pk]), {"decision": "returned", "comment": "Tuzating"})
        thesis.refresh_from_db()
        self.assertEqual(thesis.status, Thesis.Status.RETURNED)
        self.login("kafedra_di")
        self.client.post(reverse("theses:send", args=[thesis.pk]))
        for username in ("dekanat_atf", "sifat"):
            self.login(username)
            self.client.post(reverse("theses:decide", args=[thesis.pk]), {"decision": "approved", "comment": ""})
        thesis.refresh_from_db()
        self.assertEqual(thesis.status, Thesis.Status.APPROVED)
        self.assertTrue(student.notifications.exists())

        # 6) Talaba tasdiqlangan hujjatni yuklab oladi
        self.login("999000111")
        student.must_change_password = False
        student.save()
        resp = self.client.get(reverse("theses:document", args=[thesis.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_scientific_work_evaluation(self):
        teacher = User.objects.get(username="di.teacher1")
        coauthor = User.objects.filter(thesis__supervisor=teacher).first()
        self.login("di.teacher1")
        resp = self.client.post(reverse("research:create"), {
            "title": "Test maqola", "work_type": "article", "level": "oak", "students": [coauthor.pk],
            "file": SimpleUploadedFile("a.pdf", b"%PDF-1.4"),
        })
        work = ScientificWork.objects.get(title="Test maqola")
        self.assertRedirects(resp, reverse("research:detail", args=[work.pk]))
        criteria = Criterion.objects.filter(is_active=True)
        totals = []
        for username, factor in (("kafedra_di", 1.0), ("dekanat_atf", 0.8), ("sifat", 0.6)):
            self.login(username)
            data = {"decision": "approved", "comment": ""}
            for c in criteria:
                data[f"c_{c.pk}"] = str(c.max_score * factor)
            totals.append(sum(c.max_score * factor for c in criteria))
            self.client.post(reverse("research:evaluate", args=[work.pk]), data)
        work.refresh_from_db()
        self.assertEqual(work.status, ScientificWork.Status.APPROVED)
        self.assertAlmostEqual(float(work.final_score), sum(totals) / 3, places=2)
        # Talaba o‘z profilida tasdiqlangan ishni ko‘radi
        self.login(coauthor.username)
        self.assertContains(self.client.get(reverse("accounts:student_detail", args=[coauthor.pk])), "Test maqola")
