"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { navItems, viewPaths } from "@/lib/navigation";
import { Icon } from "@/components/ui/Icon";
import { getMe, clearToken } from "@/lib/api";
import type { User } from "@/lib/api";

interface SidebarProps { mobileOpen: boolean; closeMobile: () => void }

export function Sidebar({ mobileOpen, closeMobile }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    getMe()
      .then((userData) => {
        setUser(userData);
      })
      .catch(() => {
        clearToken();
        router.push("/login");
      });
  }, [router]);

  // Filtrar items según el rol
  const isProvider = user?.organization?.type === "proveedor";
  const filteredItems = isProvider
    ? navItems.filter((item) => ["dashboard", "inventario", "ordenes", "auditoria"].includes(item.id))
    : navItems.filter((item) => ["dashboard", "cotizaciones", "ordenes", "auditoria"].includes(item.id));

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };
  return (
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><span className="brand-mark"><span /></span><span>ProvCons</span></div>
      <button className="sidebar-close" onClick={closeMobile} aria-label="Cerrar menú"><Icon name="close" /></button>
      <nav className="side-nav" aria-label="Navegación principal">
        {filteredItems.map((item) => (
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
        <button type="button">Ir al centro de ayuda <Icon name="arrow" size={15} /></button>
      </div>
      <button className="user-card" onClick={handleLogout} aria-label="Cerrar sesión">
        <span className="avatar">{user?.full_name?.slice(0, 2).toUpperCase() || "U"}</span>
        <div><strong>{user?.full_name || "Usuario"}</strong><small>{user?.organization?.type === "proveedor" ? "Proveedor" : "Constructora"}</small></div>
        <Icon name="chevron" size={16} />
      </button>
    </aside>
  );
}
