"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import { Icon } from "@/components/ui/Icon";
import { getMe } from "@/lib/api";
import type { User } from "@/lib/api";

export function Topbar({ openMobile }: { openMobile: () => void }) {
  const { role } = useRole();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [showSearch, setShowSearch] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    getMe().then(setUser).catch(() => {
      router.push("/login");
    });
  }, [router]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      console.log("Búsqueda:", searchQuery);
      // Aquí irá la lógica de búsqueda real
      setShowSearch(false);
      setSearchQuery("");
    }
  };

  const notifications = [
    { id: 1, message: "No hay notificaciones nuevas", time: "Hace un momento" }
  ];

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={openMobile} aria-label="Abrir menú"><Icon name="menu" /></button>
      <div className="org-info">
        <strong>{user?.organization?.name || "Organización"}</strong>
        <span><span className="status-dot" /> Organización verificada</span>
      </div>
      <div className="top-actions">
        <button
          className="icon-btn"
          aria-label="Buscar"
          onClick={() => setShowSearch(!showSearch)}
        >
          <Icon name="search" />
        </button>
        <button
          className="icon-btn notification"
          aria-label="Notificaciones"
          onClick={() => setShowNotifications(!showNotifications)}
        >
          <Icon name="bell" /><span />
        </button>
      </div>

      {showSearch && (
        <div className="search-modal" onClick={() => setShowSearch(false)}>
          <div className="search-content" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleSearch}>
              <Icon name="search" size={20} />
              <input
                type="text"
                placeholder="Buscar órdenes, cotizaciones, proveedores..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
              />
              <button type="button" onClick={() => setShowSearch(false)} aria-label="Cerrar">
                <Icon name="close" size={20} />
              </button>
            </form>
            <div className="search-results">
              {searchQuery ? (
                <p style={{ padding: "1rem", color: "var(--text-secondary)" }}>
                  No se encontraron resultados para "{searchQuery}"
                </p>
              ) : (
                <p style={{ padding: "1rem", color: "var(--text-secondary)" }}>
                  Escribe algo para buscar...
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {showNotifications && (
        <div className="notifications-panel">
          <div className="notifications-header">
            <h3>Notificaciones</h3>
            <button onClick={() => setShowNotifications(false)} aria-label="Cerrar">
              <Icon name="close" size={18} />
            </button>
          </div>
          <div className="notifications-list">
            {notifications.map((notif) => (
              <div key={notif.id} className="notification-item">
                <div>
                  <p>{notif.message}</p>
                  <small>{notif.time}</small>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <style jsx>{`
        .search-modal {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: flex-start;
          justify-content: center;
          padding-top: 100px;
          z-index: 1000;
        }

        .search-content {
          background: white;
          border-radius: 8px;
          width: 90%;
          max-width: 600px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
          overflow: hidden;
        }

        .search-content form {
          display: flex;
          align-items: center;
          padding: 1rem;
          border-bottom: 1px solid var(--border-color);
          gap: 0.5rem;
        }

        .search-content input {
          flex: 1;
          border: none;
          outline: none;
          font-size: 1rem;
          padding: 0.5rem;
        }

        .search-content button {
          background: none;
          border: none;
          cursor: pointer;
          padding: 0.5rem;
          display: flex;
          align-items: center;
        }

        .search-results {
          max-height: 400px;
          overflow-y: auto;
        }

        .notifications-panel {
          position: absolute;
          top: 60px;
          right: 20px;
          background: white;
          border-radius: 8px;
          width: 350px;
          max-height: 400px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
          z-index: 100;
          display: flex;
          flex-direction: column;
        }

        .notifications-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem;
          border-bottom: 1px solid var(--border-color);
        }

        .notifications-header h3 {
          margin: 0;
          font-size: 1rem;
        }

        .notifications-header button {
          background: none;
          border: none;
          cursor: pointer;
          padding: 0.5rem;
          display: flex;
          align-items: center;
        }

        .notifications-list {
          overflow-y: auto;
          flex: 1;
        }

        .notification-item {
          padding: 1rem;
          border-bottom: 1px solid var(--border-color);
          cursor: pointer;
          transition: background 0.2s;
        }

        .notification-item:hover {
          background: var(--bg-secondary);
        }

        .notification-item p {
          margin: 0 0 0.5rem 0;
          font-size: 0.95rem;
        }

        .notification-item small {
          color: var(--text-secondary);
          font-size: 0.85rem;
        }
      `}</style>
    </header>
  );
}
