"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Criterion } from "@/components/ui/Criterion";
import { Icon } from "@/components/ui/Icon";
import { Score } from "@/components/ui/Score";
import { getMe, uploadQuotationFile } from "@/lib/api";
import type { User, QuotationResult } from "@/lib/api";

type Stage = "upload" | "processing" | "review" | "results";

export function Quotations() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stage, setStage] = useState<Stage>("upload");
  const [fileName, setFileName] = useState<string>("");
  const [quotationResult, setQuotationResult] = useState<QuotationResult | null>(null);
  const [error, setError] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    getMe()
      .then((userData) => {
        setUser(userData);
        if (userData.organization?.type !== "constructora") {
          router.push("/dashboard");
        }
      })
      .catch(() => {
        router.push("/login");
      });
  }, [router]);

  const isConstructora = user?.organization?.type === "constructora";

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
      await processQuotationFile(file);
    }
  };

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const processQuotationFile = async (file: File) => {
    setStage("processing");
    setError("");

    try {
      const result = await uploadQuotationFile(file, file.name);
      setQuotationResult(result);

      // Simular tiempo de procesamiento
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setStage("results"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar la cotización");
      setStage("upload");
    }
  };

  const goOrders = () => router.push("/ordenes");

  if (isConstructora && (stage === "upload" || stage === "processing")) {
    return (
      <div className="page narrow-page">
        <section className="page-heading">
          <div><p className="eyebrow">NUEVA SOLICITUD</p><h1>¿Qué materiales necesitas?</h1><p>Sube una cotización, lista de materiales o foto. La IA organizará la solicitud para comparar proveedores.</p></div>
        </section>
        <div className="step-labels"><span className="current"><b>1</b> Subir solicitud</span><i /><span><b>2</b> Revisar materiales</span><i /><span><b>3</b> Comparar</span></div>
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

  if (isConstructora && stage === "review") {
    const rows = [
      { name: 'Varilla corrugada ½"', qty: "800", unit: "Unidades", conf: 98, tone: "success" as const },
      { name: "Malla electrosoldada", qty: "120", unit: "Unidades", conf: 96, tone: "success" as const },
      { name: "Alambre negro", qty: "60", unit: "Kilogramos", conf: 84, tone: "warning" as const },
    ];
    return (
      <div className="page narrow-page">
        <section className="page-heading">
          <div><p className="eyebrow">NUEVA SOLICITUD / REVISIÓN</p><h1>Confirma los materiales</h1><p>Encontramos 3 productos en tu archivo. Revisa que las cantidades sean correctas.</p></div>
          <Badge tone="success"><Icon name="check" size={12} /> Lectura completada</Badge>
        </section>
        <div className="step-labels"><span><b><Icon name="check" size={13} /></b> Archivo listo</span><i /><span className="current"><b>2</b> Revisar materiales</span><i /><span><b>3</b> Comparar</span></div>
        <section className="card request-review">
          <div className="request-meta">
            <label>Nombre de la solicitud<input defaultValue="Acero para Torre Alameda" /></label>
            <label>Lugar de entrega<input defaultValue="Chapinero, Bogotá" /></label>
            <label>Fecha requerida<input type="date" defaultValue="2025-05-19" /></label>
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Material detectado</th><th>Cantidad</th><th>Unidad</th><th>Confianza IA</th><th /></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.name}>
                    <td><input defaultValue={r.name} /></td>
                    <td><input className="small-input" defaultValue={r.qty} /></td>
                    <td><button className="unit-select">{r.unit} <Icon name="chevron" size={13} /></button></td>
                    <td><Badge tone={r.tone}><Icon name={r.tone === "success" ? "check" : "warning"} size={12} /> {r.conf}%</Badge></td>
                    <td><button className="remove-row" aria-label="Eliminar material"><Icon name="close" size={15} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="add-material"><Icon name="plus" size={16} /> Agregar otro material</button>
          <div className="card-actions">
            <Button variant="ghost" onClick={() => setStage("upload")}>Cambiar archivo</Button>
            <Button icon="spark" onClick={() => setStage("results")}>Buscar mejores proveedores</Button>
          </div>
        </section>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Pantalla de resultados con proveedores recomendados
  if (isConstructora && stage === "results" && quotationResult) {
    return (
      <div className="page">
        <section className="page-heading">
          <div>
            <p className="eyebrow">RESULTADOS / {quotationResult.title}</p>
            <h1>Proveedores recomendados</h1>
            <p>La IA analizó {quotationResult.items_extracted} materiales y encontró {quotationResult.matches_found} coincidencias. Aquí están los mejores proveedores.</p>
          </div>
          <Button variant="secondary" icon="plus" onClick={() => {
            setStage("upload");
            setQuotationResult(null);
          }}>Nueva cotización</Button>
        </section>

        <div className="match-layout">
          <div className="match-list">
            {quotationResult.top_providers && quotationResult.top_providers.length > 0 ? (
              quotationResult.top_providers.map((provider, i) => (
                <article key={provider.id} className={`match-card ${i === 0 ? "best-match" : ""}`}>
                  {i === 0 && <div className="best-label"><Icon name="spark" size={14} /> MEJOR OPCIÓN SEGÚN IA</div>}
                  <div className="match-main">
                    <div className="company-logo">PR</div>
                    <div>
                      <h2>Proveedor {provider.provider_org_id}</h2>
                      <p><Icon name="shield" size={14} /> Verificado · IA Score: {Math.round(provider.score * 100)}%</p>
                    </div>
                    <Score value={Math.round(provider.score * 100)} />
                  </div>
                  <div className="criteria">
                    <Criterion
                      label="Disponibilidad"
                      value={`${Math.round((provider.criteria_breakdown?.disponibilidad || 0.5) * 100)}% del material`}
                      percent={Math.round((provider.criteria_breakdown?.disponibilidad || 0.5) * 100)}
                    />
                    <Criterion
                      label="Precio"
                      value={`${Math.round((provider.criteria_breakdown?.precio || 0.5) * 100)}% competitivo`}
                      percent={Math.round((provider.criteria_breakdown?.precio || 0.5) * 100)}
                    />
                    <Criterion
                      label="Logística"
                      value={`${Math.round((provider.criteria_breakdown?.logistica || 0.5) * 100)}% de velocidad`}
                      percent={Math.round((provider.criteria_breakdown?.logistica || 0.5) * 100)}
                    />
                    <Criterion
                      label="Confiabilidad"
                      value={`${Math.round((provider.criteria_breakdown?.confiabilidad || 0.5) * 100)}% historial`}
                      percent={Math.round((provider.criteria_breakdown?.confiabilidad || 0.5) * 100)}
                    />
                  </div>
                  <div className="match-bottom">
                    <div><span>Análisis IA</span><strong>{provider.criteria_breakdown?.justificacion || "Análisis completado"}</strong></div>
                    <Button variant={i === 0 ? "primary" : "secondary"} onClick={goOrders}>
                      {i === 0 ? "Elegir mejor proveedor" : "Considerar"}
                    </Button>
                  </div>
                </article>
              ))
            ) : (
              <div style={{ padding: "2rem", textAlign: "center" }}>
                <p style={{ color: "var(--text-secondary)" }}>No se encontraron proveedores coincidentes</p>
                <Button variant="secondary" onClick={() => {
                  setStage("upload");
                  setQuotationResult(null);
                }}>Intentar otra cotización</Button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Pantalla vacía o de cotizaciones
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">COTIZACIONES</p>
          <h1>Cotizaciones</h1>
          <p>Aquí aparecerán tus cotizaciones y oportunidades de proveedores.</p>
        </div>
        {isConstructora && <Button variant="secondary" icon="plus" onClick={() => setStage("upload")}>Subir cotización</Button>}
      </section>
      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "#fee", borderColor: "#fcc" }}>
          <p style={{ color: "#c00", margin: 0 }}>❌ Error: {error}</p>
        </section>
      )}
      <section className="card" style={{ padding: "3rem", textAlign: "center" }}>
        <div style={{ opacity: 0.5, marginBottom: "1rem" }}>
          <Icon name="file" size={48} />
        </div>
        <h2 style={{ marginBottom: "0.5rem" }}>Sin cotizaciones</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          No tienes cotizaciones aún. {isConstructora ? "Crea una solicitud de materiales para comenzar a comparar proveedores." : "Las solicitudes de cotizaciones aparecerán aquí."}
        </p>
      </section>
    </div>
  );
}
