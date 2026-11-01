"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { getForecast } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import type { DeliveryDays, ForecastConfidence, ForecastOption, ProviderProfile, QuotationForecast } from "@/lib/api";

const CONFIDENCE_TONE: Record<ForecastConfidence, "warning" | "info" | "success"> = {
  baja: "warning", media: "info", alta: "success",
};

const SCENARIOS = [
  { key: "optimista", label: "Si todo sale bien" },
  { key: "probable", label: "Lo más probable" },
  { key: "pesimista", label: "Si el proveedor falla" },
] as const;

function pct(value: number) {
  return `${Math.round(value * 100)} %`;
}

function days(delivery: DeliveryDays | null) {
  return delivery ? `${delivery.median} días` : "Sin historial";
}

function materials(count: number) {
  return count === 1 ? "1 material" : `${count} materiales`;
}

function scenarioDays(value: number | null) {
  return value != null ? `${value} días` : "plazo sin historial";
}

function Trend({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: "var(--muted)" }}>Sin datos</span>;
  if (Math.abs(value) < 0.5) return <span>Estable</span>;
  const rising = value > 0;
  return (
    <span style={{ color: rising ? "var(--danger)" : "var(--success)" }}>
      {rising ? "↑" : "↓"} {Math.abs(value)} % / mes
    </span>
  );
}

