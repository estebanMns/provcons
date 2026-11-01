"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ForecastPanel } from "@/components/quotations/ForecastPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Criterion } from "@/components/ui/Criterion";
import { Icon } from "@/components/ui/Icon";
import { Score } from "@/components/ui/Score";
import { createOrders, getComparison, getMe, listQuotations, rerunComparison, uploadQuotationFile } from "@/lib/api";
import { precheckUpload, rememberUpload } from "@/lib/uploadCheck";
import { formatCOP, formatDate } from "@/lib/format";
import type { User, QuotationResult, QuotationSummary, PaymentTerms } from "@/lib/api";

type Stage = "list" | "upload" | "processing" | "results";

const QUOTATION_STATUS: Record<QuotationSummary["status"], { label: string; tone: "success" | "warning" | "danger" | "info" | "neutral" }> = {
  abierta: { label: "Abierta", tone: "info" },
  en_negociacion: { label: "En negociación", tone: "warning" },
  cerrada: { label: "Cerrada", tone: "success" },
  cancelada: { label: "Cancelada", tone: "danger" },
};

// Lo que la constructora está por comprar: un proveedor o la mejor combinación
interface Purchase {
  title: string;
  matchIds: number[];
  total: number;
  providers: string[];
  itemsCount: number;
}

const initials = (name: string) => name.split(/\s+/).filter((w) => w.length > 2).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || name.slice(0, 2).toUpperCase();

