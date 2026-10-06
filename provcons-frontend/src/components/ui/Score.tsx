import type { CSSProperties } from "react";

export function Score({ value, compact = false }: { value: number; compact?: boolean }) {
  return (
    <div className={`score ${compact ? "score-compact" : ""}`} style={{ "--score": `${value * 3.6}deg` } as CSSProperties}>
      <strong>{value}</strong>
      {!compact && <span>/100</span>}
    </div>
  );
}
