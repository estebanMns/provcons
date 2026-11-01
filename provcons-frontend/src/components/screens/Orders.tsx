"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { advanceOrder, cancelOrder, confirmOrder, getMe, listOrders } from "@/lib/api";
import type { Order, OrderStatus, User } from "@/lib/api";
import { formatCOP, formatDate } from "@/lib/format";
import { ORDER_STATUS } from "@/lib/orderStatus";

const STEPS: { status: OrderStatus; label: string }[] = [
  { status: "pendiente", label: "Creada" },
  { status: "confirmada", label: "Confirmada" },
  { status: "en_transito", label: "En tránsito" },
  { status: "entregada", label: "Entregada" },
];

type Filter = "todas" | "activas" | "finalizadas";
const isActive = (o: Order) => o.status === "pendiente" || o.status === "confirmada" || o.status === "en_transito";

export function Orders() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [filter, setFilter] = useState<Filter>("activas");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [toCancel, setToCancel] = useState<Order | null>(null);

  useEffect(() => {
    getMe()
      .then((me) => {
        setUser(me);
        listOrders()
          .then(setOrders)
          .catch((err) => {
            setError(err instanceof Error ? err.message : "No se pudieron cargar las órdenes");
            setOrders([]);
          });
      })
      .catch(() => router.push("/login"));
  }, [router]);

  if (!user || orders === null) return null;

  const isProvider = user.organization?.type === "proveedor";

  const run = async (order: Order, action: (id: number) => Promise<Order>) => {
    setBusyId(order.id);
    setError("");
    try {
      const updated = await action(order.id);
      setOrders((list) => (list ?? []).map((o) => (o.id === updated.id ? updated : o)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar la orden");
    } finally {
      setBusyId(null);
      setToCancel(null);
    }
  };

  const visible = orders.filter((o) => filter === "todas" || (filter === "activas" ? isActive(o) : !isActive(o)));
  const counts = { todas: orders.length, activas: orders.filter(isActive).length, finalizadas: orders.filter((o) => !isActive(o)).length };

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">ÓRDENES</p>
          <h1>{isProvider ? "Órdenes recibidas" : "Tus órdenes"}</h1>
          <p>{isProvider
            ? "Pedidos que te hicieron las constructoras. Confírmalos y actualiza el envío."
            : "Pedidos creados desde tus cotizaciones. Cada proveedor confirma el suyo."}</p>
        </div>
        {!isProvider && <Button icon="plus" onClick={() => router.push("/cotizaciones")}>Nueva orden</Button>}
      </section>

      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "var(--danger-soft)", borderColor: "#f3c9c6" }}>
          <p style={{ color: "var(--danger)", margin: 0 }}>{error}</p>
        </section>
      )}

      {orders.length === 0 ? (
        <section className="card" style={{ padding: "3rem", textAlign: "center" }}>
          <div style={{ opacity: 0.5, marginBottom: "1rem" }}><Icon name="truck" size={48} /></div>
          <h2 style={{ marginBottom: "0.5rem" }}>Sin órdenes</h2>
          <p style={{ color: "var(--text-secondary)" }}>
            {isProvider
              ? "Cuando una constructora elija tus productos en una comparación, la orden aparecerá aquí."
              : "Sube una cotización, compara proveedores y elige el que más te convenga para crear tu primera orden."}
          </p>
        </section>
      ) : (
        <>
          <div className="table-tools card" style={{ marginBottom: 14 }}>
            <strong style={{ fontSize: 12, alignSelf: "center" }}>{counts.activas} activa(s)</strong>
            <div>
              {(["activas", "finalizadas", "todas"] as Filter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={filter === f ? { background: "white", color: "var(--brand)", fontWeight: 700, boxShadow: "var(--shadow)" } : { background: "transparent", boxShadow: "none", fontWeight: 400 }}
                >
                  {f[0].toUpperCase() + f.slice(1)} <b>{counts[f]}</b>
                </button>
              ))}
            </div>
          </div>

          {visible.length === 0 && (
            <p style={{ color: "var(--muted)", fontSize: 12, textAlign: "center", padding: "2rem" }}>No hay órdenes en este filtro.</p>
          )}

          <div style={{ display: "grid", gap: 14 }}>
            {visible.map((o) => {
              const counterpart = isProvider ? o.constructora_name : o.provider_name;
              const stepIndex = STEPS.findIndex((s) => s.status === o.status);
              const busy = busyId === o.id;
              return (
                <article key={o.id} className="card order-details">
                  <div className="match-main" style={{ flexWrap: "wrap" }}>
                    <div className="company-logo"><Icon name={isProvider ? "building" : "truck"} size={18} /></div>
                    <div>
                      <h2>Orden #{o.id} · {counterpart ?? "—"}</h2>
                      <p>
                        {o.quotation_title ? `Cotización «${o.quotation_title}» · ` : ""}
                        {formatDate(o.created_at)}
                        {o.payment_terms ? ` · pago ${o.payment_terms === "contado" ? "de contado" : "a cuotas"}` : ""}
                      </p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <Badge tone={ORDER_STATUS[o.status].tone}>{ORDER_STATUS[o.status].label}</Badge>
                      {o.total_amount != null && <strong style={{ display: "block", fontSize: 16, marginTop: 6 }}>{formatCOP(o.total_amount)}</strong>}
                    </div>
                  </div>

                  {o.status !== "cancelada" && (
                    <div className="order-stepper" style={{ margin: "0 18px 4px", gridTemplateColumns: "repeat(4, minmax(80px, 1fr))", overflowX: "auto" }}>
                      {STEPS.map((s, i) => (
                        <div key={s.status} className={i < stepIndex || o.status === "entregada" ? "complete" : i === stepIndex ? "current" : ""}>
                          <span>{i < stepIndex || o.status === "entregada" ? <Icon name="check" size={13} /> : i + 1}</span>
                          <strong>{s.label}</strong>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="table-scroll">
                    <table>
                      <thead><tr><th>Material pedido</th><th>Producto del proveedor</th><th>Cantidad</th><th>Precio unitario</th><th>Subtotal</th></tr></thead>
                      <tbody>
                        {o.items.map((item) => (
                          <tr key={item.id}>
                            <td>{item.requested_material}</td>
                            <td>{item.material_name}</td>
                            <td>{item.quantity} {item.unit}</td>
                            <td>{item.unit_price != null ? formatCOP(item.unit_price) : "—"}</td>
                            <td>{item.subtotal != null ? formatCOP(item.subtotal) : "—"}</td>
                          </tr>
                        ))}
                        {o.items.length === 0 && (
                          <tr><td colSpan={5} style={{ color: "var(--muted)", textAlign: "center" }}>Esta orden no tiene materiales registrados.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <OrderActions
                    order={o}
                    isProvider={isProvider}
                    busy={busy}
                    onConfirm={() => run(o, confirmOrder)}
                    onAdvance={() => run(o, advanceOrder)}
                    onCancel={() => setToCancel(o)}
                  />
                </article>
              );
            })}
          </div>
        </>
      )}

      {toCancel && (
        <div className="modal-backdrop" onClick={() => busyId === null && setToCancel(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <span className="modal-icon" style={{ color: "var(--danger)", background: "var(--danger-soft)" }}><Icon name="warning" size={26} /></span>
            <h2>{isProvider ? "¿Rechazar la orden?" : "¿Cancelar la orden?"}</h2>
            <p>
              {isProvider
                ? `La constructora verá la orden #${toCancel.id} como cancelada y podrá pedir esos materiales a otro proveedor.`
                : `La orden #${toCancel.id} a ${toCancel.provider_name} quedará cancelada y podrás pedir esos materiales a otro proveedor.`}
            </p>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setToCancel(null)} disabled={busyId !== null}>Volver</Button>
              <Button variant="danger" onClick={() => run(toCancel, cancelOrder)} disabled={busyId !== null}>
                {isProvider ? "Sí, rechazar" : "Sí, cancelar"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function OrderActions({ order, isProvider, busy, onConfirm, onAdvance, onCancel }: {
  order: Order; isProvider: boolean; busy: boolean;
  onConfirm: () => void; onAdvance: () => void; onCancel: () => void;
}) {
  const canCancel = order.status === "pendiente" || order.status === "confirmada";
  const buttons = [];

  if (isProvider) {
    if (order.status === "pendiente") buttons.push(<Button key="confirm" icon="check" onClick={onConfirm} disabled={busy}>Confirmar orden</Button>);
    if (order.status === "confirmada") buttons.push(<Button key="ship" icon="truck" onClick={onAdvance} disabled={busy}>Marcar en tránsito</Button>);
    if (order.status === "en_transito") buttons.push(<Button key="deliver" icon="check" onClick={onAdvance} disabled={busy}>Marcar entregada</Button>);
    if (canCancel) buttons.unshift(<Button key="reject" variant="ghost" onClick={onCancel} disabled={busy}>Rechazar</Button>);
  } else if (canCancel) {
    buttons.push(<Button key="cancel" variant="ghost" onClick={onCancel} disabled={busy}>Cancelar orden</Button>);
  }

  const hint = isProvider
    ? { pendiente: "Revisa los materiales y confirma si puedes cumplir.", confirmada: "Cuando despaches el pedido, márcalo en tránsito.", en_transito: "Marca la orden como entregada al llegar a la obra." }[order.status as string]
    : { pendiente: "Esperando a que el proveedor confirme.", confirmada: "El proveedor confirmó; pronto despachará.", en_transito: "El pedido va en camino." }[order.status as string];

  if (!buttons.length && !hint) return null;
  return (
    <div className="card-actions">
      <small style={{ color: "var(--muted)" }}>{hint ?? ""}</small>
      <div>{buttons}</div>
    </div>
  );
}
