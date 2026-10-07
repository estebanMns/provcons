import type { Metadata } from "next";
import localFont from "next/font/local";
import { RoleProvider } from "@/context/RoleContext";
import { ClientAuthProvider } from "@/components/ClientAuthProvider";
import "./globals.css";

const manrope = localFont({
  src: "./fonts/Manrope-latin.woff2",
  variable: "--font-manrope",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ProvCons",
  description: "Plataforma B2B para el sector construcción: compara proveedores con IA explicable.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={manrope.variable}>
      <body>
        <ClientAuthProvider>
          <RoleProvider>{children}</RoleProvider>
        </ClientAuthProvider>
      </body>
    </html>
  );
}
