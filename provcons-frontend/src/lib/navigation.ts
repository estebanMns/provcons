import type { IconName, View } from "./types";

export const viewPaths: Record<View, string> = {
  dashboard: "/dashboard",
  inventario: "/inventario",
  cotizaciones: "/cotizaciones",
  ordenes: "/ordenes",
  auditoria: "/auditoria",
  rendimiento: "/rendimiento",
};

export const navItems: { id: View; label: string; icon: IconName }[] = [
  { id: "dashboard", label: "Resumen", icon: "grid" },
  { id: "inventario", label: "Inventario", icon: "box" },
  { id: "cotizaciones", label: "Cotizaciones", icon: "file" },
  { id: "ordenes", label: "Órdenes", icon: "truck" },
  { id: "auditoria", label: "Historial", icon: "history" },
  { id: "rendimiento", label: "Rendimiento", icon: "route" },
];
