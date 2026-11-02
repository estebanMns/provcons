import { Suspense } from "react";
import { Auth } from "@/components/screens/Auth";

// Suspense: Auth lee ?registro=1 con useSearchParams y la página sigue siendo estática
export default function LoginPage() {
  return <Suspense><Auth /></Suspense>;
}
