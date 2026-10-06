import type { IconName } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";

const events: readonly [string, string, string, IconName][] = [
  ["Orden OC-1842 creada", "Carlos Méndez generó la orden desde la cotización COT-0248.", "Hoy, 9:32 a. m.", "file"],
  ["Condiciones de pago actualizadas", "Laura Gómez cambió el plazo de contado a 30 días.", "Ayer, 4:18 p. m.", "wallet"],
  ["Propuesta enviada", "Materiales del Norte envió una propuesta por $25.934.100.", "13 may, 11:06 a. m.", "arrow"],
  ["Inventario actualizado", "La IA procesó Inventario_mayo_2025.xlsx. Carlos confirmó 48 productos.", "12 may, 3:42 p. m.", "box"],
  ["Usuario agregado", "Laura Gómez fue agregada con rol Gestor.", "9 may, 8:20 a. m.", "building"],
];

export function Audit() {
  return (
    <div className="page narrow-page">
      <section className="page-heading">
        <div><p className="eyebrow">ADMINISTRACIÓN</p><h1>Historial de actividad</h1><p>Registro de solo lectura de las acciones realizadas en tu organización.</p></div>
        <Button variant="secondary" icon="file">Exportar registro</Button>
      </section>
      <section className="card audit-card">
        <div className="audit-filters">
          <div className="search-field"><Icon name="search" size={18} /><input placeholder="Buscar por orden, persona o acción" /></div>
          <button>Todas las acciones <Icon name="chevron" size={14} /></button>
          <button>Últimos 30 días <Icon name="chevron" size={14} /></button>
        </div>
        <div className="audit-list">
          {events.map(([title, detail, date, icon], i) => (
            <div className="audit-event" key={title}>
              <div className="audit-line"><span><Icon name={icon} /></span>{i < events.length - 1 && <i />}</div>
              <div>
                <strong>{title}</strong>
                <p>{detail}</p>
                <span className="audit-user"><b>{i === 1 ? "LG" : "CM"}</b> {i === 1 ? "Laura Gómez · Gestora" : "Carlos Méndez · Administrador"}</span>
              </div>
              <time>{date}</time>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
