"use client";

import { useReportWebVitals } from "next/web-vitals";
import { API_BASE } from "@/lib/api";

// Envía al backend las métricas de experiencia del navegador (Core Web
// Vitals): LCP (carga), INP (respuesta a la interacción), CLS (estabilidad
// visual), FCP y TTFB. Se ven agregadas en la pantalla "Rendimiento".
export function WebVitals() {
  useReportWebVitals((metric) => {
    if (!["LCP", "INP", "CLS", "FCP", "TTFB", "FID"].includes(metric.name)) return;
    // keepalive: el envío termina aunque el usuario cambie de página
    fetch(`${API_BASE}/metrics/web-vitals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: metric.name, value: metric.value }),
      keepalive: true,
    }).catch(() => {
      // las métricas nunca deben afectar la experiencia del usuario
    });
  });
  return null;
}
