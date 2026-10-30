import pytest

from app.modules.matching.text_matching import (
    MATCH_THRESHOLD, material_similarity, normalize_unit, specs_conflict, units_compatible,
)


@pytest.mark.parametrize("requested, offered", [
    ("Cemento gris", "Cemento gris x 50kg"),
    ("cemento gris 50 kg", "Cemento gris x 50kg"),
    ("Bultos de cemento", "Cemento gris x 50kg"),
    ("arena de río", "Arena de rio (lavada)"),
    ("grava", 'Grava triturada 3/4"'),
    ("varillas corrugadas 3/8", 'Varilla corrugada 3/8" x 6m'),
    ("bloque 15 x 20 x 40", "Bloque de concreto 15x20x40"),
    ("teja zinc calibre 28", "Teja de zinc cal. 28, 3m"),
    ("ALAMBRE NEGRO", "Alambre negro cal. 18 (rollo 1kg)"),
])
def test_mismo_material_escrito_distinto_coincide(requested, offered):
    assert material_similarity(requested, offered) >= MATCH_THRESHOLD


@pytest.mark.parametrize("requested, offered", [
    ('varilla 1/2"', 'Varilla corrugada 3/8" x 6m'),
    ("bloque 10x20x40", "Bloque de concreto 15x20x40"),
    ("teja zinc calibre 26", "Teja de zinc cal. 28, 3m"),
    ("cemento blanco", "Cemento gris x 50kg"),
    ("alambre negro", "Cemento gris x 50kg"),
    ("malla electrosoldada", "Teja de zinc cal. 28, 3m"),
])
def test_materiales_distintos_no_coinciden(requested, offered):
    assert material_similarity(requested, offered) < MATCH_THRESHOLD


def test_la_coincidencia_exacta_puntua_mas_que_la_parcial():
    exacta = material_similarity("varilla corrugada 3/8", 'Varilla corrugada 3/8" x 6m')
    parcial = material_similarity("varilla", 'Varilla corrugada 3/8" x 6m')
    assert exacta > parcial


def test_unidades_equivalentes():
    assert normalize_unit("Bultos") == "bulto"
    assert units_compatible("unid", "unidades")
    assert units_compatible("m3", "M3")
    assert not units_compatible("m3", "bulto")
    assert units_compatible("", "bulto")  # sin unidad no se puede descartar


def test_conflicto_de_medidas():
    assert specs_conflict('varilla 1/2"', 'Varilla corrugada 3/8" x 6m')
    assert specs_conflict("bloque 10x20x40", "Bloque de concreto 15x20x40")
    assert not specs_conflict("acero de refuerzo 3/8", 'Varilla corrugada 3/8" x 6m')
    assert not specs_conflict("cemento gris", "Cemento gris x 50kg")  # el pedido no trae medida
