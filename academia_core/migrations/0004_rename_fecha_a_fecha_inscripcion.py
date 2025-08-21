# academia_core/migrations/0004_rename_fecha_a_fecha_inscripcion.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("academia_core", "0003_inscripcionespacio_motivo_baja"),  # <- IMPORTANTÍSIMO
    ]

    operations = [
        migrations.RenameField(
            model_name="inscripcionespacio",
            old_name="fecha",
            new_name="fecha_inscripcion",
        ),
    ]
