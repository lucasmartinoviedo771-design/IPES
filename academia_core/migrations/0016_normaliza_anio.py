# academia_core/migrations/0016_normaliza_anio.py
from django.db import migrations

MAP = {
    "1": "1°", "1º": "1°", "1°": "1°", "01": "1°", "1o": "1°", "I": "1°",
    "2": "2°", "2º": "2°", "2°": "2°", "02": "2°", "2o": "2°", "II": "2°",
    "3": "3°", "3º": "3°", "3°": "3°", "03": "3°", "3o": "3°", "III": "3°",
    "4": "4°", "4º": "4°", "4°": "4°", "04": "4°", "4o": "4°", "IV": "4°",
}

def forward(apps, schema_editor):
    Espacio = apps.get_model("academia_core", "EspacioCurricular")
    for e in Espacio.objects.all():
        raw = (e.anio or "").strip().upper().replace("º", "°")
        raw = raw.replace("PRIMERO", "1").replace("SEGUNDO", "2")\
                 .replace("TERCERO", "3").replace("CUARTO", "4")
        val = MAP.get(raw, MAP.get(raw.strip("°º"), e.anio))
        if val != e.anio:
            Espacio.objects.filter(pk=e.pk).update(anio=val)

def backward(apps, schema_editor):
    # No-op
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("academia_core", "0015_estudianteprofesorado_nota_compromiso"),  # <-- ESTA ES LA CLAVE
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
