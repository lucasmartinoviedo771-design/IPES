from academia_core.models import Profesorado

file_path = r"C:\proyectos\academia\profesorado_names.txt"
print(f"Attempting to write to: {file_path}")

with open(file_path, 'w', encoding='utf-8') as f:
    for p in Profesorado.objects.all():
        f.write(p.nombre + '\n')