from __future__ import annotations
import re


# Conversión a ordinal con "º" (1 -> "1º")
def _to_ordinal(n: int | None) -> str:
    if not n:
        return ""
    try:
        n = int(n)
        return f"{n}\N{MASCULINE ORDINAL INDICATOR}"
    except Exception:
        return ""


_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
_WORDS = {"PRIM": 1, "SEG": 2, "TERC": 3, "CUART": 4, "QUINT": 5}


def _extract_year(*candidates: str) -> int | None:
    """Busca año en campos o en el nombre: dígitos, romanos o 'prim/seg/terc...'."""
    for raw in candidates:
        if not raw:
            continue
        s = str(raw).strip()
        # Dígitos
        m = re.search(r"\d+", s)
        if m:
            try:
                n = int(m.group())
                if n > 0:
                    return n
            except Exception:
                pass
        u = s.upper().replace("º", "").replace("°", "").strip()
        if u in _ROMAN:  # Romanos
            return _ROMAN[u]
        for k, n in _WORDS.items():  # Palabras
            if k in u:
                return n
    return None


def _cuatrimestre_label(val: str | None, nombre_fallback: str | None = None) -> str:
    """Devuelve 'Anual', '1º C', '2º C' o una letra (A/B/...)."""
    # 1) "Anual"
    for src in (val, nombre_fallback):
        if src and re.search(r"\banual\b", str(src), re.I):
            return "Anual"
    # 2) Número -> "Nº C"
    for src in (val, nombre_fallback):
        if not src:
            continue
        m = re.search(r"\d+", str(src))
        if m:
            try:
                n = int(m.group())
                if n > 0:
                    return f"{n}\N{MASCULINE ORDINAL INDICATOR} C"
            except Exception:
                pass
    # 3) Letra sola (A/B/C) -> tal cual
    s = (val or "").strip()
    if re.fullmatch(r"[A-Za-z]\w*", s):
        return s
    # 4) Último recurso
    return s


def espacio_etiqueta(e) -> str:
    """
    Etiqueta final sin la palabra 'año', como pediste:
      - '1º, 1º C Nombre'
      - '1º, Anual Nombre'
      - '1º, A Nombre'
      - Si falta algo, usa lo que encuentre (también puede deducir del nombre)
    """
    nombre = getattr(e, "nombre", "") or str(e)

    y_num = _extract_year(getattr(e, "anio", None), nombre)
    y = _to_ordinal(y_num)
    c = _cuatrimestre_label(getattr(e, "cuatrimestre", None), nombre)

    left = []
    if y:
        left.append(y)
    if c:
        left.append(c)

    if left:
        return f"{', '.join(left)} {nombre}".strip()
    return nombre
