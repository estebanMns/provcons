"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getToken } from "@/lib/api";

export function ClientAuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    const publicRoutes = ["/login"];
    const isPublicRoute = publicRoutes.includes(pathname);

    if (!token && !isPublicRoute) {
      router.replace("/login");
    } else if (token && isPublicRoute) {
      router.replace("/dashboard");
    }

    setIsChecking(false);
  }, [pathname, router]);

  // Verificar cambios de token cada segundo para detectar logout
  useEffect(() => {
    const interval = setInterval(() => {
      const token = getToken();
      const publicRoutes = ["/login"];
      const isPublicRoute = publicRoutes.includes(pathname);

      if (!token && !isPublicRoute) {
        router.replace("/login");
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [pathname, router]);

  return <>{children}</>;
}
