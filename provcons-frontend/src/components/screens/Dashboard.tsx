"use client";

import { useRouter } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import { viewPaths } from "@/lib/navigation";
import type { View } from "@/lib/types";
import { Attention } from "@/components/ui/Attention";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Opportunity } from "@/components/ui/Opportunity";
import { StatCard } from "@/components/ui/StatCard";

export function Dashboard() {
  const { role } = useRole();
  const router = useRouter();
  const go = (view: View) => router.push(viewPaths[view]);
  const provider = role === "proveedor";
  return (
    <div className="page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">MARTES, 14 DE MAYO</p>
          <h1>Buenos días, Carlos</h1>
          <p>{provider ? "Esto es lo que está pasando con tus ventas hoy." : "Estas son las oportunidades y compras que requieren tu atención."}</p>
        </div>
        <Button icon={provider ? "upload" : "plus"} onClick={() => go(provider ? "inventario" : "cotizaciones")}>
          {provider ? "Actualizar inventario" : "Nueva cotización"}
        </Button>
      </section>
      <div className="stats-grid">
        <StatCard label={provider ? "Inventario activo" : "Cotizaciones activas"} value={provider ? "248 ítems" : "6"} detail={provider ? "Actualizado hace 2 días" : "2 cierran esta semana"} icon={provider ? "box" : "file"} tone="blue" />
        <StatCard label={provider ? "Oportunidades aptas" : "Proveedores sugeridos"} value={provider ? "12" : "18"} detail={provider ? "+4 desde ayer" : "5 nuevos matches"} icon="spark" tone="purple" />
        <StatCard label="Órdenes por confirmar" value="2" detail="$ 24.680.000 COP" icon="truck" tone="orange" />
        <StatCard label={provider ? "Tasa de aceptación" : "Ahorro estimado"} value={provider ? "78%" : "8,4%"} detail={provider ? "+6% este mes" : "$ 9,2 M este mes"} icon="check" tone="green" />
      </div>

      <div className="dashboard-grid">
        <section className="card opportunities">
          <div className="card-head">
            <div><h2>{provider ? "Oportunidades recomendadas" : "Proveedores recomendados"}</h2><p>Priorizadas por afinidad con tus necesidades.</p></div>
            <button onClick={() => go("cotizaciones")}>Ver todas <Icon name="arrow" size={16} /></button>
          </div>
          {provider ? (
            <>
              <Opportunity name="Cemento gris y varilla corrugada" company="Constructora Bolívar · Bogotá" value="$ 18.400.000" score={94} tags={["Inventario completo", "Entrega cercana"]} />
              <Opportunity name="Arena lavada y grava ¾" company="Obras del Centro · Chía" value="$ 7.850.000" score={87} tags={["Buen precio", "Pago a 30 días"]} />
              <Opportunity name="Bloque estructural N.° 5" company="Grupo Hábitat · Cajicá" value="$ 12.100.000" score={82} tags={["Stock suficiente", "Ruta habitual"]} />
            </>
          ) : (
            <>
              <Opportunity name="Aceros Colombia S.A.S." company="Para cotización COT-0248 · Bogotá" value="$ 47.200.000" score={96} tags={["Stock completo", "Mejor precio"]} />
              <Opportunity name="Distribuciones El Roble" company="Para cotización COT-0246 · Chía" value="$ 31.850.000" score={89} tags={["Entrega rápida", "Crédito 30 días"]} />
              <Opportunity name="Suministros Andinos" company="Para cotización COT-0248 · Bogotá" value="$ 49.100.000" score={85} tags={["Bajo riesgo", "Stock completo"]} />
            </>
          )}
        </section>
        <aside className="card attention">
          <div className="card-head"><div><h2>Requiere tu atención</h2><p>Acciones pendientes.</p></div></div>
          <Attention icon="truck" title="Confirma una nueva orden" text="OC-1842 · $ 18.400.000" time="Hace 20 min" onClick={() => go("ordenes")} />
          <Attention icon="warning" title={provider ? "12 ítems con poco stock" : "Cotización próxima a cerrar"} text={provider ? "Revisa antes de recibir pedidos" : "COT-0246 · cierra mañana"} time="Hace 3 h" />
          <Attention icon="file" title={provider ? "Catálogo por revisar" : "3 propuestas por comparar"} text={provider ? "La IA detectó 4 dudas" : "COT-0248 · Acero estructural"} time="Ayer" onClick={() => go(provider ? "inventario" : "cotizaciones")} />
        </aside>
      </div>
    </div>
  );
}
