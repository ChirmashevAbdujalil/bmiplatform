"""Rasmiy hujjatlarni (Word / Excel) shakllantirish."""
import io

from django.conf import settings
from django.utils import timezone
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

NAVY = RGBColor(0x0B, 0x2E, 0x59)
FONT = "Times New Roman"


def _fmt_dt(value):
    if not value:
        return "—"
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")


def _fmt_date(value):
    if not value:
        return "—"
    if hasattr(value, "hour"):
        value = timezone.localtime(value)
    return value.strftime("%d.%m.%Y")


def _new_document(landscape=False):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(12)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    section = doc.sections[0]
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = Cm(2.5 if not landscape else 1.8)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    return doc


def _para(doc, text="", bold=False, size=12, align=None, color=None, italic=False, space_after=4):
    p = doc.add_paragraph()
    if text:
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)
        if color is not None:
            run.font.color.rgb = color
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(space_after)
    return p


def _shade(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _cell_text(cell, text, bold=False, size=11, align=None, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text if text is not None else ""))
    run.bold = bold
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _table(doc, headers, rows, widths=None, size=11):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        _cell_text(cell, h, bold=True, size=size, align="center", color=RGBColor(0xFF, 0xFF, 0xFF))
        _shade(cell, "0B2E59")
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            _cell_text(cells[i], value, size=size, align="center" if i == 0 else None)
    if widths:
        _set_widths(table, widths)
    return table


def _set_widths(table, widths):
    """Ustun kengliklarini Word va LibreOffice uchun qat’iy belgilash."""
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    grid = table._tbl.tblGrid
    for i, col in enumerate(grid.findall(qn("w:gridCol"))):
        if i < len(widths):
            col.set(qn("w:w"), str(int(Cm(widths[i]).twips)))
    for row in table.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)


def _header(doc, subtitle=None):
    _para(doc, settings.UNIVERSITY_NAME.upper(), bold=True, size=13, align="center", color=NAVY, space_after=0)
    if subtitle:
        _para(doc, subtitle, size=12, align="center", space_after=0)
    line = _para(doc, "_" * 78, align="center", color=NAVY, space_after=10)
    line.runs[0].font.size = Pt(8)


def _to_bytes(doc):
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _qr_png(data):
    try:
        import qrcode
    except ImportError:  # pragma: no cover
        return None
    img = qrcode.make(data, box_size=6, border=1)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# BMI: tasdiqlangan mavzu va ilmiy rahbar to‘g‘risidagi hujjat
