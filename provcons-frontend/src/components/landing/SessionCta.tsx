"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { getToken } from "@/lib/api";

// La sesión vive en localStorage (un "almacén externo" a React): se lee con
// useSyncExternalStore. En el servidor (HTML estático de SSG) no hay sesión,
// por eso getServerSnapshot devuelve false y el navegador lo ajusta al hidratar.
const subscribe = (onChange: () => void) => {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};

export function SessionCta({ className = "btn btn-secondary" }: { className?: string }) {
  const hasSession = useSyncExternalStore(subscribe, () => Boolean(getToken()), () => false);

  return hasSession
    ? <Link className={className} href="/dashboard"><span>Ir a mi panel</span></Link>
    : <Link className={className} href="/login"><span>Iniciar sesión</span></Link>;
}
