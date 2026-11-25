from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _create_criteria(sender, **kwargs):
    from .services import ensure_default_criteria

    ensure_default_criteria()


class ResearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "research"
    verbose_name = "Ilmiy ishlar"

    def ready(self):
        post_migrate.connect(_create_criteria, sender=self)
