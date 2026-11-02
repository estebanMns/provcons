"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { confirmOrder, getOrderEvaluation } from "@/lib/api";
import type { Order, OrderEvaluation } from "@/lib/api";
import { formatCOP, formatDate } from "@/lib/format";
import { VERDICT, addDays, installmentPlan } from "@/lib/installments";

const MAX_DAYS = 180;

// Antes de aceptar, el proveedor ve cómo cumple la constructora, elige
// cuántas cuotas darle y en cuántos días entrega.
export function AcceptOrderModal({ order, onClose, onDone }: { order: Order; onClose: () => void; onDone: (updated: Order) => void }) {
  const [evaluation, setEvaluation] = useState<OrderEvaluation | null>(null);
  const [loadError, setLoadError] = useState("");
  const [installments, setInstallments] = useState(1);
  const [rate, setRate] = useState("0");
  const [days, setDays] = useState("5");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getOrderEvaluation(order.id)
      .then((e) => { if (!cancelled) setEvaluation(e); })
      .catch((err) => { if (!cancelled) setLoadError(err instanceof Error ? err.message : "No se pudo evaluar a la constructora"); });
    return () => { cancelled = true; };
  }, [order.id]);

  const amount = order.total_amount ?? 0;
  const rateValue = Math.min(10, Math.max(0, Number(rate.replace(",", ".")) || 0));
  const daysValue = Math.round(Number(days));
  const daysValid = Number.isFinite(daysValue) && daysValue >= 1 && daysValue <= MAX_DAYS;
  const plan = installmentPlan(amount, installments, rateValue);
  const verdict = evaluation?.options.find((o) => o.installments === installments)?.verdict;
  // De contado como lo pidió la constructora se confirma de una vez; lo demás es una propuesta
  const needsApproval = installments > 1 || order.payment_terms === "cuotas";

  const submit = async () => {
    if (!daysValid) { setError(`Escribe los días de entrega (de 1 a ${MAX_DAYS}).`); return; }
    setSaving(true);
    setError("");
    try {
      onDone(await confirmOrder(order.id, {
        delivery_days: daysValue, installments, monthly_rate_pct: installments > 1 ? rateValue : 0, note: note.trim() || undefined,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo aceptar la orden");
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={() => !saving && onClose()}>
      <div className="modal accept-modal" role="dialog" aria-labelledby="accept-title" onClick={(e) => e.stopPropagation()}>
        <div className="accept-head">
          <div>
            <p className="eyebrow">ORDEN #{order.id} · {formatCOP(amount)}</p>
            <h2 id="accept-title">Revisar y aceptar</h2>
            <p>{order.constructora_name ?? "La constructora"} pidió pago {order.payment_terms === "cuotas" ? "a cuotas" : "de contado"}.</p>
          </div>
          <button className="accept-close" onClick={onClose} disabled={saving} aria-label="Cerrar"><Icon name="close" size={18} /></button>
        </div>

        <div className="accept-grid">
          <section className="accept-client">
            <h3><Icon name="shield" size={16} /> ¿La constructora paga bien?</h3>
            {loadError ? (
              <p className="accept-error">{loadError}</p>
            ) : !evaluation ? (
              <><div className="forecast-skeleton" /><div className="forecast-skeleton short" /></>
            ) : (
              <>
                <div className="accept-score">
                  <strong>{Math.round(evaluation.score * 100)} %</strong>
                  <span>cumplimiento estimado<br /><Badge tone={evaluation.confidence === "baja" ? "warning" : "info"}>confianza {evaluation.confidence}</Badge></span>
                </div>
                <ul className="accept-facts">
                  <li><span>Órdenes recibidas</span><b>{evaluation.history.orders_delivered}</b></li>
                  <li><span>Canceladas por ella</span><b>{evaluation.history.orders_cancelled_by_client}</b></li>
                  <li><span>Total comprado</span><b>{formatCOP(evaluation.history.total_purchased)}</b></li>
                  <li><span>Órdenes contigo</span><b>{evaluation.history.orders_with_you}</b></li>
                  <li><span>En la plataforma</span><b>{evaluation.history.months_on_platform < 1 ? "menos de 1 mes" : `${Math.floor(evaluation.history.months_on_platform)} mes(es)`}</b></li>
                </ul>
                <ul className="accept-reasons">{evaluation.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                <small className="forecast-muted">ProvCons aún no registra pagos: se mide por las órdenes que recibió y las que canceló.</small>
              </>
            )}
          </section>

          <section className="accept-terms">
            <h3><Icon name="wallet" size={16} /> Cuotas</h3>
            {evaluation && <p className="accept-max">Te recomendamos hasta <b>{evaluation.max_installments} cuota{evaluation.max_installments !== 1 ? "s" : ""}</b>.</p>}
            <div className="installment-options" role="radiogroup" aria-label="Número de cuotas">
              {(evaluation?.options ?? [1, 2, 3, 4, 6, 9, 12].map((n) => ({ installments: n, verdict: undefined }))).map((o) => (
                <button
                  key={o.installments}
                  role="radio"
                  aria-checked={installments === o.installments}
                  className={`installment-option ${o.verdict ? `is-${o.verdict}` : ""} ${installments === o.installments ? "selected" : ""}`}
                  onClick={() => setInstallments(o.installments)}
                  disabled={saving}
                  title={o.verdict ? VERDICT[o.verdict].label : undefined}
                >
                  {o.installments === 1 ? "Contado" : o.installments}
                </button>
              ))}
            </div>

            {installments > 1 && (
              <label className="accept-field">Interés mensual (%)
                <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} disabled={saving} />
              </label>
            )}

            <div className="accept-plan">
              <span>{installments === 1 ? "Pago de contado" : `${installments} cuotas de`} <strong>{formatCOP(plan.payment)}</strong></span>
              {installments > 1 && <small>Total {formatCOP(plan.total)} · interés {formatCOP(plan.interest)}</small>}
              {verdict && <Badge tone={VERDICT[verdict].tone}>{VERDICT[verdict].label}</Badge>}
            </div>
            {evaluation && installments > evaluation.max_installments && (
              <p className="accept-warning"><Icon name="warning" size={14} /> Son más cuotas de las recomendadas: el riesgo de no cobrar es mayor.</p>
            )}

            {evaluation && (
              <div className="accept-ai">
                <span className="forecast-label">{evaluation.narrative.source === "ia" ? "EXPLICACIÓN CON IA" : "EXPLICACIÓN"}</span>
                <p>{evaluation.narrative.summary}</p>
                {evaluation.narrative.advice && <p className="forecast-advice"><Icon name="check" size={14} /> {evaluation.narrative.advice}</p>}
              </div>
            )}

            <h3><Icon name="truck" size={16} /> Entrega</h3>
            <label className="accept-field">Días para entregar
              <input type="number" min={1} max={MAX_DAYS} value={days} onChange={(e) => setDays(e.target.value)} disabled={saving} />
            </label>
            {daysValid && <small className="forecast-muted">Llegaría aprox. el {formatDate(addDays(new Date(), daysValue).toISOString())}.</small>}

            <label className="accept-field">Nota para la constructora (opcional)
              <input maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ej.: la primera cuota al despachar" disabled={saving} />
            </label>
          </section>
        </div>

        {error && <p className="accept-error">{error}</p>}
        <div className="accept-footer">
          <small>{needsApproval ? "La constructora debe aceptar estas condiciones antes de que la orden quede confirmada." : "La orden queda confirmada con este tiempo de entrega."}</small>
          <div className="modal-actions">
            <Button variant="secondary" onClick={onClose} disabled={saving}>Volver</Button>
            <Button icon="check" onClick={submit} disabled={saving || !daysValid}>{saving ? "Enviando…" : needsApproval ? "Enviar propuesta" : "Confirmar orden"}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
