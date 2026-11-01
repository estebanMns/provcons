"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { getMetricsSummary } from "@/lib/api";
import type { LatencyStats, MetricsSummary } from "@/lib/api";

const REFRESH_MS = 10_000;

// Umbrales oficiales de Core Web Vitals (bueno / mejorable / malo), en ms salvo CLS
const VITALS: { name: string; label: string; good: number; poor: number; unit: string }[] = [
  { name: "LCP", label: "Carga del contenido principal", good: 2500, poor: 4000, unit: "ms" },
  { name: "INP", label: "Respuesta a la interacción", good: 200, poor: 500, unit: "ms" },
  { name: "CLS", label: "Estabilidad visual", good: 0.1, poor: 0.25, unit: "" },
  { name: "FCP", label: "Primer contenido visible", good: 1800, poor: 3000, unit: "ms" },
  { name: "TTFB", label: "Respuesta del servidor", good: 800, poor: 1800, unit: "ms" },
];

const ms = (v: number | null | undefined) => (v == null ? "—" : `${v.toLocaleString("es-CO", { maximumFractionDigits: 1 })} ms`);

function rating(value: number, good: number, poor: number) {
  if (value <= good) return { label: "Bueno", tone: "success" as const };
  if (value <= poor) return { label: "Mejorable", tone: "warning" as const };
  return { label: "Malo", tone: "danger" as const };
}

function LatencyTable({ title, note, rows }: { title: string; note: string; rows: (LatencyStats & { name: string; errors?: number })[] }) {
  return (
    <section className="card" style={{ marginBottom: 18 }}>
      <div className="card-head"><div><h2>{title}</h2><p>{note}</p></div></div>
      {rows.length === 0 ? (
        <p style={{ padding: 20, margin: 0, color: "var(--muted)", fontSize: 11 }}>Aún no hay mediciones.</p>
      ) : (
        <div className="table-scroll" style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>Operación</th><th>Llamadas</th><th>p50</th><th>p95</th><th>p99</th><th>Errores</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td><code style={{ fontSize: 11 }}>{r.name}</code></td>
                  <td>{r.count}</td>
                  <td>{ms(r.p50)}</td>
                  <td><strong>{ms(r.p95)}</strong></td>
                  <td>{ms(r.p99)}</td>
                  <td>{r.errors ? <Badge tone="danger">{r.errors}</Badge> : 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function Performance() {
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = () => getMetricsSummary()
      .then((s) => { if (!cancelled) { setSummary(s); setError(""); } })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "No se pudieron cargar las métricas"); });
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  const lag = summary?.event_loop_lag_ms;
  const grpc = summary?.grpc[0];
  const ai = summary?.ai ?? [];
  const totalRequests = summary?.http.reduce((sum, r) => sum + r.count, 0) ?? 0;

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">OBSERVABILIDAD</p>
          <h1>Rendimiento</h1>
          <p>Métricas del servidor en vivo (se actualizan cada 10 s) y Web Vitals medidos en los navegadores de los usuarios. También en formato Prometheus en <code>/metrics</code>.</p>
        </div>
      </section>

      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "var(--danger-soft)", borderColor: "#f3c9c6" }}>
          <p style={{ color: "var(--danger)", margin: 0 }}>{error}</p>
        </section>
      )}

      {summary && (
        <>
          <div className="stats-grid">
            <StatCard icon="route" tone="blue" label="Peticiones atendidas" value={totalRequests.toLocaleString("es-CO")}
              detail={`Servidor activo hace ${Math.round(summary.uptime_seconds / 60)} min`} />
            <StatCard icon="spark" tone="purple" label="Retraso del event loop" value={ms(lag?.current)}
              detail={`p95 ${ms(lag?.p95)} · ${lag && (lag.p95 ?? 0) < 50 ? "sin bloqueos" : "revisar código síncrono"}`} />
            <StatCard icon="grid" tone="green" label="Motor gRPC (p95)" value={ms(grpc?.p95)}
              detail={`${grpc?.count ?? 0} llamadas · ${summary.engine_fallbacks} respaldo(s) local(es)`} />
            <StatCard icon="file" tone="orange" label="IA Gemini (p95)" value={ms(ai.length ? Math.max(...ai.map((a) => a.p95 ?? 0)) : null)}
              detail={`${ai.reduce((s, a) => s + a.count, 0)} llamadas · ${ai.reduce((s, a) => s + a.errors, 0)} errores`} />
          </div>

          <section className="card" style={{ marginBottom: 18 }}>
            <div className="card-head"><div><h2>Web Vitals</h2><p>Experiencia real en el navegador, percentil 75 (criterio de Google)</p></div></div>
            <div className="table-scroll" style={{ overflowX: "auto" }}>
              <table>
                <thead><tr><th>Métrica</th><th>Qué mide</th><th>Muestras</th><th>p75</th><th>Evaluación</th></tr></thead>
                <tbody>
                  {VITALS.map((v) => {
                    const data = summary.web_vitals[v.name];
                    const value = data?.p75;
                    const r = value != null ? rating(value, v.good, v.poor) : null;
                    return (
                      <tr key={v.name}>
                        <td><strong>{v.name}</strong></td>
                        <td>{v.label}</td>
                        <td>{data?.count ?? 0}</td>
                        <td>{value == null ? "—" : v.unit ? `${Math.round(value)} ${v.unit}` : value.toFixed(3)}</td>
                        <td>{r ? <Badge tone={r.tone}>{r.label}</Badge> : <small style={{ color: "var(--muted)" }}>Sin datos</small>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <LatencyTable title="API por ruta" note="Ordenadas por p95: las más lentas primero"
            rows={summary.http.map((r) => ({ ...r, name: `${r.method} ${r.route}` }))} />
          <LatencyTable title="Servicios externos" note="Motor de comparación (gRPC) e IA (Gemini)"
            rows={[...summary.grpc.map((g) => ({ ...g, name: `gRPC ${g.method}` })), ...ai.map((a) => ({ ...a, name: `Gemini (${a.kind})` }))]} />
        </>
      )}
    </div>
  );
}
