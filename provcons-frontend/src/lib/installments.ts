// La misma fórmula que el backend (app/modules/transactions/credit.py), solo
// para ver la cuota al instante mientras se escribe la tasa. El valor que se
// guarda lo recalcula siempre el backend.
import type { InstallmentVerdict } from "@/lib/api";

export function installmentPlan(amount: number, installments: number, monthlyRatePct: number) {
  // Una sola cuota es pago de contado: sin interés
  const rate = installments > 1 ? monthlyRatePct / 100 : 0;
  const payment = rate === 0 ? amount / installments : (amount * rate) / (1 - (1 + rate) ** -installments);
  const total = payment * installments;
  return { payment, total, interest: total - amount };
}

export const VERDICT: Record<InstallmentVerdict, { label: string; tone: "success" | "warning" | "danger" }> = {
  conveniente: { label: "Conveniente", tone: "success" },
  con_riesgo: { label: "Con riesgo", tone: "warning" },
  no_conveniente: { label: "No conveniente", tone: "danger" },
};

export const addDays = (from: Date, days: number) => new Date(from.getTime() + days * 86_400_000);
