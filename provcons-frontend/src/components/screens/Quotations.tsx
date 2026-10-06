"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Criterion } from "@/components/ui/Criterion";
import { Icon } from "@/components/ui/Icon";
import { Score } from "@/components/ui/Score";

type Stage = "upload" | "processing" | "review" | "results";

const matchData = [
  { name: "Aceros Colombia", score: 96, price: "$ 47.200.000", delivery: "2 días", payment: "30 días", risk: "Bajo", tone: "success" as const },
  { name: "Suministros Andinos", score: 88, price: "$ 49.100.000", delivery: "1 día", payment: "Contado", risk: "Bajo", tone: "success" as const },
  { name: "Ferretería Industrial", score: 79, price: "$ 45.900.000", delivery: "5 días", payment: "15 días", risk: "Medio", tone: "warning" as const },
];

export function Quotations() {
  const { role } = useRole();
  const router = useRouter();
  const [stage, setStage] = useState<Stage>(role === "constructora" ? "upload" : "results");
  const timer = useRef<number | null>(null);

  const processQuotation = () => {
    setStage("processing");
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setStage("review"), 1800);
  };
  const goOrders = () => router.push("/ordenes");

  if (role === "constructora" && (stage === "upload" || stage === "processing")) {
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
            <Button onClick={processQuotation}>Seleccionar archivo</Button>
            <div className="file-types"><span><Icon name="pdf" /> PDF</span><span><Icon name="excel" /> Excel</span><span><Icon name="camera" /> Foto</span></div>
            <small><Icon name="shield" size={15} /> Archivo privado · Máximo 25 MB</small>
          </section>
        ) : (
          <section className="processing-card">
            <div className="ai-loader"><span /><Icon name="spark" size={30} /></div>
            <h2>Estamos leyendo tu solicitud</h2>
            <p>Identificamos materiales, cantidades y unidades para buscar proveedores que puedan cumplir toda la orden.</p>
            <div className="processing-file"><Icon name="pdf" /><div><strong>Lista_materiales_Torre_Alameda.pdf</strong><span>Reconociendo cantidades y unidades…</span></div><Badge tone="info">72%</Badge></div>
            <div className="progress quotation-progress"><span /></div>
            <small><Icon name="shield" size={15} /> Compararemos proveedores solo cuando confirmes los datos.</small>
          </section>
        )}
        <div className="tip"><Icon name="spark" /><div><strong>La IA se encarga del trabajo manual</strong><p>No necesitas copiar cada producto. Revisa el resultado y ajusta únicamente lo necesario.</p></div></div>
      </div>
    );
  }

  if (role === "constructora" && stage === "review") {
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

  const constructora = role === "constructora";
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">COTIZACIONES / COT-0248</p>
          <h1>{constructora ? "Proveedores recomendados" : "Oportunidad compatible"}</h1>
          <p>{constructora ? "Comparamos precio, disponibilidad, logística y condiciones para ayudarte a decidir." : "Tu inventario cumple con los materiales principales de esta solicitud."}</p>
        </div>
        {constructora ? <Button variant="secondary" icon="plus" onClick={() => setStage("upload")}>Nueva solicitud</Button> : <Button variant="secondary" icon="file">Ver solicitud</Button>}
      </section>
      <div className="trust-banner">
        <span><Icon name="spark" /></span>
        <div><strong>Recomendación explicable</strong><p>El puntaje combina cuatro criterios. Ningún proveedor paga para aparecer primero.</p></div>
        <button>¿Cómo calculamos esto?</button>
      </div>
      <div className="match-layout">
        <div className="match-list">
          {matchData.map((m, i) => (
            <article className={`match-card ${i === 0 ? "best-match" : ""}`} key={m.name}>
              {i === 0 && <div className="best-label"><Icon name="spark" size={14} /> MEJOR OPCIÓN</div>}
              <div className="match-main">
                <div className="company-logo">{m.name.split(" ").map((x) => x[0]).join("").slice(0, 2)}</div>
                <div><h2>{m.name}</h2><p><Icon name="shield" size={14} /> Empresa verificada · 4,8 en entregas</p></div>
                <Score value={m.score} />
              </div>
              <div className="criteria">
                <Criterion label="Disponibilidad" value={i === 2 ? "92% de la solicitud" : "100% disponible"} percent={i === 2 ? 92 : 100} />
                <Criterion label="Precio" value={i === 2 ? "7% bajo promedio" : i === 0 ? "4% bajo promedio" : "En el promedio"} percent={i === 2 ? 98 : i === 0 ? 91 : 78} />
                <Criterion label="Logística" value={`Entrega en ${m.delivery}`} percent={i === 1 ? 98 : i === 0 ? 90 : 60} />
                <Criterion label="Historial" value="Cumplimiento alto" percent={i === 0 ? 96 : 88} />
              </div>
              <div className="match-bottom">
                <div><span>Total estimado</span><strong>{m.price}</strong></div>
                <div className="match-tags">
                  <Badge tone="info"><Icon name="wallet" size={13} /> {m.payment}</Badge>
                  <Badge tone={m.tone}><Icon name="shield" size={13} /> Riesgo {m.risk.toLowerCase()}</Badge>
                </div>
                <Button variant={i === 0 ? "primary" : "secondary"} onClick={goOrders}>
                  {constructora ? (i === 0 ? "Elegir mejor proveedor" : "Elegir proveedor") : "Enviar propuesta"}
                </Button>
              </div>
            </article>
          ))}
        </div>
        <aside className="quote-summary card">
          <p className="eyebrow">SOLICITUD</p>
          <h2>Acero para Torre Alameda</h2>
          <span>COT-0248 · Cierra en 3 días</span>
          <div><strong>3</strong><small>productos</small></div>
          <ul>
            <li><span>Varilla corrugada ½&quot;</span><b>800 und</b></li>
            <li><span>Malla electrosoldada</span><b>120 und</b></li>
            <li><span>Alambre negro</span><b>60 kg</b></li>
          </ul>
          <div className="location"><Icon name="route" /><span><small>ENTREGA EN</small><strong>Chapinero, Bogotá</strong></span></div>
        </aside>
      </div>
    </div>
  );
}
