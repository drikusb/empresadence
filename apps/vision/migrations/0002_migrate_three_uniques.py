from django.db import migrations


def migrate_three_uniques(apps, schema_editor):
    """Move any existing three_uniques content to three_uniques_1."""
    VTOSection = apps.get_model('vto', 'VTOSection')
    for section in VTOSection.objects.filter(key='three_uniques', content__gt=''):
        VTOSection.objects.update_or_create(
            vto=section.vto,
            key='three_uniques_1',
            defaults={
                'content': section.content,
                'last_edited_by': section.last_edited_by,
                'last_edited_at': section.last_edited_at,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('vto', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_three_uniques, migrations.RunPython.noop),
    ]
