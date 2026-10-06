"use client";

import { usePathname, useRouter } from "next/navigation";
import { navItems, viewPaths } from "@/lib/navigation";
import { Icon } from "@/components/ui/Icon";

interface SidebarProps { mobileOpen: boolean; closeMobile: () => void }

export function Sidebar({ mobileOpen, closeMobile }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  return (
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><span className="brand-mark"><span /></span><span>ProvCons</span></div>
      <button className="sidebar-close" onClick={closeMobile} aria-label="Cerrar menú"><Icon name="close" /></button>
      <nav className="side-nav" aria-label="Navegación principal">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={pathname === viewPaths[item.id] ? "active" : ""}
            onClick={() => { router.push(viewPaths[item.id]); closeMobile(); }}
          >
            <Icon name={item.icon} /><span>{item.label}</span>{item.id === "ordenes" && <em>2</em>}
          </button>
        ))}
      </nav>
      <div className="side-help">
        <span className="help-icon"><Icon name="spark" size={18} /></span>
        <strong>¿Necesitas ayuda?</strong>
        <p>Te acompañamos paso a paso.</p>
        <button>Ir al centro de ayuda <Icon name="arrow" size={15} /></button>
      </div>
      <button className="user-card" onClick={() => router.push("/login")} aria-label="Ir a la pantalla de acceso">
        <span className="avatar">CM</span>
        <div><strong>Carlos Méndez</strong><small>Administrador</small></div>
        <Icon name="chevron" size={16} />
      </button>
    </aside>
  );
}
