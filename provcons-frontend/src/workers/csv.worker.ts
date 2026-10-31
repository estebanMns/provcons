// Web Worker: arma el CSV del historial en un hilo aparte del navegador.
// Con miles de eventos, construir y escapar el texto en el hilo principal
// congelaría la pantalla; aquí corre en paralelo y solo devuelve el resultado.

export interface CsvRequest {
  header: string[];
  rows: string[][];
}

export interface CsvResponse {
  csv: string;
  rows: number;
  millis: number;
}

const escape = (value: string) => `"${value.replaceAll('"', '""')}"`;

self.onmessage = (event: MessageEvent<CsvRequest>) => {
  const started = performance.now();
  const { header, rows } = event.data;
  // BOM para que Excel abra bien las tildes
  const csv = "﻿" + [header, ...rows].map((r) => r.map((c) => escape(String(c ?? ""))).join(",")).join("\r\n");
  const response: CsvResponse = { csv, rows: rows.length, millis: Math.round(performance.now() - started) };
  (self as unknown as Worker).postMessage(response);
};
