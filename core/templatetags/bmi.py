from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Joriy GET parametrlarini saqlagan holda ayrimlarini almashtiradi."""
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return "?" + query.urlencode() if query else "?"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def percent(value, total):
    try:
        return round(float(value) * 100 / float(total)) if float(total) else 0
    except (TypeError, ValueError):
        return 0


@register.filter
def decision_badge(value):
    return {"approved": "success", "returned": "danger"}.get(value, "secondary")


@register.filter
def selected(value, current):
    return "selected" if str(value) == str(current or "") else ""


@register.simple_tag
def approval_steps(thesis):
    return [
        ("Dekanat", thesis.dekanat_decision, thesis.dekanat_by, thesis.dekanat_at, thesis.dekanat_comment),
        ("Ta’lim sifati bo‘limi", thesis.sifat_decision, thesis.sifat_by, thesis.sifat_at, thesis.sifat_comment),
    ]


@register.simple_tag(takes_context=True)
def sel(context, key, value):
    """<option> uchun: GET parametri qiymatga teng bo‘lsa 'selected' qaytaradi."""
    return "selected" if str(context["request"].GET.get(key, "")) == str(value) else ""
