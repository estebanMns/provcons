// Revisión previa a cada subida (en un Web Worker) y recuerdo de los archivos
// ya subidos por su huella SHA-256, para avisar si se repite uno.
import { checkFileInWorker } from "@/lib/workers";

export type UploadKind = "inventario" | "cotizacion";

const MAX_BYTES = 25 * 1024 * 1024;
const STORAGE_KEY = "provcons_uploaded_files";

type UploadedMap = Record<string, { name: string; at: string }>;

// localStorage puede no estar disponible (modo privado, bloqueado): nunca rompe la subida
function readUploaded(): UploadedMap {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

export type PrecheckResult = { ok: true; hash: string } | { ok: false; error: string };

export async function precheckUpload(file: File, kind: UploadKind): Promise<PrecheckResult> {
  const result = await checkFileInWorker({ file, maxBytes: MAX_BYTES });
  if (!result.ok) return result;

  const previous = readUploaded()[`${kind}:${result.hash}`];
  if (previous) {
    const when = new Date(previous.at).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const again = window.confirm(`Ya subiste este mismo archivo («${previous.name}») el ${when}. ¿Quieres subirlo de nuevo?`);
    if (!again) return { ok: false, error: "Subida cancelada: el archivo ya se había subido." };
  }
  return { ok: true, hash: result.hash };
}

export function rememberUpload(kind: UploadKind, hash: string, name: string): void {
  try {
    const uploaded = readUploaded();
    uploaded[`${kind}:${hash}`] = { name, at: new Date().toISOString() };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(uploaded));
  } catch {
    // sin almacenamiento disponible: simplemente no se recuerda
  }
}
