from django.db import migrations

def normalize(apps, schema_editor):
    # Modelo real según tus migraciones:
    EP = apps.get_model('academia_core', 'EstudianteProfesorado')
    for obj in EP.objects.all():
        # Normalizar fotos
        v_fotos = getattr(obj, 'doc_fotos_carnet', False)
        try:
            v_fotos = int(v_fotos)
        except (TypeError, ValueError):
            v_fotos = 1 if str(v_fotos).strip().lower() in ('1', 'true', 't', 'si', 'sí') else 0
        obj.doc_fotos_carnet = bool(v_fotos)

        # Normalizar folios
        v_folios = getattr(obj, 'doc_folios_oficio', False)
        try:
            v_folios = int(v_folios)
        except (TypeError, ValueError):
            v_folios = 1 if str(v_folios).strip().lower() in ('1', 'true', 't', 'si', 'sí') else 0
        obj.doc_folios_oficio = bool(v_folios)

        obj.save(update_fields=['doc_fotos_carnet', 'doc_folios_oficio'])

class Migration(migrations.Migration):

    dependencies = [
        # 👇 ESTA es la migración que acabás de aplicar y que cambió a BooleanField
        ('academia_core', '0022_alter_estudianteprofesorado_doc_folios_oficio_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize, reverse_code=migrations.RunPython.noop),
    ]
