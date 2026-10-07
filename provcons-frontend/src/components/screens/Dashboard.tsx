"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import { viewPaths } from "@/lib/navigation";
import type { View } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { getMe } from "@/lib/api";
import type { User } from "@/lib/api";

export function Dashboard() {
  const { role } = useRole();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const go = (view: View) => router.push(viewPaths[view]);
  const provider = role === "proveedor";

  useEffect(() => {
    getMe().then(setUser).catch(() => {
      router.push("/login");
    });
  }, [router]);

  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <h1>Bienvenido, {user?.full_name?.split(" ")[0] || "Usuario"}</h1>
          <p>{provider ? "Tu espacio de provedor está listo. Comienza subiendo tu catálogo o inventario." : "Tu espacio de constructor está listo. Comienza creando tu primera cotización."}</p>
        </div>
        <Button icon={provider ? "upload" : "plus"} onClick={() => go(provider ? "inventario" : "cotizaciones")}>
          {provider ? "Subir inventario" : "Nueva cotización"}
        </Button>
      </section>

      <section className="card" style={{ padding: "2rem", textAlign: "center" }}>
        <div style={{ opacity: 0.5, marginBottom: "1rem" }}>
          <Icon name={provider ? "box" : "file"} size={48} />
        </div>
        <h2 style={{ marginBottom: "0.5rem" }}>Aquí irán tus datos</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          {provider
            ? "Una vez subas tu inventario, verás aquí un resumen de tu catálogo y oportunidades de venta."
            : "Una vez crees cotizaciones, verás aquí un resumen de tus compras pendientes y proveedores sugeridos."
          }
        </p>
      </section>
    </div>
  );
}
