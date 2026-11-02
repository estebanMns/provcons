import type { CSSProperties } from "react";

// Figuras que viajan alrededor del fondo de la página principal: triángulos,
// X y O, solo con borde y siempre detrás del contenido. Es solo CSS (sin
// JavaScript en el navegador): cada figura recorre una órbita propia mientras
// gira sobre sí misma. Con "reducir movimiento" se quedan quietas.
const ORANGE = "#F7931E", TEAL = "#1F8A8A", YELLOW = "#E0A21F", NAVY = "#0F2A3D";

type Kind = "tri" | "x" | "o";

// x, y: punto de partida (% de la página); size en px; orbit: 1 a 3;
// dur y spin en segundos; reverse: sentido contrario; mobile: también en celular
const SHAPES: { kind: Kind; x: number; y: number; size: number; color: string; orbit: 1 | 2 | 3; dur: number; spin: number; delay: number; reverse?: boolean; mobile?: boolean }[] = [
  { kind: "tri", x: 4, y: 6, size: 70, color: ORANGE, orbit: 1, dur: 38, spin: 24, delay: 0, mobile: true },
  { kind: "o", x: 86, y: 4, size: 46, color: TEAL, orbit: 2, dur: 32, spin: 18, delay: -6, mobile: true },
  { kind: "x", x: 48, y: 2, size: 28, color: YELLOW, orbit: 3, dur: 26, spin: 14, delay: -3 },
  { kind: "tri", x: 92, y: 30, size: 84, color: TEAL, orbit: 2, dur: 44, spin: 30, delay: -12, reverse: true },
  { kind: "x", x: 2, y: 38, size: 38, color: NAVY, orbit: 3, dur: 30, spin: 20, delay: -9, mobile: true },
  { kind: "o", x: 62, y: 22, size: 22, color: ORANGE, orbit: 1, dur: 22, spin: 12, delay: -4 },
  { kind: "tri", x: 30, y: 48, size: 56, color: YELLOW, orbit: 2, dur: 36, spin: 26, delay: -15 },
  { kind: "o", x: 76, y: 56, size: 34, color: ORANGE, orbit: 3, dur: 28, spin: 16, delay: -2, reverse: true, mobile: true },
  { kind: "tri", x: 10, y: 70, size: 90, color: TEAL, orbit: 1, dur: 45, spin: 34, delay: -20 },
  { kind: "x", x: 54, y: 74, size: 34, color: NAVY, orbit: 2, dur: 34, spin: 22, delay: -8 },
  { kind: "tri", x: 88, y: 80, size: 60, color: ORANGE, orbit: 3, dur: 40, spin: 28, delay: -18, reverse: true, mobile: true },
  { kind: "o", x: 36, y: 90, size: 26, color: TEAL, orbit: 1, dur: 24, spin: 13, delay: -11 },
  { kind: "tri", x: 70, y: 92, size: 44, color: YELLOW, orbit: 2, dur: 30, spin: 19, delay: -5 },
  { kind: "x", x: 20, y: 18, size: 24, color: TEAL, orbit: 3, dur: 20, spin: 10, delay: -7, reverse: true },
  { kind: "o", x: 14, y: 2, size: 30, color: YELLOW, orbit: 2, dur: 27, spin: 15, delay: -13, mobile: true },
  { kind: "x", x: 72, y: 8, size: 32, color: ORANGE, orbit: 1, dur: 33, spin: 17, delay: -16, reverse: true },
  { kind: "tri", x: 40, y: 28, size: 40, color: NAVY, orbit: 3, dur: 37, spin: 25, delay: -10 },
  { kind: "o", x: 96, y: 50, size: 52, color: YELLOW, orbit: 1, dur: 41, spin: 29, delay: -22, reverse: true },
  { kind: "x", x: 6, y: 56, size: 30, color: ORANGE, orbit: 2, dur: 29, spin: 16, delay: -14, mobile: true },
  { kind: "tri", x: 58, y: 44, size: 30, color: TEAL, orbit: 1, dur: 25, spin: 15, delay: -1 },
  { kind: "o", x: 46, y: 62, size: 40, color: NAVY, orbit: 3, dur: 35, spin: 21, delay: -19 },
  { kind: "x", x: 82, y: 68, size: 26, color: TEAL, orbit: 2, dur: 23, spin: 12, delay: -9, reverse: true },
  { kind: "tri", x: 24, y: 84, size: 36, color: ORANGE, orbit: 3, dur: 31, spin: 18, delay: -17, mobile: true },
  { kind: "x", x: 94, y: 94, size: 36, color: YELLOW, orbit: 1, dur: 39, spin: 23, delay: -6 },
];

// Todas con el mismo grosor de línea y sin relleno
function Shape({ kind, color }: { kind: Kind; color: string }) {
  const stroke = { fill: "none", stroke: color, strokeOpacity: 0.55, strokeWidth: 6, strokeLinecap: "round", strokeLinejoin: "round" } as const;
  if (kind === "o") return <circle cx="50" cy="50" r="40" {...stroke} />;
  if (kind === "x") return <path d="M18 18 L82 82 M82 18 L18 82" {...stroke} />;
  return <polygon points="50,8 94,90 6,90" {...stroke} />;
}

export function BackgroundShapes() {
  return (
    <div className="bg-shapes" aria-hidden="true">
      {SHAPES.map((s, i) => (
        <span
          key={i}
          className={`bg-tri orbit-${s.orbit}${s.reverse ? " reverse" : ""}${s.mobile ? "" : " desktop-only"}`}
          style={{
            left: `${s.x}%`, top: `${s.y}%`,
            "--s": `${s.size}px`, "--dur": `${s.dur}s`, "--spin": `${s.spin}s`, "--delay": `${s.delay}s`,
          } as CSSProperties}
        >
          <svg viewBox="0 0 100 100"><Shape kind={s.kind} color={s.color} /></svg>
        </span>
      ))}
    </div>
  );
}
