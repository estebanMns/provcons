"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { getMe } from "@/lib/api";
import type { User } from "@/lib/api";

type Stage = "idle" | "processing" | "review" | "done";

export function Inventory() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [items, setItems] = useState<any[]>([]);
  const [fileName, setFileName] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    getMe()
      .then((userData) => {
        setUser(userData);
        if (userData.organization?.type !== "proveedor") {
          router.push("/dashboard");
        }
      })
      .catch(() => {
        router.push("/login");
      });
  }, [router]);

  if (!user) {
    return null;
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
      process();
    }
  };

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const process = () => {
    setStage("processing");
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setStage("review"), 1800);
  };

  if (stage === "idle" || stage === "processing") {
    return (
      <div className="page narrow-page">
        <section className="page-heading">
          <div><p className="eyebrow">INVENTARIO</p><h1>Actualiza tu catálogo</h1><p>Sube tu lista y la organizaremos por ti. Podrás revisarla antes de publicar.</p></div>
        </section>
        <div className="step-labels"><span className="current"><b>1</b> Subir archivo</span><i /><span><b>2</b> Revisar datos</span><i /><span><b>3</b> Publicar</span></div>
        {stage === "idle" ? (
          <section className="upload-card">
            <div className="upload-icon"><Icon name="upload" size={28} /></div>
            <h2>Arrastra aquí tu catálogo</h2>
            <p>También puedes seleccionar un archivo desde tu dispositivo.</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.xlsx,.xls,.jpg,.jpeg,.png"
              onChange={handleFileSelect}
              style={{ display: "none" }}
            />
            <Button onClick={handleSelectFile}>Seleccionar archivo</Button>
            <div className="file-types"><span><Icon name="pdf" /> PDF</span><span><Icon name="excel" /> Excel</span><span><Icon name="camera" /> Foto</span></div>
            <small>Máximo 25 MB · Tus archivos están protegidos</small>
          </section>
        ) : (
          <section className="processing-card">
            <div className="ai-loader"><span /><Icon name="spark" size={30} /></div>
            <h2>Estamos organizando tu catálogo</h2>
            <p>Nuestra IA está leyendo productos, cantidades y precios. Suele tomar menos de un minuto; puedes dejar esta pantalla abierta.</p>
            <div className="processing-file">
              <Icon name={fileName.endsWith(".pdf") ? "pdf" : fileName.endsWith(".xlsx") || fileName.endsWith(".xls") ? "excel" : "camera"} />
              <div>
                <strong>{fileName || "archivo"}</strong>
                <span>Analizando datos…</span>
              </div>
              <Badge tone="info">67%</Badge>
            </div>
            <div className="progress"><span /></div>
            <small><Icon name="shield" size={15} /> No publicaremos nada sin tu aprobación.</small>
          </section>
        )}
        <div className="tip"><Icon name="spark" /><div><strong>Consejo</strong><p>Para obtener mejores resultados, asegúrate de que los nombres y precios sean legibles.</p></div></div>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">INVENTARIO / REVISIÓN</p>
          <h1>{stage === "review" ? "Revisa lo que encontramos" : "Inventario actualizado"}</h1>
          <p>{stage === "review" ? "Confirma o corrige los datos antes de incorporarlos a tu inventario." : "Tu catálogo está listo para encontrar nuevas oportunidades."}</p>
        </div>
        {stage === "done" && <Button icon="upload" onClick={() => setStage("idle")}>Subir otro archivo</Button>}
      </section>
      {stage === "review" && (
        <div className="review-summary">
          <div className="review-ai"><Icon name="spark" /><div><strong>La IA encontró 48 productos</strong><p>44 tienen alta confianza y 4 necesitan una revisión rápida.</p></div></div>
          <div className="review-count"><span><b>44</b> Listos</span><span><b>4</b> Por revisar</span></div>
        </div>
      )}
      <section className="card inventory-card">
        <div className="table-tools">
          <div className="search-field"><Icon name="search" size={18} /><input placeholder="Buscar producto o código" /></div>
          <div><button>Todos <b>{stage === "review" ? "48" : "248"}</b></button><button>Por revisar <b>4</b></button></div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Producto</th><th>Código</th><th>Disponible</th><th>Unidad</th><th>Precio unitario</th><th>Lectura IA</th></tr></thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.sku}>
                  <td><input value={item.name} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} /></td>
                  <td>{item.sku}</td>
                  <td><input className="small-input" value={item.qty} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, qty: Number(e.target.value) || 0 } : x)))} /></td>
                  <td>{item.unit}</td>
                  <td>$ {item.price}</td>
                  <td><Badge tone={item.confidence > 90 ? "success" : "warning"}>{item.confidence > 90 ? <Icon name="check" size={12} /> : <Icon name="warning" size={12} />} {item.confidence}%</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {stage === "review" ? (
          <div className="card-actions">
            <Button variant="ghost">Guardar borrador</Button>
            <div><Button variant="secondary" onClick={() => setStage("idle")}>Volver</Button><Button icon="check" onClick={() => setStage("done")}>Confirmar 48 productos</Button></div>
          </div>
        ) : (
          <div className="success-footer">
            <div><Icon name="check" /><span><strong>Catálogo publicado correctamente</strong><small>Última actualización: hoy, 10:42 a. m.</small></span></div>
            <Button icon="arrow" onClick={() => router.push("/cotizaciones")}>Ver oportunidades</Button>
          </div>
        )}
      </section>
    </div>
  );
}
