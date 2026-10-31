// Acceso a los Web Workers de la app.
// Cada worker se crea con `new Worker(new URL(..., import.meta.url))`: así el
// empaquetador de Next lo detecta y lo publica como un archivo aparte. Se
// crea uno por tarea y siempre se termina al acabar (no quedan hilos vivos).
import type { CsvRequest, CsvResponse } from "@/workers/csv.worker";
import type { FileCheckRequest, FileCheckResponse } from "@/workers/file-check.worker";

function runInWorker<TIn, TOut>(worker: Worker, message: TIn, timeoutMs = 30000): Promise<TOut> {
  return new Promise<TOut>((resolve, reject) => {
    const timer = setTimeout(() => {
      worker.terminate();
      reject(new Error("La tarea en segundo plano tardó demasiado"));
    }, timeoutMs);
    worker.onmessage = (event: MessageEvent<TOut>) => {
      clearTimeout(timer);
      worker.terminate();
      resolve(event.data);
    };
    worker.onerror = (event) => {
      clearTimeout(timer);
      worker.terminate();
      reject(new Error(event.message || "Error en la tarea en segundo plano"));
    };
    worker.postMessage(message);
  });
}

export function buildCsvInWorker(request: CsvRequest): Promise<CsvResponse> {
  return runInWorker(new Worker(new URL("../workers/csv.worker.ts", import.meta.url), { type: "module" }), request);
}

export function checkFileInWorker(request: FileCheckRequest): Promise<FileCheckResponse> {
  return runInWorker(new Worker(new URL("../workers/file-check.worker.ts", import.meta.url), { type: "module" }), request);
}
