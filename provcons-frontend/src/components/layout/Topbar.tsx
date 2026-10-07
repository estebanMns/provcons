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

  useEffect(() => {
    getMe().then(setUser).catch(() => {
      router.push("/login");
    });
  }, [router]);

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={openMobile} aria-label="Abrir menú"><Icon name="menu" /></button>
      <div className="org-info">
        <strong>{user?.organization?.name || "Organización"}</strong>
        <span><span className="status-dot" /> Organización verificada</span>
      </div>
      <div className="top-actions">
        <button className="icon-btn" aria-label="Buscar"><Icon name="search" /></button>
        <button className="icon-btn notification" aria-label="Notificaciones"><Icon name="bell" /><span /></button>
      </div>
    </header>
  );
}
