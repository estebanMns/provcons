import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { SessionCta } from "@/components/landing/SessionCta";
import type { IconName } from "@/lib/types";

// Patrones de rendering: esta página es un Server Component.
// - SSG: se genera como HTML estático en el build (carga inmediata, sin JS
//   para el contenido principal).
// - ISR: cada 5 minutos Next la regenera en segundo plano con las cifras
//   actuales, sin volver a desplegar.
// Las pantallas privadas, en cambio, son CSR: dependen de la sesión del
// usuario, que vive en el navegador.
export const revalidate = 300;

interface PublicStats {
  providers: number;
  constructoras: number;
  catalog_products: number;
  quotations_compared: number;
  orders_delivered: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function getStats(): Promise<PublicStats | null> {
  try {
    const response = await fetch(`${API_BASE}/public/stats`, {
      next: { revalidate },
      // El backend gratuito puede estar dormido: el build nunca debe esperar
      // de más ni fallar por eso (la próxima regeneración traerá las cifras)
      signal: AbortSignal.timeout(8000),
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

const STEPS: { icon: IconName; title: string; text: string }[] = [
  { icon: "upload", title: "Sube tu lista", text: "PDF, Excel o una foto tomada en obra. La IA extrae materiales, cantidades y precios." },
  { icon: "spark", title: "Compara proveedores", text: "Reconoce sinónimos y medidas, y compara precio, stock y cobertura de cada proveedor." },
  { icon: "truck", title: "Compra y sigue el pedido", text: "Crea la orden con un clic; el proveedor la confirma, la despacha y la entrega." },
];

export default async function Home() {
  const stats = await getStats();
  const figures: { label: string; value?: number }[] = [
    { label: "Proveedores", value: stats?.providers },
    { label: "Constructoras", value: stats?.constructoras },
    { label: "Productos en catálogo", value: stats?.catalog_products },
    { label: "Cotizaciones comparadas", value: stats?.quotations_compared },
  ];

  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="brand"><span className="brand-mark"><span /></span><span>ProvCons</span></div>
        <SessionCta />
      </header>

      <section className="landing-hero">
        <p className="eyebrow">PLATAFORMA B2B PARA EL SECTOR CONSTRUCCIÓN</p>
        <h1>Compra materiales al mejor proveedor, con IA que puedes entender.</h1>
        <p>Sube tu lista de materiales y ProvCons compara a los proveedores por precio, disponibilidad y cobertura. Te dice a quién comprarle y por qué.</p>
        <div className="landing-actions">
          <Link className="btn btn-primary" href="/login"><span>Crear una organización</span></Link>
          <Link className="btn btn-secondary" href="/login"><span>Ingresar</span></Link>
        </div>
      </section>

      <section className="landing-stats" aria-label="Cifras de la plataforma">
        {figures.map((f) => (
          <div key={f.label} className="stat-card">
            <div><span>{f.label}</span><strong>{f.value ?? "—"}</strong></div>
          </div>
        ))}
      </section>

      <section className="landing-steps">
        {STEPS.map((s, i) => (
          <article key={s.title} className="card">
            <span className="landing-step-icon"><Icon name={s.icon} size={20} /></span>
            <small>Paso {i + 1}</small>
            <h2>{s.title}</h2>
            <p>{s.text}</p>
          </article>
        ))}
      </section>

      <footer className="landing-footer">
        <small>ProvCons · Cifras actualizadas cada 5 minutos{stats ? "" : " (no disponibles en este momento)"}</small>
      </footer>
    </div>
  );
}
