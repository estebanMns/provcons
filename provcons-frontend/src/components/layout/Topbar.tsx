"use client";

import { useRouter } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import { Icon } from "@/components/ui/Icon";

export function Topbar({ openMobile }: { openMobile: () => void }) {
  const { role, setRole } = useRole();
  const router = useRouter();
  const switchRole = (next: typeof role) => { setRole(next); router.push("/dashboard"); };
  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={openMobile} aria-label="Abrir menú"><Icon name="menu" /></button>
      <div className="org-info">
        <strong>{role === "proveedor" ? "Materiales del Norte S.A.S." : "Constructora Andina S.A.S."}</strong>
        <span><span className="status-dot" /> Organización verificada</span>
      </div>
      <div className="top-actions">
        <div className="role-switch" aria-label="Cambiar vista de demostración">
          <button className={role === "proveedor" ? "selected" : ""} onClick={() => switchRole("proveedor")}>Proveedor</button>
          <button className={role === "constructora" ? "selected" : ""} onClick={() => switchRole("constructora")}>Constructora</button>
        </div>
        <button className="icon-btn" aria-label="Buscar"><Icon name="search" /></button>
        <button className="icon-btn notification" aria-label="Notificaciones"><Icon name="bell" /><span /></button>
      </div>
    </header>
  );
}
