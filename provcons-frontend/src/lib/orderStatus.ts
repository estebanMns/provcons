// Cómo se muestra cada estado de una orden (texto y color), según quién mira.
import type { OrderStatus } from "@/lib/api";

type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export const ORDER_STATUS: Record<OrderStatus, { label: string; tone: Tone }> = {
  pendiente: { label: "Esperando confirmación", tone: "warning" },
  confirmada: { label: "Confirmada", tone: "info" },
  en_transito: { label: "En tránsito", tone: "info" },
  entregada: { label: "Entregada", tone: "success" },
  cancelada: { label: "Cancelada", tone: "danger" },
};

// Para el proveedor una orden pendiente es algo que él debe confirmar
export const orderStatusFor = (status: OrderStatus, isProvider: boolean) =>
  status === "pendiente" && isProvider ? { ...ORDER_STATUS.pendiente, label: "Por confirmar" } : ORDER_STATUS[status];