// Predicción a futuro de cada opción de compra. Se carga aparte de la
// comparación: la comparación se ve de inmediato y esto llega después.
export function ForecastPanel({ quotationId }: { quotationId: number }) {
  const [forecast, setForecast] = useState<QuotationForecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getForecast(quotationId)
      .then((data) => { if (!cancelled) setForecast(data); })
      .catch((e: unknown) => { if (!cancelled) setError(e instanceof Error ? e.message : "No se pudo calcular la predicción"); });
    return () => { cancelled = true; };
  }, [quotationId]);

  if (error) {
    return (
      <section className="card forecast-panel">
        <div className="forecast-head"><Icon name="warning" /><strong>La predicción no está disponible</strong></div>
        <p className="forecast-muted">{error}. La comparación de abajo sigue siendo válida.</p>
      </section>
    );
  }

  if (!forecast) {
    return (
      <section className="card forecast-panel" aria-busy="true">
        <div className="forecast-head"><Icon name="spark" /><strong>Prediciendo qué pasará con cada opción…</strong></div>
        <div className="forecast-skeleton" />
        <div className="forecast-skeleton short" />
      </section>
    );
  }

  if (forecast.options.length === 0) return null;

  const best = forecast.options.find((o) => o.key === forecast.best_option_key) ?? forecast.options[0];
  const providers = new Map<number, ProviderProfile>(forecast.providers.map((p) => [p.provider_org_id, p]));
  const differs = forecast.current_recommendation_key != null && forecast.current_recommendation_key !== best.key;
  const today = forecast.options.find((o) => o.key === forecast.current_recommendation_key);

  return (
    <section className="card forecast-panel">
      <div className="forecast-head">
        <Icon name="spark" />
        <div>
          <span className="eyebrow">PREDICCIÓN A FUTURO</span>
          <h2>¿Qué pasará si eliges cada opción?</h2>
        </div>
        <Badge tone={forecast.narrative_source === "ia" ? "info" : "neutral"}>
          {forecast.narrative_source === "ia" ? "Redactado con IA" : "Sin IA"}
        </Badge>
      </div>

      <div className="forecast-best">
        <div>
          <span className="forecast-label">MEJOR OPCIÓN A FUTURO</span>
          <h3>{best.label}</h3>
          <p>{forecast.summary}</p>
          {differs && today && (
            <p className="forecast-note">
              Hoy se recomienda {today.label.charAt(0).toLowerCase() + today.label.slice(1)} ({formatCOP(today.cost_today)}), pero contando el riesgo
              de que falle su costo esperado es {formatCOP(today.expected_cost)} frente a {formatCOP(best.expected_cost)}.
            </p>
          )}
        </div>
        <div className="forecast-kpis">
          <span>Costo esperado <strong>{formatCOP(best.expected_cost)}</strong></span>
          <span>Probabilidad de cumplir <strong>{pct(best.success_probability)}</strong></span>
          <span>Entrega estimada <strong>{days(best.delivery_days)}</strong></span>
          <span>Confianza <strong><Badge tone={CONFIDENCE_TONE[best.confidence]}>{best.confidence}</Badge></strong></span>
        </div>
      </div>

      <div className="table-scroll">
        <table className="forecast-table">
          <thead>
            <tr>
              <th>Opción</th>
              <th>Costo hoy</th>
              <th>Costo esperado</th>
              <th>Cumplimiento</th>
              <th>Entrega</th>
              <th>Tendencia de precio</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {forecast.options.map((o) => (
              <OptionRow
                key={o.key}
                option={o}
                isBest={o.key === best.key}
                main={o.main_provider_id != null ? providers.get(o.main_provider_id) : undefined}
                open={openKey === o.key}
                onToggle={() => setOpenKey(openKey === o.key ? null : o.key)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <p className="forecast-muted" style={{ marginTop: 12 }}>
        Estimación con el historial real de órdenes de cada proveedor (entregas, rechazos, días de entrega y precios).
        El costo esperado suma el sobrecosto de recomprar de urgencia si el proveedor falla. Con poco historial la confianza es baja.
        {forecast.items_unavailable.length > 0 && ` Sin ofertas: ${forecast.items_unavailable.join(", ")}.`}
      </p>
    </section>
  );
}

function OptionRow({ option: o, isBest, main, open, onToggle }: {
  option: ForecastOption; isBest: boolean; main?: ProviderProfile; open: boolean; onToggle: () => void;
}) {
  return (
    <>
      <tr className={isBest ? "forecast-row-best" : undefined}>
        <td>
          <strong>{o.label}</strong>{isBest && <> <Badge tone="success">Mejor a futuro</Badge></>}<br />
          <small style={{ color: "var(--muted)" }}>
            {materials(o.items_from_main)}{o.complement_items > 0 ? ` + ${o.complement_items} con otro proveedor` : ""}
            {main && main.orders_closed > 0 ? ` · ${main.orders_delivered} de ${main.orders_closed} órdenes entregadas` : main ? " · sin órdenes cerradas" : ""}
          </small>
        </td>
        <td>{formatCOP(o.cost_today)}</td>
        <td><strong>{formatCOP(o.expected_cost)}</strong></td>
        <td>{pct(o.success_probability)} <Badge tone={CONFIDENCE_TONE[o.confidence]}>{o.confidence}</Badge></td>
        <td>{days(o.delivery_days)}</td>
        <td>{main ? <Trend value={main.price_trend_pct_30d} /> : <span style={{ color: "var(--muted)" }}>Varios</span>}</td>
        <td>
          <button className="forecast-toggle" onClick={onToggle} aria-expanded={open}>
            {open ? "Ocultar" : "Ver qué pasará"}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="forecast-detail">
          <td colSpan={7}>
            <div className="forecast-detail-body">
              <p>{o.narrative.que_pasara}</p>
              <div className="forecast-scenarios">
                {SCENARIOS.map((s) => (
                  <div key={s.key}>
                    <span>{s.label}</span>
                    <strong>{formatCOP(o.scenarios[s.key].cost)}</strong>
                    <small>{scenarioDays(o.scenarios[s.key].days)}</small>
                  </div>
                ))}
              </div>
              {o.narrative.riesgos.length > 0 && (
                <ul>
                  {o.narrative.riesgos.map((r) => <li key={r}><Icon name="warning" size={12} /> <span>{r}</span></li>)}
                </ul>
              )}
              {o.narrative.consejo && <p className="forecast-advice"><Icon name="check" size={12} /> <span>{o.narrative.consejo}</span></p>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
