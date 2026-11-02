"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { deleteInventoryItem, getInventory, getMe, updateInventoryItem, uploadInventoryFile } from "@/lib/api";
import { precheckUpload, rememberUpload } from "@/lib/uploadCheck";
import { formatCOP } from "@/lib/format";
import type { User, InventoryItem, InventoryUploadResult } from "@/lib/api";

type Stage = "idle" | "processing" | "review" | "done";

export function Inventory() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [fileName, setFileName] = useState<string>("");
  const [uploadResult, setUploadResult] = useState<InventoryUploadResult | null>(null);
  const [error, setError] = useState<string>("");
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const [toDelete, setToDelete] = useState<InventoryItem | null>(null);
  const [search, setSearch] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Si el efecto se descarta (desmontaje o doble ejecución en modo estricto),
    // sus respuestas tardías se ignoran: no deben pisar lo que el usuario ya hizo
    let cancelled = false;
    getMe()
      .then((userData) => {
        if (cancelled) return;
        setUser(userData);
        if (userData.organization?.type !== "proveedor") {
          router.push("/dashboard");
          return;
        }
        getInventory(userData.organization.id).then((saved) => {
          if (!cancelled && saved.length > 0) {
            setItems(saved);
            setStage("review");
          }
        });
      })
      .catch(() => {
        if (!cancelled) router.push("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!user) {
    return null;
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // permite volver a elegir el mismo archivo tras un error
    if (file && user.organization) {
      setFileName(file.name);
      await processInventoryFile(file);
    }
  };

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const processInventoryFile = async (file: File) => {
    setError("");
    // Revisión en un Web Worker (tipo real, tamaño, archivo repetido) antes de subir
    const check = await precheckUpload(file, "inventario");
    if (!check.ok) {
      setError(check.error);
      return;
    }

    setStage("processing");
    try {
      const result = await uploadInventoryFile(file, user.organization!.id);
      rememberUpload("inventario", check.hash, file.name);
      setUploadResult(result);
      setItems(await getInventory(user.organization!.id));
      setStage("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar el inventario");
      setStage("idle");
    }
  };

  if (stage === "idle" || stage === "processing") {
    return (
      <div className="page narrow-page">
        <section className="page-heading">
          <div><p className="eyebrow">INVENTARIO</p><h1>Actualiza tu catálogo</h1><p>Sube tu lista y la organizaremos por ti. Podrás revisarla antes de publicar.</p></div>
        </section>
        <div className="step-labels"><span className="current"><b>1</b> Subir archivo</span><i /><span><b>2</b> Revisar datos</span><i /><span><b>3</b> Publicar</span></div>
        {error && (
          <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "#fee", borderColor: "#fcc" }}>
            <p style={{ color: "#c00", margin: 0 }}>❌ Error: {error}</p>
          </section>
        )}
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

  const term = search.trim().toLowerCase();
  const visible = term ? items.filter((i) => `${i.sku} ${i.material_name}`.toLowerCase().includes(term)) : items;

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">INVENTARIO</p>
          <h1>{stage === "done" ? "Inventario actualizado" : "Mi catálogo"}</h1>
          <p>{stage === "done" ? "Tu catálogo está listo para encontrar nuevas oportunidades." : "Sube tus productos para que los clientes puedan encontrarte."}</p>
        </div>
        <Button icon="upload" onClick={() => setStage("idle")}>Subir otro archivo</Button>
      </section>
      {error && (
        <section className="card" style={{ padding: "1rem", marginBottom: "1rem", background: "#fee", borderColor: "#fcc" }}>
          <p style={{ color: "#c00", margin: 0 }}>❌ Error: {error}</p>
        </section>
      )}
      {stage === "done" && uploadResult && (
        <div className="review-summary">
          <div className="review-ai"><Icon name="spark" /><div><strong>La IA encontró {uploadResult.items_extracted} productos</strong><p>Los productos con un código que ya tenías sumaron su cantidad al stock; los demás se agregaron como nuevos.{uploadResult.skipped ? ` ${uploadResult.skipped} fila(s) se omitieron por datos incompletos.` : ""}</p></div></div>
          <div className="review-count"><span><b>{uploadResult.created}</b> Nuevos</span><span><b>{uploadResult.updated}</b> Sumados al stock</span></div>
        </div>
      )}
      <section className="card inventory-card">
        <div className="table-tools">
          <div className="search-field"><Icon name="search" size={18} /><input placeholder="Buscar por código o producto" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
          <div><button>Todos <b>{items.length}</b></button></div>
        </div>
        <p className="inventory-note"><Icon name="spark" size={14} /> El stock baja solo cuando aceptas una orden, y vuelve si la orden se cancela.</p>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Código</th><th>Producto</th><th>Disponible</th><th>Unidad</th><th>Precio unitario</th><th aria-label="Acciones" /></tr></thead>
            <tbody>
              {visible.length > 0 ? (
                visible.map((item) => (
                  <tr key={item.id}>
                    <td><code className="sku">{item.sku}</code></td>
                    <td>{item.material_name}</td>
                    <td>{item.quantity_available}</td>
                    <td>{item.unit}</td>
                    <td>{item.unit_price != null && item.unit_price !== "" ? formatCOP(Number(item.unit_price)) : "—"}</td>
                    <td className="row-actions">
                      <button onClick={() => setEditing(item)} aria-label={`Editar ${item.material_name}`}>Editar</button>
                      <button className="danger" onClick={() => setToDelete(item)} aria-label={`Eliminar ${item.material_name}`}>Eliminar</button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "var(--text-secondary)" }}>
                    {items.length ? "Ningún producto coincide con la búsqueda" : "No hay productos en el inventario"}
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
      {editing && (
        <EditItemModal
          item={editing}
          onClose={() => setEditing(null)}
          onSave={async (changes) => {
            const updated = await updateInventoryItem(user.organization!.id, editing.id, changes);
            setItems((list) => list.map((i) => (i.id === updated.id ? updated : i)));
            setEditing(null);
          }}
        />
      )}

      {toDelete && (
        <div className="modal-backdrop" onClick={() => setToDelete(null)}>
          <div className="modal" role="dialog" aria-labelledby="del-title" onClick={(e) => e.stopPropagation()}>
            <span className="modal-icon" style={{ color: "var(--danger)", background: "var(--danger-soft)" }}><Icon name="warning" size={26} /></span>
            <h2 id="del-title">¿Eliminar este producto?</h2>
            <p><strong>{toDelete.sku}</strong> · {toDelete.material_name}. Dejará de aparecer en tu inventario y en las comparaciones de las constructoras. Las órdenes anteriores no cambian. Si vuelves a subirlo con el mismo código, reaparece.</p>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setToDelete(null)}>Volver</Button>
              <Button variant="danger" onClick={async () => {
                try {
                  await deleteInventoryItem(user.organization!.id, toDelete.id);
                  setItems((list) => list.filter((i) => i.id !== toDelete.id));
                } catch (err) {
                  setError(err instanceof Error ? err.message : "No se pudo eliminar el producto");
                } finally {
                  setToDelete(null);
                }
              }}>Sí, eliminar</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Corregir código, nombre, unidad, cantidad o precio de un producto
function EditItemModal({ item, onClose, onSave }: {
  item: InventoryItem; onClose: () => void;
  onSave: (changes: { sku: string; material_name: string; unit: string; quantity_available: number; unit_price: number }) => Promise<void>;
}) {
  const [form, setForm] = useState({
    sku: item.sku, material_name: item.material_name, unit: item.unit,
    quantity_available: String(item.quantity_available), unit_price: String(item.unit_price ?? ""),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const save = async () => {
    const quantity = Number(form.quantity_available.replace(",", "."));
    const price = Number(form.unit_price.replace(",", "."));
    if (!form.sku.trim()) return setError("El código no puede quedar vacío.");
    if (form.material_name.trim().length < 2) return setError("Escribe el nombre del producto.");
    if (!form.unit.trim()) return setError("Escribe la unidad.");
    if (!Number.isFinite(quantity) || quantity < 0) return setError("La cantidad debe ser un número igual o mayor a 0.");
    if (!Number.isFinite(price) || price <= 0) return setError("El precio debe ser mayor a 0.");
    setSaving(true);
    setError("");
    try {
      await onSave({ sku: form.sku.trim(), material_name: form.material_name.trim(), unit: form.unit.trim(), quantity_available: quantity, unit_price: price });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar");
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={() => !saving && onClose()}>
      <div className="modal inventory-edit" role="dialog" aria-labelledby="edit-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="edit-title">Editar producto</h2>
        <div className="inventory-edit-grid">
          <label>Código<input value={form.sku} onChange={set("sku")} maxLength={60} disabled={saving} /></label>
          <label>Unidad<input value={form.unit} onChange={set("unit")} maxLength={20} disabled={saving} /></label>
          <label className="wide">Producto<input value={form.material_name} onChange={set("material_name")} maxLength={200} disabled={saving} /></label>
          <label>Disponible<input inputMode="decimal" value={form.quantity_available} onChange={set("quantity_available")} disabled={saving} /></label>
          <label>Precio unitario<input inputMode="decimal" value={form.unit_price} onChange={set("unit_price")} disabled={saving} /></label>
        </div>
        {error && <p className="inventory-edit-error" role="alert">{error}</p>}
        <div className="modal-actions">
          <Button variant="secondary" onClick={onClose} disabled={saving}>Cancelar</Button>
          <Button icon="check" onClick={save} disabled={saving}>{saving ? "Guardando…" : "Guardar cambios"}</Button>
        </div>
      </div>
    </div>
  );
}
