from django.apps import AppConfig


class VisionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.vision'
    # Kept as 'vto' on purpose: this is the app_label Django stores in every
    # migration record and content type, and no self-hosted install should
    # need a manual DB migration just because the package was renamed.
    label = 'vto'
    verbose_name = 'Vision and Delivery Board'
