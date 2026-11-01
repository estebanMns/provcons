"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { listActivity } from "@/lib/api";
import { buildCsvInWorker } from "@/lib/workers";
import { formatDateTime } from "@/lib/format";
import type { AuditCategory, AuditEntry } from "@/lib/api";

const PAGE_SIZE = 50;

const FILTERS: { id: AuditCategory | "todo"; label: string }[] = [
  { id: "todo", label: "Todo" },
  { id: "ordenes", label: "Órdenes" },
  { id: "cotizaciones", label: "Cotizaciones" },
  { id: "inventario", label: "Inventario" },
  { id: "cuenta", label: "Cuenta" },
];

const CATEGORY_LABEL: Record<string, { label: string; tone: "info" | "success" | "warning" | "neutral" }> = {
  order: { label: "Orden", tone: "success" },
  quotation: { label: "Cotización", tone: "info" },
  matching: { label: "Comparación", tone: "info" },
  inventory: { label: "Inventario", tone: "warning" },
  user: { label: "Cuenta", tone: "neutral" },
  organization: { label: "Cuenta", tone: "neutral" },
};


async function downloadCsv(entries: AuditEntry[]) {
  // El CSV se arma en un Web Worker: con miles de eventos no congela la pantalla
  const { csv } = await buildCsvInWorker({
    header: ["Fecha", "Usuario", "Organización", "Acción", "Detalle"],
    rows: entries.map((e) => [
      new Date(e.created_at).toISOString(), e.actor_name ?? "", e.actor_organization_name ?? "", e.action, e.description,
    ]),
  });
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `historial-provcons-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function Audit() {
  const [filter, setFilter] = useState<AuditCategory | "todo">("todo");
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  // Primera página de cada filtro: el estado solo cambia cuando llega la
  // respuesta, y las respuestas de un filtro anterior se descartan
  useEffect(() => {
    let cancelled = false;
    listActivity(0, PAGE_SIZE, filter === "todo" ? undefined : filter)
      .then((page) => {
        if (cancelled) return;
        setEntries(page);
        setHasMore(page.length === PAGE_SIZE);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "No se pudo cargar el historial");
        setEntries([]);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  const changeFilter = (next: AuditCategory | "todo") => {
    if (next === filter) return;
    setEntries(null); // muestra "Cargando…" mientras llega el nuevo filtro
    setError("");
    setFilter(next);
  };

  const loadMore = async () => {
    if (!entries) return;
    setLoading(true);
    try {
      const page = await listActivity(entries.length, PAGE_SIZE, filter === "todo" ? undefined : filter);
      setEntries((current) => [...(current ?? []), ...page]);
      setHasMore(page.length === PAGE_SIZE);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el historial");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page narrow-page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRACIÓN</p>
          <h1>Historial de actividad</h1>
          <p>Registro de solo lectura de las acciones de tu organización y de las órdenes en las que participa.</p>
        </div>
        <Button
          variant="secondary" icon="file" disabled={!entries?.length || exporting}
          onClick={async () => {
            if (!entries) return;
            setExporting(true);
            try {
              await downloadCsv(entries);
            } catch (err) {
              setError(err instanceof Error ? err.message : "No se pudo exportar el registro");
            } finally {
              setExporting(false);
            }
          }}
        >
          {exporting ? "Exportando…" : "Exportar registro"}
        </Button>
      </section>

      <div className="table-tools card" style={{ marginBottom: 14 }}>
        <strong style={{ fontSize: 12, alignSelf: "center" }}>{entries ? `${entries.length}${hasMore ? "+" : ""} evento(s)` : "Cargando…"}</strong>
        <div>
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => changeFilter(f.id)}
              style={filter === f.id ? { background: "white", color: "var(--brand)", fontWeight: 700, boxShadow: "var(--shadow)" } : { background: "transparent", boxShadow: "none", fontWeight: 400 }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "var(--danger-soft)", borderColor: "#f3c9c6" }}>
          <p style={{ color: "var(--danger)", margin: 0 }}>{error}</p>
        </section>
      )}

      {entries !== null && entries.length === 0 && !error ? (
        <section className="card audit-card" style={{ padding: "3rem", textAlign: "center" }}>
          <div style={{ opacity: 0.5, marginBottom: "1rem" }}><Icon name="history" size={48} /></div>
          <h2 style={{ marginBottom: "0.5rem" }}>Sin actividad</h2>
          <p style={{ color: "var(--text-secondary)" }}>Aquí aparecerán las cotizaciones, órdenes y cambios de inventario de tu organización.</p>
        </section>
      ) : entries !== null && (
        <section className="card">
          <div className="table-scroll">
            <table>
              <thead><tr><th>Fecha</th><th>Quién</th><th>Acción</th></tr></thead>
              <tbody>
                {entries.map((e) => {
                  const category = CATEGORY_LABEL[e.action.split(".")[0]] ?? { label: "Otro", tone: "neutral" as const };
                  return (
                    <tr key={e.id}>
                      <td style={{ whiteSpace: "nowrap", color: "var(--muted)" }}>{formatDateTime(e.created_at)}</td>
                      <td>
                        <strong>{e.actor_name ?? "Sistema"}</strong>
                        {!e.own_organization && e.actor_organization_name && (
                          <small style={{ display: "block", color: "var(--muted)" }}>{e.actor_organization_name}</small>
                        )}
                      </td>
                      <td>
                        <Badge tone={category.tone}>{category.label}</Badge>
                        <span style={{ marginLeft: 8 }}>{e.description}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="card-actions" style={{ justifyContent: "center" }}>
              <Button variant="secondary" onClick={loadMore} disabled={loading}>
                {loading ? "Cargando…" : "Cargar más"}
              </Button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
