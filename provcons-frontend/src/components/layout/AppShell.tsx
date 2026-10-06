"use client";

import { useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { navItems, viewPaths } from "@/lib/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const title = navItems.find((x) => viewPaths[x.id] === pathname)?.label;
  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileOpen} closeMobile={() => setMobileOpen(false)} />
      {mobileOpen && <button className="mobile-overlay" onClick={() => setMobileOpen(false)} aria-label="Cerrar menú" />}
      <div className="main-shell">
        <Topbar openMobile={() => setMobileOpen(true)} />
        <main aria-label={title}>{children}</main>
      </div>
    </div>
  );
}
