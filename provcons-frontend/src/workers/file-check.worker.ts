// Web Worker: revisa un archivo antes de subirlo, sin bloquear la pantalla.
// - Tipo real por su firma de bytes ("magic numbers"), no por la extensión:
//   un .pdf que en realidad es texto se rechaza antes de gastar una llamada a la IA
// - Tamaño máximo
// - Huella SHA-256 para detectar si el mismo archivo ya se subió

export interface FileCheckRequest {
  file: File;
  maxBytes: number;
}

export type FileKind = "pdf" | "png" | "jpg" | "xlsx";

export type FileCheckResponse =
  | { ok: true; kind: FileKind; hash: string; size: number; millis: number }
  | { ok: false; error: string };

const SIGNATURES: { kind: FileKind; bytes: number[] }[] = [
  { kind: "pdf", bytes: [0x25, 0x50, 0x44, 0x46] },             // %PDF
  { kind: "png", bytes: [0x89, 0x50, 0x4e, 0x47] },             // \x89PNG
  { kind: "jpg", bytes: [0xff, 0xd8, 0xff] },                   // JPEG
  { kind: "xlsx", bytes: [0x50, 0x4b, 0x03, 0x04] },            // ZIP (los .xlsx son ZIP)
];

const EXTENSION_KIND: Record<string, FileKind> = { pdf: "pdf", png: "png", jpg: "jpg", jpeg: "jpg", xlsx: "xlsx" };

function detectKind(head: Uint8Array): FileKind | null {
  return SIGNATURES.find((s) => s.bytes.every((b, i) => head[i] === b))?.kind ?? null;
}

const reply = (response: FileCheckResponse) => (self as unknown as Worker).postMessage(response);

self.onmessage = async (event: MessageEvent<FileCheckRequest>) => {
  const started = performance.now();
  const { file, maxBytes } = event.data;
  try {
    if (file.size === 0) return reply({ ok: false, error: "El archivo está vacío" });
    if (file.size > maxBytes) {
      return reply({ ok: false, error: `El archivo pesa ${(file.size / 1048576).toFixed(1)} MB; el máximo es ${Math.round(maxBytes / 1048576)} MB` });
    }

    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (extension === "xls") {
      return reply({ ok: false, error: "El formato .xls (Excel 97-2003) no es compatible; guárdalo como .xlsx" });
    }
    const expected = EXTENSION_KIND[extension];
    if (!expected) return reply({ ok: false, error: "Formato no compatible. Sube un PDF, una imagen (JPG o PNG) o un Excel (.xlsx)" });

    const buffer = await file.arrayBuffer();
    const actual = detectKind(new Uint8Array(buffer, 0, Math.min(8, buffer.byteLength)));
    if (actual !== expected) {
      return reply({ ok: false, error: `El archivo dice ser .${extension} pero su contenido no lo es; puede estar dañado o renombrado` });
    }

    const digest = await crypto.subtle.digest("SHA-256", buffer);
    const hash = Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
    reply({ ok: true, kind: actual, hash, size: file.size, millis: Math.round(performance.now() - started) });
  } catch (err) {
    reply({ ok: false, error: err instanceof Error ? err.message : "No se pudo leer el archivo" });
  }
};
