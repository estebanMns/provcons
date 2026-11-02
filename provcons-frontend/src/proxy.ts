import { NextRequest, NextResponse } from "next/server";

// En Next 16 este archivo se llama proxy.ts (antes middleware.ts) y debe estar
// junto a la carpeta app/, es decir dentro de src/.
export function proxy(request: NextRequest) {
  const token = request.cookies.get("auth_token")?.value;
  const pathname = request.nextUrl.pathname;

  // Rutas públicas que no requieren autenticación
  // "/" es la página de presentación (estática con ISR)
  const publicRoutes = ["/", "/login", "/restablecer"];
  const isPublicRoute = publicRoutes.includes(pathname);

  // Si no está en ruta pública y no tiene token, redirige al login.
  // El caso contrario (/login con token) lo resuelve ClientAuthProvider, que sí
  // puede validar el token contra la API; hacerlo aquí con un token vencido
  // crearía un bucle entre /login y /dashboard.
  if (!isPublicRoute && !token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|fonts|landing).*)"],
};
