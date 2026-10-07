import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";

export function Audit() {
  return (
    <div className="page narrow-page">
      <section className="page-heading">
        <div><p className="eyebrow">ADMINISTRACIÓN</p><h1>Historial de actividad</h1><p>Registro de solo lectura de las acciones realizadas en tu organización.</p></div>
        <Button variant="secondary" icon="file">Exportar registro</Button>
      </section>
      <section className="card audit-card" style={{ padding: "3rem", textAlign: "center" }}>
        <div style={{ opacity: 0.5, marginBottom: "1rem" }}>
          <Icon name="history" size={48} />
        </div>
        <h2 style={{ marginBottom: "0.5rem" }}>Sin historial</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          El historial de actividad de tu organización aparecerá aquí una vez comiences a crear órdenes, cotizaciones u actualizar datos.
        </p>
      </section>
    </div>
  );
}
