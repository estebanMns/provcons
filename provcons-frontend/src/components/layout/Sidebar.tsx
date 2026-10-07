"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { navItems, viewPaths } from "@/lib/navigation";
import { Icon } from "@/components/ui/Icon";
import { Button } from "@/components/ui/Button";
import { getMe, clearToken } from "@/lib/api";
import type { User } from "@/lib/api";

interface SidebarProps { mobileOpen: boolean; closeMobile: () => void }

export function Sidebar({ mobileOpen, closeMobile }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [showLogoutModal, setShowLogoutModal] = useState(false);

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

  const handleLogoutClick = () => {
    setShowLogoutModal(true);
  };

  const confirmLogout = () => {
    clearToken();
    setShowLogoutModal(false);
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
      <button className="user-card" onClick={handleLogoutClick} aria-label="Cerrar sesión">
        <span className="avatar">{user?.full_name?.slice(0, 2).toUpperCase() || "U"}</span>
        <div><strong>{user?.full_name || "Usuario"}</strong><small>{user?.organization?.type === "proveedor" ? "Proveedor" : "Constructora"}</small></div>
        <Icon name="chevron" size={16} />
      </button>

      {showLogoutModal && (
        <div className="modal-backdrop" onClick={() => setShowLogoutModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <span className="modal-icon"><Icon name="shield" size={26} /></span>
            <h2>¿Cerrar sesión?</h2>
            <p>¿Estás seguro de que deseas cerrar sesión? Tendrás que volver a ingresar con tus credenciales.</p>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setShowLogoutModal(false)}>Cancelar</Button>
              <Button icon="arrow" onClick={confirmLogout}>Sí, cerrar sesión</Button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
