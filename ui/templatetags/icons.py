from django import template
from django.utils.safestring import mark_safe

register = template.Library()

PATHS = {
    "speedometer": "M12 20a8 8 0 1 0-8-8 8 8 0 0 0 8 8zm0-8 4-2",
    "check": "M5 13l4 4L19 7",
    "grid": "M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z",
    "calendar2": "M7 3v4m10-4v4M3 8h18M5 21h14a2 2 0 0 0 2-2V8H3v11a2 2 0 0 0 2 2z",
    "pencil": "M12 20h9",
    "shield": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    "diagram": "M4 6h6v6H4zM14 4h6v8h-6zM8 12v8h8",
    "calendar": "M7 3v2m10-2v2M3 8h18M5 21h14a2 2 0 0 0 2-2V8H3v11a2 2 0 0 0 2 2z",
    "book": "M4 19.5A2.5 2.5 0 0 1 6.5 17H21v3H6.5A2.5 2.5 0 0 1 4 17.5zM4 5.5A2.5 2.5 0 0 1 6.5 3H21v11H6.5A2.5 2.5 0 0 1 4 11.5z",
    "layers": "M12 2l10 6-10 6L2 8l10-6zm0 12l10 6-10 6-10-6 10-6z",
    "mortarboard": "M2 10l10-5 10 5-10 5-10-5zm10 5v5",
    "id": "M4 4h16v16H4zM8 8h8M8 12h8M8 16h5",
    "hourglass": "M6 2h12v4l-4 4 4 4v4H6v-4l4-4-4-4V2z",
    "lock": "M6 10V8a6 6 0 1 1 12 0v2h-2V8a4 4 0 1 0-8 0v2H6zM6 10h12v10H6V10z",
    "gear": "M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z",
    "history": "M3 12a9 9 0 1 1 3 6M3 12H1m2 0h3",
    "help": "M9 9a3 3 0 1 1 6 0c0 2-3 2-3 4M12 17h.01",
    "arrow-right": "M5 12h14M13 5l7 7-7 7",
    "bolt": "M13 2L3 14h7l-1 8 10-12h-7l1-8z",
    "sun": "M12 4v-2M12 22v-2M4 12H2M22 12h-2M5 5l-1-1M20 20l-1-1M5 19l-1 1M20 4l-1 1M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z",
    "moon": "M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z",
    "search": "M21 21l-4.35-4.35M10 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16z",
    "plus-circle": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zm-4-10h8m-4-4v8",
}

@register.simple_tag
def icon(name, classes="w-4 h-4"):
    d = PATHS.get(name, "")
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" class="{classes}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/></svg>'
    return mark_safe(svg)  # <- evita escapes