# ---------------------------------------------------------------------------
def thesis_certificate(thesis, verify_url):
    student = thesis.student
    profile = getattr(student, "student_profile", None)
    doc = _new_document()
    _header(doc, thesis.department.faculty.name if thesis.department else None)

    _para(doc, "BITIRUV MALAKAVIY ISHI MAVZUSI VA ILMIY RAHBARINI", bold=True, size=14, align="center", space_after=0)
    _para(doc, "BIRIKTIRISH TO‘G‘RISIDA", bold=True, size=14, align="center", space_after=0)
    _para(doc, "TASDIQLANGAN HUJJAT", bold=True, size=14, align="center", color=NAVY, space_after=12)
    _para(doc, f"Hujjat raqami: BMI-{thesis.academic_year[:4]}-{thesis.pk:05d}    |    "
               f"O‘quv yili: {thesis.academic_year}", size=11, align="center", italic=True, space_after=12)

    rows = [
        ("Talabaning F.I.Sh.", student.full_name),
        ("Talaba ID (HEMIS)", profile.student_id if profile else "—"),
        ("Fakultet", student.faculty.name if student.faculty else "—"),
        ("Bitiruvchi kafedra", thesis.department.name if thesis.department else "—"),
        ("Ta’lim yo‘nalishi", str(profile.direction) if profile and profile.direction else "—"),
        ("Kurs / guruh", f"{profile.course}-kurs, {profile.group_name}" if profile else "—"),
        ("Ta’lim shakli", profile.get_education_form_display() if profile else "—"),
        ("Bitiruv malakaviy ishi mavzusi", thesis.topic),
        ("Ilmiy rahbar", _supervisor_line(thesis.supervisor)),
    ]
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        cells = table.add_row().cells
        _cell_text(cells[0], label, bold=True, size=12)
        _shade(cells[0], "EEF2F8")
        _cell_text(cells[1], value, size=12, bold=(label == "Bitiruv malakaviy ishi mavzusi"))

    _set_widths(table, [6, 11])
    _para(doc, space_after=6)
    _para(doc, "ELEKTRON KELISHUV VARAQASI", bold=True, size=12, align="center", color=NAVY, space_after=6)
    approvals = [
        ("Kafedra (kelishuvga yubordi)", thesis.sent_by, thesis.sent_at, "Yuborildi"),
        ("Dekanat", thesis.dekanat_by, thesis.dekanat_at, thesis.get_dekanat_decision_display()),
        ("Ta’lim sifati bo‘limi", thesis.sifat_by, thesis.sifat_at, thesis.get_sifat_decision_display()),
    ]
    _table(
        doc,
        ["Bo‘linma", "Mas’ul shaxs", "Qaror", "Sana va vaqt"],
        [(a, u.full_name if u else "—", d, _fmt_dt(t)) for a, u, t, d in approvals],
        widths=[5, 5.5, 3, 3.5],
    )

    _para(doc, space_after=6)
    _para(
        doc,
        f"Hujjat {_fmt_dt(thesis.approved_at)} da barcha mas’ul bo‘linmalar tomonidan elektron tarzda "
        f"kelishilgan va tasdiqlangan. Hujjatning haqiqiyligini QR-kod yoki quyidagi havola orqali "
        f"tekshirish mumkin.",
        size=11, align="justify",
    )
    qr = _qr_png(verify_url)
    if qr is not None:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(qr, width=Cm(3.2))
    _para(doc, f"Tekshirish kodi: {thesis.short_code}", bold=True, size=11, align="center", space_after=0)
    _para(doc, verify_url, size=9, align="center", italic=True)
    return _to_bytes(doc)


def _supervisor_line(supervisor):
    if not supervisor:
        return "—"
    tp = getattr(supervisor, "teacher_profile", None)
    extra = ", ".join(x for x in [tp.position if tp else "", tp.degree if tp else ""] if x)
    return f"{supervisor.full_name}" + (f" ({extra})" if extra else "")


# ---------------------------------------------------------------------------
# BMI: tasdiqlangan mavzular ro‘yxati (fakultet/kafedra/kurs/yo‘nalish kesimida)
# ---------------------------------------------------------------------------
def theses_list_docx(theses, filter_caption):
    doc = _new_document(landscape=True)
    _header(doc)
    _para(doc, "BITIRUV MALAKAVIY ISHLARI MAVZULARI VA ILMIY RAHBARLARI", bold=True, size=14, align="center",
          space_after=0)
    _para(doc, "RO‘YXATI", bold=True, size=14, align="center", space_after=4)
    if filter_caption:
        _para(doc, filter_caption, italic=True, size=11, align="center", space_after=10)

    groups = {}
    for t in theses:
        faculty = t.department.faculty.name if t.department else "Fakultet ko‘rsatilmagan"
        dept = t.department.name if t.department else "Kafedra ko‘rsatilmagan"
        groups.setdefault((faculty, dept), []).append(t)

    if not groups:
        _para(doc, "Tanlangan mezonlar bo‘yicha tasdiqlangan mavzular topilmadi.", italic=True, align="center")

    for (faculty, dept), items in groups.items():
        _para(doc, f"{faculty} — {dept}", bold=True, size=12, color=NAVY, space_after=4)
        rows = []
        for i, t in enumerate(items, start=1):
            p = getattr(t.student, "student_profile", None)
            rows.append((
                i,
                t.student.full_name,
                p.student_id if p else "",
                f"{p.course}-kurs / {p.group_name}" if p else "",
                str(p.direction) if p and p.direction else "",
                t.topic,
                t.supervisor.full_name if t.supervisor else "",
                _fmt_date(t.approved_at),
            ))
        _table(
            doc,
            ["№", "Talaba F.I.Sh.", "ID", "Kurs / guruh", "Yo‘nalish", "BMI mavzusi", "Ilmiy rahbar", "Sana"],
            rows,
            widths=[0.9, 4, 2.3, 2.4, 3.6, 7.6, 3.6, 2.3],
            size=10,
        )
        _para(doc, space_after=8)

    _para(doc, f"Jami: {sum(len(v) for v in groups.values())} ta. "
               f"Ro‘yxat {_fmt_dt(timezone.now())} holatiga {settings.PLATFORM_NAME} orqali shakllantirildi.",
          size=10, italic=True)
    return _to_bytes(doc)


