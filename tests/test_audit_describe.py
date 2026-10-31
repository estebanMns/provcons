from app.core.audit import AuditLog
from app.modules.audit.service import describe


def _entry(action, resource_id=7, **details):
    return AuditLog(action=action, resource_type="Order", resource_id=resource_id, details=details)


def test_orden_creada_con_proveedor_y_total():
    text = describe(_entry("order.created", 12, provider_org_id=3, total_amount=10370000), {3: "Argos"})
    assert text == "Creó la orden #12 a Argos por $10.370.000"


def test_eventos_antiguos_sin_datos_no_dejan_huecos():
    assert describe(_entry("order.created", 1), {}) == "Creó la orden #1"
    assert describe(_entry("matching.run", 2, matches_generated=1), {}) == "Comparó proveedores para la cotización #2: 1 ofertas"
    assert describe(_entry("inventory.file_imported", None), {}) == "Subió el archivo de inventario"


def test_estados_de_la_orden():
    assert describe(_entry("order.en_transito", 5), {}) == "Despachó la orden #5"
    assert describe(_entry("order.rejected", 5), {}) == "Rechazó la orden #5"


def test_accion_desconocida_se_muestra_sin_romper():
    assert describe(_entry("algo.nuevo", 9), {}) == "algo.nuevo (Order #9)"
