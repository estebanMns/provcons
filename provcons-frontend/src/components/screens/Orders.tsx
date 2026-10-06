"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Insight } from "@/components/ui/Insight";

const steps = ["Orden creada", "Confirmada", "En preparación", "En tránsito", "Entregada"];

export function Orders() {
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">ÓRDENES / OC-1842</p>
          <div className="title-row"><h1>Orden de compra OC-1842</h1><Badge tone={confirmed ? "success" : "warning"}>{confirmed ? "Confirmada" : "Pendiente de confirmar"}</Badge></div>
          <p>Creada el 14 de mayo de 2025 · Constructora Bolívar</p>
        </div>
        <Button variant="secondary" icon="file">Descargar PDF</Button>
      </section>
      <section className="order-stepper">
        {steps.map((step, i) => {
          const complete = i === 0 || (confirmed && i === 1);
          const current = i === (confirmed ? 2 : 1);
          return (
            <div key={step} className={complete ? "complete" : current ? "current" : ""}>
              <span>{complete ? <Icon name="check" size={16} /> : i + 1}</span>
              <strong>{step}</strong>
              <small>{i === 0 ? "14 may, 9:32" : confirmed && i === 1 ? "Hoy, 10:48" : current ? "Siguiente paso" : "Pendiente"}</small>
            </div>
          );
        })}
      </section>
      <div className="order-layout">
        <div>
          <section className="card order-details">
            <div className="card-head"><div><h2>Resumen de la orden</h2><p>3 productos · Entrega estimada 16 de mayo</p></div></div>
            <table>
              <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Subtotal</th></tr></thead>
              <tbody>
                <tr><td>Varilla corrugada ½ pulg.</td><td>300 und</td><td>$ 42.500</td><td>$ 12.750.000</td></tr>
                <tr><td>Cemento gris UG 50 kg</td><td>150 bultos</td><td>$ 36.800</td><td>$ 5.520.000</td></tr>
                <tr><td>Bloque estructural N.° 5</td><td>960 und</td><td>$ 3.250</td><td>$ 3.120.000</td></tr>
              </tbody>
            </table>
            <div className="totals">
              <span>Subtotal <b>$ 21.390.000</b></span>
              <span>Logística <b>$ 480.000</b></span>
              <span>IVA <b>$ 4.064.100</b></span>
              <strong>Total <b>$ 25.934.100</b></strong>
            </div>
          </section>
          <section className="card delivery-card">
            <div><Icon name="route" /><span><small>DIRECCIÓN DE ENTREGA</small><strong>Proyecto Torre Alameda</strong><p>Carrera 7 # 82-38, Bogotá · Recibe: Andrés Rojas</p></span></div>
            <Badge tone="info">Entrega estimada: 16 may.</Badge>
          </section>
        </div>
        <aside className="insights-panel">
          <div className="insights-head"><span><Icon name="spark" /></span><div><p className="eyebrow">ANÁLISIS PROVCONS</p><h2>Condiciones recomendadas</h2></div></div>
          <p className="insight-intro">Analizamos 23 operaciones similares y el historial entre ambas empresas.</p>
          <Insight icon="wallet" label="Forma de pago" value="50% anticipo · 50% a 30 días" note="Buena liquidez para ambas partes" tone="green" />
          <Insight icon="route" label="Costo logístico estimado" value="$ 420.000 – $ 510.000" note="La oferta está dentro del rango" tone="blue" />
          <Insight icon="shield" label="Riesgo de la operación" value="Bajo" note="96% de cumplimiento histórico" tone="green" />
          <button className="explain-link"><Icon name="spark" size={16} /> Ver cómo llegamos a estas recomendaciones <Icon name="chevron" size={14} /></button>
          {!confirmed ? (
            <div className="decision-actions">
              <Button wide icon="check" onClick={() => setConfirming(true)}>Confirmar orden</Button>
              <Button wide variant="ghost">Solicitar un ajuste</Button>
              <button className="cancel-link">Cancelar orden</button>
            </div>
          ) : (
            <div className="confirmed-box"><Icon name="check" /><div><strong>Orden confirmada</strong><p>Notificamos a la constructora y enviamos el comprobante.</p></div></div>
          )}
        </aside>
      </div>
      {confirming && (
        <div className="modal-backdrop">
          <div className="modal">
            <span className="modal-icon"><Icon name="shield" size={26} /></span>
            <h2>¿Confirmar esta orden?</h2>
            <p>Al confirmar, te comprometes a preparar los productos bajo las condiciones acordadas. Esta acción quedará registrada.</p>
            <div className="modal-summary"><span>Total de la orden <strong>$ 25.934.100</strong></span><span>Entrega acordada <strong>16 de mayo</strong></span></div>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setConfirming(false)}>Volver a revisar</Button>
              <Button icon="check" onClick={() => { setConfirmed(true); setConfirming(false); }}>Sí, confirmar orden</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
