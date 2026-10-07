"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import type { Role } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { signup, login, setToken } from "@/lib/api";

type Step = "login" | "register" | "ready";

function Brand() {
  return <div className="brand"><span className="brand-mark"><span /></span><span>ProvCons</span></div>;
}

export function Auth() {
  const router = useRouter();
  const { setRole } = useRole();
  const [step, setStep] = useState<Step>("login");
  const [authRole, setAuthRole] = useState<Role>("proveedor");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const [loginEmail, setLoginEmail] = useState("carlos@materialesdelnorte.com");
  const [loginPassword, setLoginPassword] = useState("provcons2025");

  const [signupOrgName, setSignupOrgName] = useState("");
  const [signupTaxId, setSignupTaxId] = useState("");
  const [signupFullName, setSignupFullName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");

  const enter = (role: Role) => {
    setRole(role);
    router.push(role === "proveedor" ? "/inventario" : "/dashboard");
  };

  const handleLogin = async () => {
    setError("");
    setLoading(true);
    try {
      const token = await login({ email: loginEmail, password: loginPassword });
      setToken(token);
      enter("proveedor");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al iniciar sesión";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async () => {
    setError("");
    setLoading(true);
    try {
      const user = await signup({
        organization_name: signupOrgName,
        organization_type: authRole,
        tax_id: signupTaxId,
        full_name: signupFullName,
        email: signupEmail,
        password: signupPassword,
      });
      setToken("");
      setStep("ready");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al crear la organización";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (step === "ready") {
    return (
      <div className="auth-shell">
        <aside className="auth-story">
          <Brand />
          <div className="auth-story-content">
            <Badge tone="success"><Icon name="check" size={12} /> Organización creada</Badge>
            <h1>Todo listo para comenzar.</h1>
            <p>Te guiaremos para que obtengas valor desde el primer día, sin configuraciones complicadas.</p>
          </div>
          <small>Decisiones de compra más claras, con IA que puedes entender.</small>
        </aside>
        <main className="auth-main">
          <div className="welcome-card">
            <span className="welcome-icon"><Icon name={authRole === "proveedor" ? "box" : "building"} size={30} /></span>
            <p className="eyebrow">BIENVENIDO A PROVCONS</p>
            <h2>Tu espacio está listo</h2>
            <p>{authRole === "proveedor" ? "Sube tu catálogo para que encontremos cotizaciones compatibles con tu inventario." : "Crea tu primera cotización y compararemos proveedores por precio, disponibilidad y logística."}</p>
            <div className="first-step">
              <span>1</span>
              <div>
                <strong>{authRole === "proveedor" ? "Sube tu catálogo o inventario" : "Crea una cotización"}</strong>
                <p>{authRole === "proveedor" ? "Aceptamos Excel, PDF y fotos tomadas desde tu celular." : "Solo necesitas indicar material, cantidad y unidad."}</p>
              </div>
            </div>
            <Button wide icon="arrow" onClick={() => enter(authRole)}>{authRole === "proveedor" ? "Subir mi catálogo" : "Crear mi primera cotización"}</Button>
            <button className="skip-link" onClick={() => { setRole(authRole); router.push("/dashboard"); }}>Explorar primero el panel</button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <aside className="auth-story">
        <Brand />
        <div className="auth-story-content">
          <p className="eyebrow">COMPRAS Y VENTAS, SIN SUPOSICIONES</p>
          <h1>Construye acuerdos con más confianza.</h1>
          <p>Compara oportunidades, entiende cada recomendación y toma mejores decisiones con información clara.</p>
          <div className="auth-proof">
            <span><Icon name="shield" /></span>
            <div><strong>IA explicable y segura</strong><p>Siempre sabrás por qué recomendamos una opción.</p></div>
          </div>
        </div>
        <small>ProvCons · Plataforma B2B para el sector construcción</small>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <button className="auth-back" onClick={() => (step === "register" ? setStep("login") : enter("proveedor"))}>
            <Icon name="arrow" size={16} /> {step === "register" ? "Volver" : "Volver a la demo"}
          </button>
          <p className="eyebrow">{step === "login" ? "ACCESO SEGURO" : "CREAR ORGANIZACIÓN"}</p>
          <h2>{step === "login" ? "Bienvenido de nuevo" : "Cuéntanos sobre tu empresa"}</h2>
          <p>{step === "login" ? "Ingresa con tu correo corporativo." : "Usaremos estos datos para configurar tu experiencia."}</p>
          {error && <div style={{ color: "red", marginBottom: "1rem" }}>{error}</div>}
          {step === "login" ? (
            <>
              <label>Correo corporativo<input type="email" placeholder="nombre@empresa.com" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} disabled={loading} /></label>
              <label>Contraseña<div className="password-field"><input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} disabled={loading} /><button type="button">Mostrar</button></div></label>
              <div className="login-options"><label><input type="checkbox" defaultChecked /> Recordarme</label><button type="button">Olvidé mi contraseña</button></div>
              <Button wide onClick={handleLogin} disabled={loading}>{loading ? "Ingresando..." : "Ingresar a ProvCons"}</Button>
              <div className="auth-divider"><span /> o <span /></div>
              <button className="create-account" onClick={() => { setStep("register"); setError(""); }} disabled={loading}>Crear una organización nueva <Icon name="arrow" size={15} /></button>
            </>
          ) : (
            <>
              <label>Nombre de la organización<input placeholder="Ej. Materiales del Norte S.A.S." value={signupOrgName} onChange={(e) => setSignupOrgName(e.target.value)} disabled={loading} /></label>
              <label>NIT<input placeholder="900.123.456-7" value={signupTaxId} onChange={(e) => setSignupTaxId(e.target.value)} disabled={loading} /></label>
              <fieldset>
                <legend>¿Qué tipo de organización eres?</legend>
                <div className="role-options">
                  <button className={authRole === "constructora" ? "selected" : ""} onClick={() => setAuthRole("constructora")} disabled={loading} type="button"><Icon name="building" /><span><strong>Constructora</strong><small>Busco materiales y proveedores</small></span></button>
                  <button className={authRole === "proveedor" ? "selected" : ""} onClick={() => setAuthRole("proveedor")} disabled={loading} type="button"><Icon name="box" /><span><strong>Proveedor</strong><small>Ofrezco materiales e inventario</small></span></button>
                </div>
              </fieldset>
              <label>Tu nombre completo<input placeholder="Ej. Juan Pérez" value={signupFullName} onChange={(e) => setSignupFullName(e.target.value)} disabled={loading} /></label>
              <label>Tu correo de trabajo<input type="email" placeholder="nombre@empresa.com" value={signupEmail} onChange={(e) => setSignupEmail(e.target.value)} disabled={loading} /></label>
              <label>Contraseña<input type="password" placeholder="Mínimo 8 caracteres" value={signupPassword} onChange={(e) => setSignupPassword(e.target.value)} disabled={loading} /></label>
              <Button wide icon="arrow" onClick={handleSignup} disabled={loading}>{loading ? "Creando..." : "Crear organización y continuar"}</Button>
              <small className="legal">Al continuar aceptas los términos de servicio y la política de privacidad.</small>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
