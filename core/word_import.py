"""Word (.docx) jadvallaridan ma’lumotlarni o‘qish.

Har bir jadvalning birinchi qatori sarlavha hisoblanadi; ustunlar sarlavhadagi
kalit so‘zlar orqali aniqlanadi, shuning uchun ustunlar tartibi muhim emas.
Sarlavha tanilmasa — standart shablondagi tartib qo‘llaniladi.
"""
import re

from docx import Document

APOSTROPHES = str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "`": "'", "´": "'"})


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").translate(APOSTROPHES)).strip()


def norm_key(text):
    return normalize(text).lower()


# (maydon, kalit so‘zlar) — tartib muhim: aniqroq kalitlar oldinda
SCHEMAS = {
    "teachers": {
        "columns": [
            ("username", ["login"]),
            ("position", ["lavozim"]),
            ("degree", ["daraja"]),
            ("academic_title", ["unvon"]),
            ("phone", ["telefon", "tel."]),
            ("email", ["e-mail", "email", "pochta"]),
            ("full_name", ["f.i.sh", "f.i.o", "fish", "familiya", "ism"]),
        ],
        "default": ["no", "full_name", "position", "degree", "academic_title", "phone", "email"],
        "required": ["full_name"],
    },
    "students": {
        "columns": [
            ("direction_code", ["shifr", "kodi"]),
            ("direction_name", ["yo'nalish", "yonalish", "mutaxassislik"]),
            ("student_id", ["hemis", "talaba id", "id raqam", "id"]),
            ("course", ["kurs"]),
            ("group", ["guruh"]),
            ("department", ["kafedra"]),
            ("education_form", ["shakl"]),
            ("phone", ["telefon", "tel."]),
            ("full_name", ["f.i.sh", "f.i.o", "fish", "familiya", "ism"]),
        ],
        "default": [
            "no", "full_name", "student_id", "direction_code", "direction_name",
            "course", "group", "department", "education_form", "phone",
        ],
        "required": ["full_name", "student_id"],
    },
    "theses": {
        "columns": [
            ("supervisor", ["rahbar"]),
            ("topic", ["mavzu"]),
            ("student_id", ["hemis", "talaba id", "id raqam", "id"]),
            ("full_name", ["talaba", "f.i.sh", "f.i.o", "fish", "familiya"]),
        ],
        "default": ["no", "full_name", "student_id", "topic", "supervisor"],
        "required": ["topic"],
    },
}


class ImportFormatError(Exception):
    pass


def _detect_columns(header_cells, schema):
    mapping = {}
    for idx, cell in enumerate(header_cells):
        key = norm_key(cell)
        if not key:
            continue
        for field, keywords in schema["columns"]:
            if field in mapping.values():
                continue
            if any(kw in key for kw in keywords):
                mapping[idx] = field
                break
    return mapping


def _row_texts(row):
    texts, last = [], None
    for cell in row.cells:
        # Birlashtirilgan katakchalar python-docx da takrorlanadi — bir marta olamiz
        if last is not None and cell._tc is last:
            continue
        last = cell._tc
        texts.append(normalize(cell.text))
    return texts


def read_rows(file_obj, kind):
    """Faylni o‘qib, [{'_row': n, field: value, ...}] ro‘yxatini qaytaradi."""
    schema = SCHEMAS[kind]
    try:
        document = Document(file_obj)
    except Exception as exc:  # noqa: BLE001
        raise ImportFormatError("Fayl o‘qilmadi. Faqat .docx formatidagi Word hujjat yuklang.") from exc

    if not document.tables:
        raise ImportFormatError("Hujjatda jadval topilmadi. Namuna shablondan foydalaning.")

    rows = []
    for table in document.tables:
        all_rows = [_row_texts(r) for r in table.rows]
        if not all_rows:
            continue
        mapping = _detect_columns(all_rows[0], schema)
        if all(req in mapping.values() for req in schema["required"]):
            data_rows = all_rows[1:]
        else:
            mapping = {i: f for i, f in enumerate(schema["default"])}
            first = norm_key(" ".join(all_rows[0]))
            data_rows = all_rows[1:] if ("f.i" in first or "№" in first or "mavzu" in first) else all_rows

        for number, cells in enumerate(data_rows, start=2):
            item = {"_row": number}
            for idx, field in mapping.items():
                if idx < len(cells):
                    item[field] = cells[idx]
            # Ustun raqamlari qatori (1, 2, 3 ...) yoki bo‘sh qatorlarni tashlab ketamiz
            values = [v for k, v in item.items() if k not in ("_row", "no") and v]
            if not values or all(v.isdigit() and len(v) <= 2 for v in values):
                continue
            rows.append(item)

    if not rows:
        raise ImportFormatError("Jadvalda ma’lumot topilmadi.")
    return rows


def split_full_name(full_name):
    parts = normalize(full_name).split(" ")
    last = parts[0] if parts else ""
    first = parts[1] if len(parts) > 1 else ""
    middle = " ".join(parts[2:]) if len(parts) > 2 else ""
    return last, first, middle


def parse_course(value, default=4):
    match = re.search(r"\d", value or "")
    return int(match.group()) if match else default
