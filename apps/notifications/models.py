from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='notification_preference'
    )
    overdue_todo_digest = models.BooleanField(
        default=True, help_text='Daily email listing your overdue To-Dos.'
    )
    meeting_reminders = models.BooleanField(
        default=True, help_text="Email reminder on your team's meeting day."
    )
    rock_off_track_alerts = models.BooleanField(
        default=True, help_text='Email when one of your Rocks is marked off track.'
    )

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f'Notification preferences — {self.user}'

    @classmethod
    def for_user(cls, user):
        pref, _ = cls.objects.get_or_create(user=user)
        return pref


@receiver(post_save, sender=User)
def create_notification_preference(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.objects.get_or_create(user=instance)
