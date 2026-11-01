// Formatos de la app (pesos colombianos y fechas en español de Colombia).
// Un solo lugar para que todas las pantallas muestren lo mismo.

const copFormatter = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });

export const formatCOP = (value: number) => copFormatter.format(value);

export const formatDate = (iso: string, withYear = true) =>
  new Date(iso).toLocaleDateString("es-CO", withYear ? { day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" });

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString("es-CO", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
