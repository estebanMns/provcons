"use client";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";

export function Orders() {
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">ÓRDENES</p>
          <h1>Tus órdenes</h1>
          <p>Aquí aparecerán todas tus órdenes una vez comiences a crearlas.</p>
        </div>
        <Button icon="plus">Nueva orden</Button>
      </section>

      <section className="card" style={{ padding: "3rem", textAlign: "center" }}>
        <Icon name="truck" size={48} style={{ opacity: 0.5, marginBottom: "1rem" }} />
        <h2 style={{ marginBottom: "0.5rem" }}>Sin órdenes</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          No tienes órdenes creadas aún. Crea tu primera orden para comenzar a gestionar tus compras y ventas.
        </p>
      </section>
    </div>
  );
}
