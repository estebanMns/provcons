"""Comparación de nombres de materiales de construcción.

Los proveedores y las constructoras escriben el mismo material de formas
distintas ("Cemento gris x 50kg", "cemento gris", "Bultos de cemento gris"),
así que comparar con == casi nunca encuentra coincidencias. Aquí se normaliza
el texto y se calcula una similitud que:
- ignora mayúsculas, tildes, plurales y palabras de relleno
- respeta las medidas: una varilla de 1/2" NO es una de 3/8"
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

# Palabras que no aportan a identificar el material
_STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "en", "con", "para", "por", "y", "o",
    "x", "a", "al", "tipo", "ref", "referencia", "marca", "aprox",
}

# Unidades escritas de distintas formas -> forma canónica
_UNIT_ALIASES = {
    "bulto": "bulto", "bultos": "bulto", "saco": "bulto", "sacos": "bulto", "bto": "bulto",
    "unidad": "unidad", "unidades": "unidad", "und": "unidad", "unds": "unidad", "un": "unidad",
    "unid": "unidad", "u": "unidad", "pieza": "unidad", "piezas": "unidad", "pza": "unidad",
    "m3": "m3", "mt3": "m3", "metro cubico": "m3", "metros cubicos": "m3",
    "m2": "m2", "mt2": "m2", "metro cuadrado": "m2", "metros cuadrados": "m2",
    "m": "m", "ml": "m", "metro": "m", "metros": "m", "metro lineal": "m",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg", "kilogramos": "kg",
    "ton": "ton", "tonelada": "ton", "toneladas": "ton", "t": "ton",
    "rollo": "rollo", "rollos": "rollo",
    "galon": "galon", "galones": "galon", "gal": "galon",
    "litro": "litro", "litros": "litro", "l": "litro", "lt": "litro",
    "caja": "caja", "cajas": "caja",
}

# Medidas dentro del nombre. Cada categoría se compara por separado: si ambos
# nombres traen una medida de la misma categoría y no coinciden, son materiales
# distintos.
_SPEC_PATTERNS = {
    "fraccion": re.compile(r"\b\d+/\d+\b"),
    "dimensiones": re.compile(r"\b\d+(?:[.,]\d+)?(?:x\d+(?:[.,]\d+)?)+\b"),
    "medida": re.compile(r"\b\d+(?:[.,]\d+)?(?:mm|cm|m|kg|lb|psi|mpa|gal|l)\b"),
    "calibre": re.compile(r"\bcal\s*\d+\b"),
}

# Por debajo de esta similitud se considera que no es el mismo material
MATCH_THRESHOLD = 0.6


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_text(text: str) -> str:
    text = _strip_accents((text or "").lower())
    text = text.replace('"', " ").replace("''", " ").replace("”", " ").replace("“", " ")
    text = re.sub(r"calibre", "cal", text)
    text = re.sub(r"(\d)\s*(mm|cm|kg|lb|psi|mpa|gal)\b", r"\1\2", text)  # "50 kg" -> "50kg"
    text = re.sub(r"(\d)\s*m\b", r"\1m", text)
    # "15 x 20 x 40" -> "15x20x40", pero "3/8 x 6m" se deja separado: ahí la x
    # une dos medidas distintas (diámetro y largo), no las dimensiones de una pieza.
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"(?<![/\d])(\d+(?:x\d+)*)\s+x\s*(\d+)(?![\d.,]*[a-wyz/])", r"\1x\2", text)
        text = re.sub(r"(?<![/\d])(\d+(?:x\d+)*)x\s+(\d+)(?![\d.,]*[a-wyz/])", r"\1x\2", text)
    text = re.sub(r"cal\.?\s*(\d)", r"cal \1", text)
    text = re.sub(r"[^a-z0-9/.,x ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _stem(word: str) -> str:
    """Singulariza de forma simple: bloques -> bloque, varillas -> varilla."""
    if len(word) > 4 and word.endswith("es") and word[-3] not in "aeiou":
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def normalize_unit(unit: str | None) -> str:
    key = normalize_text(unit or "").rstrip(".")
    return _UNIT_ALIASES.get(key, key)


@dataclass(frozen=True)
class MaterialName:
    words: frozenset[str]
    specs: dict[str, frozenset[str]]
    normalized: str


def parse_material(name: str) -> MaterialName:
    normalized = normalize_text(name)
    specs = {
        kind: frozenset(m.replace(",", ".").replace(" ", "") for m in pattern.findall(normalized))
        for kind, pattern in _SPEC_PATTERNS.items()
    }
    without_specs = normalized
    for pattern in _SPEC_PATTERNS.values():
        without_specs = pattern.sub(" ", without_specs)
    words = frozenset(
        _stem(w) for w in re.findall(r"[a-z]+", without_specs)
        if w not in _STOPWORDS and len(w) > 1 and w not in _UNIT_ALIASES
    )
    return MaterialName(words=words, specs={k: v for k, v in specs.items() if v}, normalized=normalized)


def material_similarity(requested: str, offered: str) -> float:
    """Similitud entre 0 y 1 entre lo que pide la constructora y lo que ofrece
    el proveedor."""
    req, off = parse_material(requested), parse_material(offered)
    if not req.words or not off.words:
        return 0.0

    common = req.words & off.words
    if not common:
        return 0.0

    # Cuánto de lo pedido aparece en la oferta (lo importante), y cuánto de la
    # oferta sobra (un nombre más específico penaliza poco).
    coverage = len(common) / len(req.words)
    precision = len(common) / len(off.words)
    sequence = SequenceMatcher(None, " ".join(sorted(req.words)), " ".join(sorted(off.words))).ratio()
    score = 0.6 * coverage + 0.15 * precision + 0.25 * sequence

    for kind, req_values in req.specs.items():
        off_values = off.specs.get(kind)
        if off_values and not (req_values & off_values):
            score *= 0.4  # misma categoría de medida, valor distinto: otro material
        elif off_values:
            score = min(1.0, score + 0.05)

    return round(score, 3)


def specs_conflict(requested: str, offered: str) -> bool:
    """True si ambos nombres traen una medida del mismo tipo con valores
    distintos (varilla 1/2" vs 3/8"). Es una regla dura: ni la revisión con IA
    puede declarar equivalentes dos materiales con medidas distintas."""
    req, off = parse_material(requested), parse_material(offered)
    return any(
        off.specs.get(kind) and not (values & off.specs[kind])
        for kind, values in req.specs.items()
    )


def units_compatible(requested_unit: str | None, offered_unit: str | None) -> bool:
    req, off = normalize_unit(requested_unit), normalize_unit(offered_unit)
    return not req or not off or req == off
