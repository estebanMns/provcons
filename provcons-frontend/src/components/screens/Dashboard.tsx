"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { viewPaths } from "@/lib/navigation";
import type { View } from "@/lib/types";
import { Attention } from "@/components/ui/Attention";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Opportunity } from "@/components/ui/Opportunity";
import { StatCard } from "@/components/ui/StatCard";
import { getDashboardSummary, getMe } from "@/lib/api";
import type { DashboardSummary, OrderStatus, RecentOrder, User } from "@/lib/api";

const copFormatter = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const formatCOP = (value: number) => copFormatter.format(value);
const formatDate = (iso: string) => new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short" });

const STATUS: Record<OrderStatus, { label: string; tone: "success" | "warning" | "danger" | "info" | "neutral" }> = {
  pendiente: { label: "Por confirmar", tone: "warning" },
  confirmada: { label: "Confirmada", tone: "info" },
  en_transito: { label: "En tránsito", tone: "info" },
  entregada: { label: "Entregada", tone: "success" },
  cancelada: { label: "Cancelada", tone: "danger" },
};

export function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");
  const go = (view: View) => router.push(viewPaths[view]);

  useEffect(() => {
    getMe()
      .then((me) => {
        setUser(me);
        getDashboardSummary()
          .then(setSummary)
          .catch((err) => setError(err instanceof Error ? err.message : "No se pudo cargar el resumen"));
      })
      .catch(() => router.push("/login"));
  }, [router]);

  if (!user) return null;
  const firstName = user.full_name?.split(" ")[0] || "Usuario";
  const provider = summary ? summary.role === "proveedor" : user.organization?.type === "proveedor";

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">RESUMEN</p>
          <h1>Bienvenido, {firstName}</h1>
          <p>{provider
            ? "Así va tu negocio: pedidos por atender y cotizaciones donde tu inventario puede vender."
            : "Así van tus compras: cotizaciones abiertas, pedidos en curso y lo que llevas comprometido."}</p>
        </div>
        <Button icon={provider ? "upload" : "plus"} onClick={() => go(provider ? "inventario" : "cotizaciones")}>
          {provider ? "Actualizar inventario" : "Nueva cotización"}
        </Button>
      </section>

      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "var(--danger-soft)", borderColor: "#f3c9c6" }}>
          <p style={{ color: "var(--danger)", margin: 0 }}>{error}</p>
        </section>
      )}

      {summary?.role === "constructora" && (
        <>
          <div className="stats-grid">
            <StatCard icon="file" tone="blue" label="Cotizaciones abiertas" value={String(summary.open_quotations)} detail="En comparación o negociación" />
            <StatCard icon="truck" tone="purple" label="Órdenes activas" value={String(summary.active_orders)} detail={`${summary.awaiting_confirmation} por confirmar · ${summary.in_transit} en camino`} />
            <StatCard icon="wallet" tone="orange" label="Compras comprometidas" value={formatCOP(summary.committed_spend)} detail="Órdenes activas y entregadas" />
            <StatCard icon="check" tone="green" label="Órdenes entregadas" value={String(summary.delivered_orders)} detail="Pedidos completados" />
          </div>
          <div className="dashboard-grid">
            <RecentOrders orders={summary.recent_orders} counterpartLabel="Proveedor" onOpen={() => go("ordenes")} />
            <section className="card">
              <div className="card-head"><div><h2>Pendientes</h2><p>Lo que requiere tu atención</p></div></div>
              {summary.awaiting_confirmation > 0 && (
                <Attention icon="truck" title={`${summary.awaiting_confirmation} orden(es) esperando al proveedor`} text="El proveedor debe confirmar antes del despacho." time="Órdenes" onClick={() => go("ordenes")} />
              )}
              {summary.open_quotations > 0 && (
                <Attention icon="file" title={`${summary.open_quotations} cotización(es) abierta(s)`} text="Revisa la comparación y elige proveedor." time="Cotizaciones" onClick={() => go("cotizaciones")} />
              )}
              {summary.awaiting_confirmation === 0 && summary.open_quotations === 0 && (
                <p style={{ padding: 20, color: "var(--muted)", fontSize: 11, margin: 0 }}>Todo al día. Sube una cotización cuando necesites materiales.</p>
              )}
            </section>
          </div>
        </>
      )}

      {summary?.role === "proveedor" && (
        <>
          <div className="stats-grid">
            <StatCard icon="box" tone="blue" label="Productos en inventario" value={String(summary.inventory_products)} detail="Disponibles para las comparaciones" />
            <StatCard icon="truck" tone="purple" label="Órdenes por atender" value={String(summary.orders_to_confirm + summary.orders_to_ship)} detail={`${summary.orders_to_confirm} por confirmar · ${summary.orders_to_ship} por despachar`} />
            <StatCard icon="spark" tone="orange" label="Oportunidades" value={formatCOP(summary.opportunities_value)} detail={`${summary.opportunities.length} cotización(es) donde coincide tu inventario`} />
            <StatCard icon="wallet" tone="green" label="Ventas entregadas" value={formatCOP(summary.delivered_sales)} detail="Órdenes completadas" />
          </div>
          <div className="dashboard-grid">
            <section className="card">
              <div className="card-head">
                <div><h2>Oportunidades de venta</h2><p>Cotizaciones abiertas donde tus productos coinciden y que aún nadie ha pedido</p></div>
              </div>
              {summary.opportunities.length === 0 ? (
                <p style={{ padding: 20, color: "var(--muted)", fontSize: 11, margin: 0 }}>
                  Todavía no hay cotizaciones abiertas con tus productos. Mantén tu inventario completo y con precios para aparecer en más comparaciones.
                </p>
              ) : summary.opportunities.map((o) => (
                <Opportunity
                  key={o.quotation_id}
                  name={o.title}
                  company={`${o.constructora} · ${formatDate(o.created_at)}`}
                  value={formatCOP(o.estimated_value)}
                  score={Math.round(o.score * 100)}
                  tags={[`${o.items_matched} de ${o.items_total} materiales`, ...(o.cheapest_items ? [`Más barato en ${o.cheapest_items}`] : [])]}
                />
              ))}
            </section>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 18, alignContent: "start" }}>
              <section className="card">
                <div className="card-head"><div><h2>Pendientes</h2><p>Pedidos que esperan por ti</p></div></div>
                {summary.orders_to_confirm > 0 && (
                  <Attention icon="warning" title={`${summary.orders_to_confirm} orden(es) por confirmar`} text="La constructora espera tu confirmación." time="Órdenes" onClick={() => go("ordenes")} />
                )}
                {summary.orders_to_ship > 0 && (
                  <Attention icon="truck" title={`${summary.orders_to_ship} orden(es) por despachar`} text="Márcalas en tránsito cuando salgan." time="Órdenes" onClick={() => go("ordenes")} />
                )}
                {summary.orders_to_confirm + summary.orders_to_ship === 0 && (
                  <p style={{ padding: 20, color: "var(--muted)", fontSize: 11, margin: 0 }}>No tienes pedidos pendientes.</p>
                )}
              </section>
              <RecentOrders orders={summary.recent_orders} counterpartLabel="Constructora" onOpen={() => go("ordenes")} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function RecentOrders({ orders, counterpartLabel, onOpen }: { orders: RecentOrder[]; counterpartLabel: string; onOpen: () => void }) {
  return (
    <section className="card">
      <div className="card-head">
        <div><h2>Últimas órdenes</h2><p>Los pedidos más recientes</p></div>
        {orders.length > 0 && <button onClick={onOpen}>Ver todas <Icon name="arrow" size={14} /></button>}
      </div>
      {orders.length === 0 ? (
        <p style={{ padding: 20, color: "var(--muted)", fontSize: 11, margin: 0 }}>Aún no hay órdenes.</p>
      ) : (
        <div className="table-scroll" style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>Orden</th><th>{counterpartLabel}</th><th>Estado</th><th style={{ textAlign: "right" }}>Total</th></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>#{o.id} <small style={{ color: "var(--muted)" }}>· {formatDate(o.created_at)}</small></td>
                  <td>{o.counterpart}</td>
                  <td><Badge tone={STATUS[o.status].tone}>{STATUS[o.status].label}</Badge></td>
                  <td style={{ textAlign: "right" }}>{o.total_amount != null ? formatCOP(o.total_amount) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
