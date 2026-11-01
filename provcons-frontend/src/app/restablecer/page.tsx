import { Suspense } from "react";
import type { Metadata } from "next";
import { ResetPassword } from "@/components/screens/ResetPassword";

export const metadata: Metadata = { title: "Restablecer contraseña · ProvCons" };

// useSearchParams necesita un límite de Suspense para que la página se
// pueda generar estática; el token se lee en el navegador.
export default function RestablecerPage() {
  return (
    <Suspense>
      <ResetPassword />
    </Suspense>
  );
}
