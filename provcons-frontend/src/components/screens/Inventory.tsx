"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { getMe, uploadInventoryFile } from "@/lib/api";
import type { User, InventoryUploadResult } from "@/lib/api";

type Stage = "idle" | "processing" | "review" | "done";

export function Inventory() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [items, setItems] = useState<any[]>([]);
  const [fileName, setFileName] = useState<string>("");
  const [uploadResult, setUploadResult] = useState<InventoryUploadResult | null>(null);
  const [error, setError] = useState<string>("");
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

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && user.organization) {
      setFileName(file.name);
      await processInventoryFile(file);
    }
  };

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const processInventoryFile = async (file: File) => {
    setStage("processing");
    setError("");

    try {
      const result = await uploadInventoryFile(file, user.organization!.id);
      setUploadResult(result);
      setItems(result.saved_items || []);

      // Simular tiempo de procesamiento
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setStage("done"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar el inventario");
      setStage("idle");
    }
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
          <p className="eyebrow">INVENTARIO</p>
          <h1>{stage === "done" ? "Inventario actualizado" : "Mi catálogo"}</h1>
          <p>{stage === "done" ? "Tu catálogo está listo para encontrar nuevas oportunidades." : "Sube tus productos para que los clientes puedan encontrarte."}</p>
        </div>
        {stage === "done" && <Button icon="upload" onClick={() => setStage("idle")}>Subir otro archivo</Button>}
      </section>
      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "#fee", borderColor: "#fcc" }}>
          <p style={{ color: "#c00", margin: 0 }}>❌ Error: {error}</p>
        </section>
      )}
      {stage === "done" && uploadResult && (
        <div className="review-summary">
          <div className="review-ai"><Icon name="spark" /><div><strong>La IA encontró {uploadResult.items_extracted} productos</strong><p>Se guardaron {uploadResult.items_saved} productos en tu inventario.</p></div></div>
          <div className="review-count"><span><b>{uploadResult.items_saved}</b> Guardados</span><span><b>{uploadResult.items_extracted}</b> Totales</span></div>
        </div>
      )}
      {stage !== "idle" && stage !== "processing" && (
        <section className="card inventory-card">
          <div className="table-tools">
            <div className="search-field"><Icon name="search" size={18} /><input placeholder="Buscar producto" /></div>
            <div><button>Todos <b>{items.length}</b></button></div>
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Producto</th><th>Disponible</th><th>Unidad</th><th>Precio unitario</th></tr></thead>
              <tbody>
                {items.length > 0 ? (
                  items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.material_name}</td>
                      <td>{item.quantity_available}</td>
                      <td>{item.unit}</td>
                      <td>$ {item.unit_price || "N/A"}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: "center", padding: "2rem", color: "var(--text-secondary)" }}>
                      No hay productos en el inventario
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {stage === "done" && (
            <div className="success-footer">
              <div><Icon name="check" /><span><strong>Catálogo publicado correctamente</strong><small>Última actualización: hace unos momentos</small></span></div>
              <Button icon="arrow" onClick={() => router.push("/dashboard")}>Volver al dashboard</Button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