def theses_list_xlsx(theses):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "BMI mavzulari"
    headers = [
        "№", "Talaba F.I.Sh.", "Talaba ID", "Fakultet", "Kafedra", "Yo‘nalish", "Kurs", "Guruh",
        "BMI mavzusi", "Ilmiy rahbar", "Holati", "O‘quv yili", "Tasdiqlangan sana", "Tekshirish kodi",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0B2E59")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, t in enumerate(theses, start=1):
        p = getattr(t.student, "student_profile", None)
        ws.append([
            i, t.student.full_name, p.student_id if p else "",
            t.department.faculty.name if t.department else "", t.department.name if t.department else "",
            str(p.direction) if p and p.direction else "", p.course if p else "", p.group_name if p else "",
            t.topic, t.supervisor.full_name if t.supervisor else "", t.get_status_display(), t.academic_year,
            _fmt_date(t.approved_at) if t.approved_at else "", t.short_code if t.approved_at else "",
        ])
    widths = [5, 32, 14, 28, 28, 30, 6, 10, 60, 30, 14, 11, 14, 12]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Import shablonlari
# ---------------------------------------------------------------------------
TEMPLATES = {
    "teachers": {
        "title": "KAFEDRA PROFESSOR-O‘QITUVCHILARI RO‘YXATI",
        "hint": "Jadvalga kafedra o‘qituvchilarini kiriting. Sarlavha qatorini o‘zgartirmang. "
                "«Login» ustuni ixtiyoriy — bo‘sh qolsa, tizim avtomatik yaratadi.",
        "headers": ["№", "F.I.Sh.", "Lavozimi", "Ilmiy darajasi", "Ilmiy unvoni", "Telefon", "E-mail", "Login"],
        "sample": [
            ["1", "Karimov Akmal Bahodirovich", "Dotsent", "PhD", "Dotsent", "+998901234567", "akarimov@mail.uz", ""],
            ["2", "Rahimova Dilnoza Anvarovna", "Katta o‘qituvchi", "", "", "+998907654321", "", ""],
        ],
    },
    "students": {
        "title": "BITIRUVCHI TALABALAR RO‘YXATI",
        "hint": "Jadvalga fakultet talabalarini kiriting. «Talaba ID» — HEMIS ID (login sifatida ishlatiladi). "
                "«Kafedra» — bitiruvchi kafedra nomi (tizimdagi nom bilan bir xil yoki uning qismi).",
        "headers": ["№", "F.I.Sh.", "Talaba ID (HEMIS)", "Yo‘nalish shifri", "Yo‘nalish nomi", "Kurs", "Guruh",
                    "Kafedra", "Ta’lim shakli", "Telefon"],
        "sample": [
            ["1", "Aliyev Jasur Olimovich", "3112311001", "60610100", "Kompyuter ilmlari va dasturlash texnologiyalari",
             "4", "411-21", "Axborot texnologiyalari", "Kunduzgi", "+998931112233"],
        ],
    },
    "theses": {
        "title": "BITIRUV MALAKAVIY ISHI MAVZULARI VA ILMIY RAHBARLARINI BIRIKTIRISH",
        "hint": "Talaba ID (yoki to‘liq F.I.Sh.) bo‘yicha talaba topiladi. «Ilmiy rahbar» ustuniga kafedra "
                "o‘qituvchisining familiyasi va ismini yozing.",
        "headers": ["№", "Talaba F.I.Sh.", "Talaba ID (HEMIS)", "BMI mavzusi", "Ilmiy rahbar F.I.Sh."],
        "sample": [
            ["1", "Aliyev Jasur Olimovich", "3112311001",
             "Ta’lim muassasalari uchun hujjat aylanishini avtomatlashtirish tizimini ishlab chiqish",
             "Karimov Akmal Bahodirovich"],
        ],
    },
}


def import_template(kind):
    spec = TEMPLATES[kind]
    doc = _new_document(landscape=len(spec["headers"]) > 6)
    _header(doc)
    _para(doc, spec["title"], bold=True, size=14, align="center", space_after=6)
    _para(doc, spec["hint"], italic=True, size=10, align="justify", space_after=10)
    _table(doc, spec["headers"], spec["sample"], size=11)
    return _to_bytes(doc)


# ---------------------------------------------------------------------------
# Login-parollar ro‘yxati
# ---------------------------------------------------------------------------
def credentials_docx(rows, title):
    doc = _new_document()
    _header(doc)
    _para(doc, title.upper(), bold=True, size=13, align="center", space_after=4)
    _para(doc, f"Platforma manzili: {settings.SITE_URL}  •  Birinchi kirishda parolni almashtirish talab qilinadi.",
          italic=True, size=10, align="center", space_after=10)
    _table(doc, ["№", "F.I.Sh.", "Login", "Parol"],
           [(i, r["name"], r["username"], r["password"]) for i, r in enumerate(rows, start=1)],
           widths=[1, 8, 4, 4])
    _para(doc, space_after=6)
    _para(doc, "Diqqat: ushbu hujjat maxfiy ma’lumotni o‘z ichiga oladi. Login-parollarni egalariga shaxsan topshiring.",
          italic=True, size=10)
    return _to_bytes(doc)


# ---------------------------------------------------------------------------
# O‘qituvchining ilmiy faoliyati bo‘yicha hisobot
# ---------------------------------------------------------------------------
def teacher_report_docx(teacher, works, theses):
    doc = _new_document(landscape=True)
    _header(doc, teacher.department.name if teacher.department else None)
    _para(doc, "O‘QITUVCHINING ILMIY FAOLIYATI BO‘YICHA MA’LUMOTNOMA", bold=True, size=14, align="center",
          space_after=2)
    _para(doc, teacher.full_name, bold=True, size=13, align="center", color=NAVY, space_after=10)

    total = sum((w.final_score or 0) for w in works if w.status == "approved")
    _para(doc, f"Tasdiqlangan ilmiy ishlar: {sum(1 for w in works if w.status == 'approved')} ta  •  "
               f"Umumiy markazlashgan ball: {total:.2f}  •  Biriktirilgan talabalar: {len(theses)} ta",
          size=11, align="center", space_after=10)

    _para(doc, "1. Ilmiy ishlar", bold=True, size=12, space_after=4)
    _table(
        doc,
        ["№", "Nomi", "Turi", "Darajasi", "Nashr", "Talaba hammualliflar", "Holati", "Ball"],
        [(i, w.title, w.get_work_type_display(), w.get_level_display(), w.publication,
          ", ".join(s.short_name for s in w.students.all()), w.get_status_display(),
          f"{w.final_score:.2f}" if w.final_score is not None else "—")
         for i, w in enumerate(works, start=1)],
        widths=[1, 7, 3, 3.5, 4, 4, 2.5, 1.8], size=10,
    )
    _para(doc, space_after=8)
    _para(doc, "2. Ilmiy rahbarlikdagi bitiruvchilar", bold=True, size=12, space_after=4)
    _table(
        doc,
        ["№", "Talaba", "Guruh", "BMI mavzusi", "Holati"],
        [(i, t.student.full_name, getattr(getattr(t.student, "student_profile", None), "group_name", ""),
          t.topic, t.get_status_display()) for i, t in enumerate(theses, start=1)],
        widths=[1, 6, 3, 13, 3], size=10,
    )
    _para(doc, space_after=8)
    _para(doc, f"Ma’lumotnoma {_fmt_dt(timezone.now())} holatiga shakllantirildi.", italic=True, size=10)
    return _to_bytes(doc)
