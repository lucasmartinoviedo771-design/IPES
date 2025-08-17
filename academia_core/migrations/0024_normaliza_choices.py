from django.db import migrations


def forward(apps, schema_editor):
    InscripcionEspacio = apps.get_model('academia_core', 'InscripcionEspacio')
    InscripcionFinal   = apps.get_model('academia_core', 'InscripcionFinal')

    map_estado = {
        'en curso': 'EN_CURSO',
        'en_curso': 'EN_CURSO',
        'encurso':  'EN_CURSO',
        'baja':     'BAJA',
    }

    map_cond_cursada = {
        'regular':        'REGULAR',
        'promocion':      'PROMOCION',
        'promoción':      'PROMOCION',
        'libre':          'LIBRE',
        'desaprobado_tp': 'DESAPROBADO_TP',
        'desaprobado pa': 'DESAPROBADO_PA',
        'desaprobado_pa': 'DESAPROBADO_PA',
    }

    map_cond_final = {
        'regular':      'REGULAR',
        'libre':        'LIBRE',
        'equivalencia': 'EQUIVALENCIA',
    }

    # normaliza estado/condicion de cursadas
    for r in InscripcionEspacio.objects.all():
        changed = False
        if getattr(r, 'estado', None):
            k = str(r.estado).strip().lower().replace(' ', '_')
            new = map_estado.get(k)
            if new and new != r.estado:
                r.estado = new
                changed = True
        if getattr(r, 'condicion', None):
            k = str(r.condicion).strip().lower()
            new = map_cond_cursada.get(k)
            if new and new != r.condicion:
                r.condicion = new
                changed = True
        if changed:
            r.save(update_fields=['estado', 'condicion'])

    # normaliza condicion de finales
    for f in InscripcionFinal.objects.all():
        if getattr(f, 'condicion', None):
            k = str(f.condicion).strip().lower()
            new = map_cond_final.get(k)
            if new and new != f.condicion:
                f.condicion = new
                f.save(update_fields=['condicion'])


def backward(apps, schema_editor):
    # No se revierte (dejamos los códigos normalizados)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academia_core', '0023_normalize_fotos_folios'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]