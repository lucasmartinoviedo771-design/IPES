from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("academia_core", "0011_estudiante_lugar_nacimiento_and_more"),
    ]

    # No hacemos nada: el constraint ya no existe
    operations = []