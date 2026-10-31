"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getToken } from "@/lib/api";

// "/" es la página de presentación pública; "/login" el acceso
const PUBLIC_ROUTES = ["/", "/login"];

export function ClientAuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    const token = getToken();
    const isPublicRoute = PUBLIC_ROUTES.includes(pathname);

    if (!token && !isPublicRoute) {
      router.replace("/login");
    } else if (token && pathname === "/login") {
      // Con sesión no tiene sentido ver el login; la presentación sí se puede ver
      router.replace("/dashboard");
    }
  }, [pathname, router]);

  // Verificar cambios de token cada segundo para detectar logout
  useEffect(() => {
    const interval = setInterval(() => {
      if (!getToken() && !PUBLIC_ROUTES.includes(pathname)) {
        router.replace("/login");
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [pathname, router]);

  return <>{children}</>;
}
