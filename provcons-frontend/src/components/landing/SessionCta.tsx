"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";

// Única parte de la página de presentación que corre en el navegador: la
// sesión está en localStorage, que no existe al generar el HTML estático.
export function SessionCta() {
  const [hasSession, setHasSession] = useState(false);

  useEffect(() => {
    setHasSession(Boolean(getToken()));
  }, []);

  return hasSession
    ? <Link className="btn btn-primary" href="/dashboard"><span>Ir a mi panel</span></Link>
    : <Link className="btn btn-secondary" href="/login"><span>Ingresar</span></Link>;
}
