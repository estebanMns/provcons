"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Attention } from "@/components/ui/Attention";
import { Icon } from "@/components/ui/Icon";
import { getDashboardSummary, getMe } from "@/lib/api";
import type { DashboardSummary, User } from "@/lib/api";
import type { IconName } from "@/lib/types";

interface Notice { icon: IconName; title: string; text: string; href: string }

// Avisos a partir del resumen: lo que la organización tiene pendiente
function noticesFrom(summary: DashboardSummary): Notice[] {
  const notices: Notice[] = [];
  if (summary.role === "proveedor") {
    if (summary.orders_to_confirm) notices.push({ icon: "warning", title: `${summary.orders_to_confirm} orden(es) por confirmar`, text: "Una constructora espera tu respuesta.", href: "/ordenes" });
    if (summary.orders_to_ship) notices.push({ icon: "truck", title: `${summary.orders_to_ship} orden(es) por despachar`, text: "Márcalas en tránsito cuando salgan.", href: "/ordenes" });
    if (summary.opportunities.length) notices.push({ icon: "spark", title: `${summary.opportunities.length} oportunidad(es) de venta`, text: "Cotizaciones abiertas donde coincide tu inventario.", href: "/dashboard" });
  } else {
    if (summary.awaiting_confirmation) notices.push({ icon: "truck", title: `${summary.awaiting_confirmation} orden(es) esperando al proveedor`, text: "Aún no las ha confirmado.", href: "/ordenes" });
    if (summary.in_transit) notices.push({ icon: "truck", title: `${summary.in_transit} orden(es) en camino`, text: "El proveedor ya despachó.", href: "/ordenes" });
    if (summary.open_quotations) notices.push({ icon: "file", title: `${summary.open_quotations} cotización(es) abierta(s)`, text: "Revisa la comparación y elige proveedor.", href: "/cotizaciones" });
  }
  return notices;
}

export function Topbar({ openMobile }: { openMobile: () => void }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    getMe().then(setUser).catch(() => {
      router.push("/login");
    });
  }, [router]);

  const refresh = () => {
    getDashboardSummary().then((s) => setNotices(noticesFrom(s))).catch(() => setNotices([]));
  };

  useEffect(refresh, []);

  const toggle = () => {
    if (!open) refresh();
    setOpen(!open);
  };

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={openMobile} aria-label="Abrir menú"><Icon name="menu" /></button>
      <div className="org-info">
        <strong>{user?.organization?.name || "Organización"}</strong>
        <span><span className="status-dot" /> {user?.organization?.type === "proveedor" ? "Proveedor" : "Constructora"}</span>
      </div>
      <div className="top-actions" style={{ position: "relative" }}>
        <button className={`icon-btn ${notices?.length ? "notification" : ""}`} aria-label="Pendientes" onClick={toggle}>
          <Icon name="bell" />{notices?.length ? <span /> : null}
        </button>
        {open && (
          <>
            <div style={{ position: "fixed", inset: 0, zIndex: 40 }} onClick={() => setOpen(false)} />
            <div className="card" style={{ position: "absolute", top: 48, right: 0, width: "min(340px, calc(100vw - 32px))", zIndex: 41, overflow: "hidden" }}>
              <div className="card-head" style={{ minHeight: 0 }}><div><h2>Pendientes</h2><p>Lo que espera por tu organización</p></div></div>
              {notices === null ? null : notices.length === 0 ? (
                <p style={{ padding: 18, margin: 0, color: "var(--muted)", fontSize: 11 }}>Todo al día. No tienes pendientes.</p>
              ) : notices.map((n) => (
                <Attention key={n.title} icon={n.icon} title={n.title} text={n.text} time="" onClick={() => go(n.href)} />
              ))}
            </div>
          </>
        )}
      </div>
    </header>
  );
}
