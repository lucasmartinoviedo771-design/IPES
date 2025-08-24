from django.core.management.base import BaseCommand
from django.apps import apps
from pathlib import Path


def field_type(f):
    try:
        return f.get_internal_type()
    except Exception:
        return f.__class__.__name__


def is_local_field(f):
    # excluye reversos
    return getattr(f, "model", None) is not None and f.model is not None


class Command(BaseCommand):
    help = "Exporta un inventario de modelos/campos y un ERD en formato Mermaid."

    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            default="academia_core",
            help="Etiqueta del app (default: academia_core)",
        )
        parser.add_argument(
            "--md", default="schema_models.md", help="Archivo Markdown de salida"
        )
        parser.add_argument(
            "--mmd", default="schema_erd.mmd", help="Archivo Mermaid ERD de salida"
        )

    def handle(self, *args, **opts):
        app_label = opts["app"]
        out_md = Path(opts["md"])
        out_mmd = Path(opts["mmd"])

        app = apps.get_app_config(app_label)
        models = list(app.get_models())

        # ---------- Markdown ----------
        lines_md = []
        lines_md.append(f"# Inventario de modelos — {app_label}\n")
        for m in models:
            lines_md.append(f"## {m.__name__}  \nTabla: `{m._meta.db_table}`\n")
            lines_md.append("| Campo | Tipo | Relación | Null | PK | Unique | M2M |")
            lines_md.append("|------:|:-----|:--------:|:----:|:--:|:------:|:---:|")
            for f in m._meta.get_fields():
                rel = ""
                if getattr(f, "is_relation", False):
                    kind = (
                        "M2M"
                        if f.many_to_many
                        else "O2O" if f.one_to_one else "FK" if f.many_to_one else "REL"
                    )
                    rel = f"{kind}→{getattr(f.related_model, '__name__', f.related_model)}"
                null_ok = getattr(f, "null", False)
                pk = getattr(f, "primary_key", False)
                unique = getattr(f, "unique", False)
                m2m = "✔" if getattr(f, "many_to_many", False) else ""
                lines_md.append(
                    f"| `{f.name}` | `{field_type(f)}` | {rel or ''} | {'✔' if null_ok else ''} | {'✔' if pk else ''} | {'✔' if unique else ''} | {m2m} |"
                )
            lines_md.append("")

        out_md.write_text("\n".join(lines_md), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"OK Markdown → {out_md.resolve()}"))

        # ---------- Mermaid ERD ----------
        # erDiagram syntax: https://mermaid.js.org/syntax/entityRelationshipDiagram.html
        lines_mmd = []
        lines_mmd.append("erDiagram")
        # Definir entidades con atributos principales (solo locales, no reversos)
        for m in models:
            lines_mmd.append(f"  {m.__name__} {{")
            for f in m._meta.local_fields + m._meta.local_many_to_many:
                t = field_type(f)
                # etiqueta “PK”/“FK” simple en el atributo
                tag = []
                if getattr(f, "primary_key", False):
                    tag.append("PK")
                if getattr(f, "many_to_one", False) or getattr(f, "one_to_one", False):
                    tag.append("FK")
                tag_txt = (" [" + ",".join(tag) + "]") if tag else ""
                lines_mmd.append(f"    {t} {f.name}{tag_txt}")
            lines_mmd.append("  }")

        # Relaciones
        rel_lines = set()
        for m in models:
            for f in m._meta.get_fields():
                if not getattr(f, "is_relation", False) or not is_local_field(f):
                    continue
                a = m.__name__
                b = getattr(f.related_model, "__name__", None)
                if not b:
                    continue
                label = f.name
                if f.many_to_many:
                    # A }o--o{ B
                    rel_lines.add(f'  {a} }}o--o{{ {b} : "{label}"')
                elif f.one_to_one:
                    # A ||--|| B (campo en A referencia a B)
                    rel_lines.add(f'  {a} ||--|| {b} : "{label}"')
                elif f.many_to_one:
                    # FK en A apunta a B -> B (1) -- (N) A
                    # Mermaid: B ||--o{ A
                    rel_lines.add(f'  {b} ||--o{{ {a} : "{label}"')

        lines_mmd.extend(sorted(rel_lines))
        out_mmd.write_text("\n".join(lines_mmd), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"OK Mermaid → {out_mmd.resolve()}"))

        self.stdout.write(
            self.style.NOTICE(
                "\nAbrí el .mmd en VS Code (extensión Mermaid) o pegalo en https://mermaid.live para ver el diagrama."
            )
        )