export function Quotations() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stage, setStage] = useState<Stage>("list");
  const [quotations, setQuotations] = useState<QuotationSummary[] | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [fileName, setFileName] = useState<string>("");
  const [quotationResult, setQuotationResult] = useState<QuotationResult | null>(null);
  const [error, setError] = useState<string>("");
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [paymentTerms, setPaymentTerms] = useState<PaymentTerms>("contado");
  const [purchasing, setPurchasing] = useState(false);
  const [purchaseError, setPurchaseError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadQuotations = () => {
    listQuotations()
      .then(setQuotations)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "No se pudieron cargar las cotizaciones");
        setQuotations([]);
      });
  };

  useEffect(() => {
    getMe()
      .then((userData) => {
        setUser(userData);
        if (userData.organization?.type !== "constructora") {
          router.push("/dashboard");
          return;
        }
        loadQuotations();
      })
      .catch(() => {
        router.push("/login");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- carga inicial, una sola vez
  }, [router]);

  const isConstructora = user?.organization?.type === "constructora";

  const backToList = () => {
    setStage("list");
    setQuotationResult(null);
    setError("");
    loadQuotations();
  };

  const openComparison = async (quotationId: number, rerun: boolean) => {
    setLoadingId(quotationId);
    setRerunning(rerun);
    setError("");
    try {
      setQuotationResult(await (rerun ? rerunComparison(quotationId) : getComparison(quotationId)));
      setStage("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo abrir la comparación");
    } finally {
      setLoadingId(null);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // permite volver a elegir el mismo archivo tras un error
    if (file) {
      setFileName(file.name);
      await processQuotationFile(file);
    }
  };

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const processQuotationFile = async (file: File) => {
    setError("");
    // Revisión en un Web Worker (tipo real, tamaño, archivo repetido) antes de subir
    const check = await precheckUpload(file, "cotizacion");
    if (!check.ok) {
      setError(check.error);
      return;
    }

    setStage("processing");
    try {
      const result = await uploadQuotationFile(file, file.name);
      rememberUpload("cotizacion", check.hash, file.name);
      setQuotationResult(result);
      setStage("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar la cotización");
      setStage("upload");
    }
  };

  const startPurchase = (p: Purchase) => {
    setPurchaseError("");
    setPaymentTerms("contado");
    setPurchase(p);
  };

  const confirmPurchase = async () => {
    if (!purchase || !quotationResult) return;
    setPurchasing(true);
    setPurchaseError("");
    try {
      await createOrders(quotationResult.quotation_id, purchase.matchIds, paymentTerms);
      router.push("/ordenes");
    } catch (err) {
      setPurchaseError(err instanceof Error ? err.message : "No se pudo crear la orden");
      setPurchasing(false);
    }
  };

  if (isConstructora && (stage === "upload" || stage === "processing")) {
    return (
      <div className="page narrow-page">
        <section className="page-heading">
          <div><p className="eyebrow">NUEVA SOLICITUD</p><h1>¿Qué materiales necesitas?</h1><p>Sube una cotización, lista de materiales o foto. La IA organizará la solicitud para comparar proveedores.</p></div>
          {stage === "upload" && <Button variant="ghost" onClick={backToList}>Mis cotizaciones</Button>}
        </section>
        <div className="step-labels"><span className="current"><b>1</b> Subir solicitud</span><i /><span><b>2</b> Revisar materiales</span><i /><span><b>3</b> Comparar</span></div>
        {error && (
          <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "#fee", borderColor: "#fcc" }}>
            <p style={{ color: "#c00", margin: 0 }}>❌ Error: {error}</p>
          </section>
        )}
        {stage === "upload" ? (
          <section className="upload-card quotation-upload">
            <div className="upload-icon"><Icon name="file" size={28} /></div>
            <h2>Sube tu lista de materiales</h2>
            <p>No importa si viene de Excel, un PDF del proyecto o una foto tomada en obra. Podrás corregir todo antes de enviarla.</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.xlsx,.xls,.jpg,.jpeg,.png"
              onChange={handleFileSelect}
              style={{ display: "none" }}
            />
            <Button onClick={handleSelectFile}>Seleccionar archivo</Button>
            <div className="file-types"><span><Icon name="pdf" /> PDF</span><span><Icon name="excel" /> Excel</span><span><Icon name="camera" /> Foto</span></div>
            <small><Icon name="shield" size={15} /> Archivo privado · Máximo 25 MB</small>
          </section>
        ) : (
          <section className="processing-card">
            <div className="ai-loader"><span /><Icon name="spark" size={30} /></div>
            <h2>Estamos leyendo tu solicitud</h2>
            <p>Identificamos materiales, cantidades y unidades para buscar proveedores que puedan cumplir toda la orden.</p>
            <div className="processing-file">
              <Icon name={fileName.endsWith(".pdf") ? "pdf" : fileName.endsWith(".xlsx") || fileName.endsWith(".xls") ? "excel" : "camera"} />
              <div>
                <strong>{fileName || "archivo"}</strong>
                <span>Reconociendo cantidades y unidades…</span>
              </div>
              <Badge tone="info">72%</Badge>
            </div>
            <div className="progress quotation-progress"><span /></div>
            <small><Icon name="shield" size={15} /> Compararemos proveedores solo cuando confirmes los datos.</small>
          </section>
        )}
        <div className="tip"><Icon name="spark" /><div><strong>La IA se encarga del trabajo manual</strong><p>No necesitas copiar cada producto. Revisa el resultado y ajusta únicamente lo necesario.</p></div></div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Pantalla de resultados: ranking de proveedores y comparación por material
  if (isConstructora && stage === "results" && quotationResult) {
    const r = quotationResult;
    const combo = r.best_combination;
    const itemsWithOffers = r.items_total - r.items_without_offers;
    const restart = () => { setStage("upload"); setQuotationResult(null); };
    return (
      <div className="page">
        <section className="page-heading">
          <div>
            <p className="eyebrow">RESULTADOS / {r.title}</p>
            <h1>Comparación de proveedores</h1>
            <p>Leímos {r.items_total} materiales: {itemsWithOffers} tienen ofertas de {r.providers.length} proveedor(es){r.items_without_offers > 0 ? ` y ${r.items_without_offers} no los ofrece nadie todavía` : ""}.</p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button variant="ghost" onClick={backToList}>Mis cotizaciones</Button>
            <Button variant="secondary" icon="plus" onClick={restart}>Nueva cotización</Button>
          </div>
        </section>

        {r.ai_review.status === "ok" ? (
          <div className="review-summary">
            <div className="review-ai">
              <Icon name="spark" />
              <div>
                <strong>La IA revisó {r.ai_review.products_reviewed} productos del inventario de los proveedores</strong>
                <p>Confirma que cada oferta sea el mismo material, encuentra sinónimos (ej. &ldquo;acero de refuerzo&rdquo; = &ldquo;varilla corrugada&rdquo;) y descarta los que solo se parecen en el nombre.</p>
              </div>
            </div>
            <div className="review-count">
              <span><b>{r.ai_review.matches_added}</b> Por sinónimo</span>
              <span><b>{r.ai_review.matches_rejected}</b> Descartadas</span>
            </div>
          </div>
        ) : r.ai_review.status === "failed" ? (
          <div className="review-summary" style={{ background: "var(--warning-soft)" }}>
            <div className="review-ai">
              <Icon name="warning" />
              <div>
                <strong>La revisión con IA no estuvo disponible</strong>
                <p>Los proveedores se compararon solo por el nombre de los productos. Puedes intentarlo de nuevo más tarde.</p>
              </div>
            </div>
          </div>
        ) : null}

        {r.providers.length === 0 ? (
          <section className="card" style={{ padding: "3rem", textAlign: "center" }}>
            <h2 style={{ marginBottom: "0.5rem" }}>Ningún proveedor tiene estos materiales</h2>
            <p style={{ color: "var(--text-secondary)" }}>Cuando los proveedores suban inventario con estos materiales, aparecerán aquí.</p>
            <Button variant="secondary" onClick={restart}>Intentar otra cotización</Button>
          </section>
        ) : (
          <>
            <div className="match-layout">
              <div className="match-list">
                {r.providers.map((p, i) => (
                  <article key={p.provider_org_id} className={`match-card ${i === 0 ? "best-match" : ""}`}>
                    {i === 0 && <div className="best-label"><Icon name="spark" size={14} /> MEJOR OPCIÓN</div>}
                    <div className="match-main">
                      <div className="company-logo">{initials(p.provider_name)}</div>
                      <div>
                        <h2>{p.provider_name}</h2>
                        <p><Icon name="wallet" size={14} /> Costo estimado {formatCOP(p.total_cost)}</p>
                      </div>
                      <Score value={Math.round(p.score * 100)} />
                    </div>
                    <div className="criteria">
                      <Criterion label="Cobertura" value={`${p.items_covered} de ${r.items_total} materiales`} percent={Math.round(p.coverage * 100)} />
                      <Criterion label="Stock completo" value={`${p.items_full_stock} de ${p.items_covered}`} percent={p.items_covered ? Math.round((p.items_full_stock / p.items_covered) * 100) : 0} />
                      <Criterion label="Más económico en" value={`${p.cheapest_items} material(es)`} percent={itemsWithOffers ? Math.round((p.cheapest_items / itemsWithOffers) * 100) : 0} />
                      <Criterion label="Unidades" value={p.unit_mismatches ? `${p.unit_mismatches} por revisar` : "Coinciden"} percent={p.items_covered ? Math.round(((p.items_covered - p.unit_mismatches) / p.items_covered) * 100) : 0} />
                    </div>
                    <div className="match-bottom">
                      <div><span>Por qué</span><strong style={{ fontSize: 11, fontWeight: 600 }}>{p.justificacion}</strong></div>
                      <Button
                        variant={i === 0 ? "primary" : "secondary"}
                        onClick={() => startPurchase({
                          title: `Comprar a ${p.provider_name}`, matchIds: p.match_ids, total: p.total_cost,
                          providers: [p.provider_name], itemsCount: p.items_covered,
                        })}
                      >
                        {i === 0 ? "Elegir proveedor" : "Elegir este"}
                      </Button>
                    </div>
                  </article>
                ))}
              </div>

              <aside className="card quote-summary">
                <span>MEJOR COMBINACIÓN</span>
                <h2>Comprando cada material al mejor precio</h2>
                <div>
                  <strong>{formatCOP(combo.total_cost)}</strong>
                  <small>{combo.items_covered} material(es) con {combo.providers_count} proveedor(es)</small>
                </div>
                <ul>
                  {combo.items.map((c) => (
                    <li key={c.item_id}><span>{c.material_name}<br /><small>{c.provider_name}</small></span><b>{c.subtotal != null ? formatCOP(c.subtotal) : "—"}</b></li>
                  ))}
                </ul>
                {combo.savings_vs_recommendation != null && combo.savings_vs_recommendation > 0 && (
                  <p style={{ fontSize: 10, color: "var(--success)", margin: "12px 0 0" }}>
                    Ahorras {formatCOP(combo.savings_vs_recommendation)} frente a comprarle todo a {r.recommendation?.provider_name}.
                  </p>
                )}
                {combo.items.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <Button
                      wide
                      variant={combo.providers_count > 1 ? "secondary" : "primary"}
                      onClick={() => startPurchase({
                        title: "Comprar la mejor combinación", matchIds: combo.items.map((c) => c.match_id),
                        total: combo.total_cost, providers: [...new Set(combo.items.map((c) => c.provider_name))],
                        itemsCount: combo.items.length,
                      })}
                    >
                      Comprar combinación
                    </Button>
                  </div>
                )}
              </aside>
            </div>

            {/* key: al recalcular la comparación cambian las ofertas y se vuelve a predecir */}
            <ForecastPanel key={r.providers.flatMap((p) => p.match_ids).join(",")} quotationId={r.quotation_id} />

            <section className="card" style={{ marginTop: 18 }}>
              <div className="table-tools"><strong style={{ fontSize: 12 }}>Comparación por material</strong></div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Material pedido</th>
                      {r.providers.map((p) => <th key={p.provider_org_id}>{p.provider_name}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {r.items.map((item) => (
                      <tr key={item.item_id}>
                        <td>
                          <strong>{item.material_name}</strong><br />
                          <small style={{ color: "var(--muted)" }}>
                            {item.quantity} {item.unit}{item.budget_unit_price ? ` · presupuesto ${formatCOP(item.budget_unit_price)} c/u` : ""}
                          </small>
                        </td>
                        {r.providers.map((p) => {
                          const o = item.offers.find((x) => x.provider_org_id === p.provider_org_id);
                          if (!o) return <td key={p.provider_org_id} style={{ color: "var(--muted)" }}>No lo ofrece</td>;
                          return (
                            <td key={p.provider_org_id} style={o.is_cheapest ? { background: "var(--success-soft)" } : undefined}>
                              <strong>{o.unit_price != null ? `${formatCOP(o.unit_price)} / ${o.unit}` : "Sin precio"}</strong><br />
                              <small style={{ color: "var(--muted)" }}>
                                {o.material_name} · stock {o.quantity_available}
                                {o.subtotal != null ? ` · total ${formatCOP(o.subtotal)}` : ""}
                              </small>
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 5 }}>
                                {o.is_cheapest && <Badge tone="success">Más barato</Badge>}
                                {o.criteria.metodo === "ia" && <Badge tone="info"><Icon name="spark" size={11} /> Sinónimo (IA)</Badge>}
                                {o.criteria.metodo === "texto+ia" && <Badge tone="info"><Icon name="check" size={11} /> Verificado por IA</Badge>}
                                {/* === false: las comparaciones antiguas no traen estos campos */}
                                {o.criteria.stock_suficiente === false && <Badge tone="warning">Stock insuficiente</Badge>}
                                {o.criteria.unidad_compatible === false && <Badge tone="danger">Unidad distinta</Badge>}
                                {o.criteria.vs_presupuesto != null && o.criteria.vs_presupuesto > 0 && (
                                  <Badge tone="neutral">{Math.round(o.criteria.vs_presupuesto * 100)}% sobre presupuesto</Badge>
                                )}
                              </div>
                              {o.criteria.revision_ia?.motivo && (
                                <small style={{ display: "block", marginTop: 5, color: "var(--ink-soft)", fontStyle: "italic" }}>
                                  IA: {o.criteria.revision_ia.motivo}
                                </small>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {purchase && (
          <div className="modal-backdrop" onClick={() => !purchasing && setPurchase(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <span className="modal-icon"><Icon name="truck" size={26} /></span>
              <h2>{purchase.title}</h2>
              <p>
                Se {purchase.providers.length > 1 ? `crearán ${purchase.providers.length} órdenes, una por proveedor` : "creará una orden"}.
                {" "}Cada proveedor deberá confirmarla antes del envío.
              </p>
              <div className="modal-summary">
                <span>Materiales <strong>{purchase.itemsCount}</strong></span>
                <span>Proveedor(es) <strong>{purchase.providers.join(", ")}</strong></span>
                <span>Total estimado <strong>{formatCOP(purchase.total)}</strong></span>
              </div>
              <div style={{ marginTop: 16, textAlign: "left" }}>
                <small style={{ color: "var(--muted)" }}>Forma de pago</small>
                <div className="modal-actions" style={{ marginTop: 6 }}>
                  <Button variant={paymentTerms === "contado" ? "primary" : "secondary"} onClick={() => setPaymentTerms("contado")}>De contado</Button>
                  <Button variant={paymentTerms === "cuotas" ? "primary" : "secondary"} onClick={() => setPaymentTerms("cuotas")}>A cuotas</Button>
                </div>
              </div>
              {purchaseError && <p style={{ color: "var(--danger)", fontSize: 11, margin: "14px 0 0" }}>{purchaseError}</p>}
              <div className="modal-actions">
                <Button variant="secondary" onClick={() => setPurchase(null)} disabled={purchasing}>Cancelar</Button>
                <Button icon="check" onClick={confirmPurchase} disabled={purchasing}>{purchasing ? "Creando…" : "Crear orden"}</Button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Historial de cotizaciones
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">COTIZACIONES</p>
          <h1>Tus cotizaciones</h1>
          <p>Cada cotización guarda su comparación de proveedores. Ábrela para comprar o vuelve a comparar si los proveedores actualizaron su inventario.</p>
        </div>
        {isConstructora && <Button icon="plus" onClick={() => { setError(""); setStage("upload"); }}>Nueva cotización</Button>}
      </section>
      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "var(--danger-soft)", borderColor: "#f3c9c6" }}>
          <p style={{ color: "var(--danger)", margin: 0 }}>{error}</p>
        </section>
      )}
      {quotations === null ? null : quotations.length === 0 ? (
        <section className="card" style={{ padding: "3rem", textAlign: "center" }}>
          <div style={{ opacity: 0.5, marginBottom: "1rem" }}><Icon name="file" size={48} /></div>
          <h2 style={{ marginBottom: "0.5rem" }}>Sin cotizaciones</h2>
          <p style={{ color: "var(--text-secondary)" }}>Sube tu primera lista de materiales para comparar proveedores.</p>
          <Button icon="upload" onClick={() => setStage("upload")}>Subir cotización</Button>
        </section>
      ) : (
        <section className="card">
          <div className="table-scroll">
            <table>
              <thead><tr><th>Cotización</th><th>Fecha</th><th>Materiales</th><th>Estado</th><th /></tr></thead>
              <tbody>
                {quotations.map((q) => (
                  <tr key={q.id}>
                    <td><strong>{q.title}</strong></td>
                    <td>{formatDate(q.created_at)}</td>
                    <td>{q.items_count}</td>
                    <td>
                      <Badge tone={QUOTATION_STATUS[q.status].tone}>{QUOTATION_STATUS[q.status].label}</Badge>
                      {q.active_orders > 0 && <small style={{ display: "block", marginTop: 4, color: "var(--muted)" }}>{q.active_orders} orden(es) activa(s)</small>}
                    </td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <div style={{ display: "inline-flex", gap: 6 }}>
                        <Button variant="ghost" onClick={() => openComparison(q.id, true)} disabled={loadingId !== null || q.items_count === 0}>
                          {loadingId === q.id && rerunning ? "Comparando…" : "Volver a comparar"}
                        </Button>
                        <Button variant="secondary" onClick={() => openComparison(q.id, false)} disabled={loadingId !== null || q.items_count === 0}>
                          {loadingId === q.id && !rerunning ? "Abriendo…" : "Ver comparación"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
