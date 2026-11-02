"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRole } from "@/context/RoleContext";
import type { Role } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Excavator3D } from "@/components/auth/Excavator3D";
import { signup, login, setToken, getMe, requestPasswordReset } from "@/lib/api";
import type { SignupPayload } from "@/lib/api";
import type { IconName } from "@/lib/types";

type Step = "login" | "register" | "forgot" | "ready";

// Las dos tarjetas del registro (diseño de Figma). Cada una trae su propio
// formulario: quien llena la de proveedor se registra como proveedor.
const PLANS: { role: Role; tag: string; title: string; chip: string; icon: IconName; features: string[] }[] = [
  {
    role: "constructora", tag: "PARA COMPRAR", title: "Constructora", chip: "Compras de materiales", icon: "building",
    features: [
      "Sube tu lista en PDF, Excel o una foto tomada en obra",
      "Compara proveedores por precio, stock y cobertura",
      "La IA predice qué pasará con cada opción de compra",
      "Crea órdenes y sigue cada entrega",
    ],
  },
  {
    role: "proveedor", tag: "PARA VENDER", title: "Proveedor", chip: "Ventas e inventario", icon: "box",
    features: [
      "Sube tu catálogo y aparece en las comparaciones",
      "Antes de aceptar, ve si la constructora cumple",
      "Propón cuotas y el tiempo de entrega",
      "Despacha y marca cada orden entregada",
    ],
  },
];

// El logo lleva siempre a la página principal
export function Brand() {
  return <Link href="/" className="brand" aria-label="ProvCons, ir al inicio"><span className="brand-mark"><span /></span><span>ProvCons</span></Link>;
}

export function Auth() {
  const router = useRouter();
  const { setRole } = useRole();
  // /login?registro=1 abre directamente el registro (enlaces de la página principal)
  const [step, setStep] = useState<Step>(useSearchParams().get("registro") ? "register" : "login");
  const [authRole, setAuthRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [signupRole, setSignupRole] = useState<Role | null>(null);  // tarjeta que se está enviando
  const [signupError, setSignupError] = useState<{ role: Role; message: string } | null>(null);

  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotMessage, setForgotMessage] = useState("");

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

      // Obtener el usuario y su organización para saber el rol real
      const user = await getMe();
      const userRole = user.organization?.type === "proveedor" ? "proveedor" : "constructora";
      enter(userRole);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al iniciar sesión";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Cada tarjeta envía sus propios datos: la organización queda del tipo de la tarjeta
  const handleSignup = async (data: Omit<SignupPayload, "organization_type">, role: Role) => {
    setSignupError(null);
    setSignupRole(role);
    try {
      await signup({ ...data, organization_type: role });
      // Se inicia sesión de una vez: los botones de la pantalla de bienvenida
      // llevan a páginas protegidas.
      setToken(await login({ email: data.email, password: data.password }));
      setAuthRole(role);
      setStep("ready");
    } catch (err: unknown) {
      setSignupError({ role, message: err instanceof Error ? err.message : "Error al crear la organización" });
    } finally {
      setSignupRole(null);
    }
  };

  const handleForgot = async () => {
    setError("");
    if (!forgotEmail.includes("@")) {
      setError("Escribe el correo con el que ingresas a ProvCons.");
      return;
    }
    setLoading(true);
    try {
      setForgotMessage(await requestPasswordReset(forgotEmail.trim()));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo enviar el enlace");
    } finally {
      setLoading(false);
    }
  };

  const goTo = (next: Step) => { setStep(next); setError(""); setForgotMessage(""); setSignupError(null); };

  const heading = {
    login: { eyebrow: "ACCESO SEGURO", title: "Bienvenido de nuevo", text: "Ingresa con tu correo corporativo." },
    register: { eyebrow: "CREAR ORGANIZACIÓN", title: "Cuéntanos sobre tu empresa", text: "Usaremos estos datos para configurar tu experiencia." },
    forgot: { eyebrow: "RECUPERAR ACCESO", title: "¿Olvidaste tu contraseña?", text: "Escribe tu correo y te enviaremos un enlace para crear una nueva. El enlace vence en 30 minutos." },
  }[step === "ready" ? "login" : step];

  if (step === "ready" && authRole) {
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

  if (step === "register") {
    return (
      <div className="auth-shell">
        <AuthStory withExcavator />
        <main className="auth-main">
          <div className="register-panel">
            <button className="auth-back" onClick={() => goTo("login")}><Icon name="arrow" size={16} /> Volver</button>
            <p className="eyebrow">CREAR ORGANIZACIÓN</p>
            <h2>¿Cómo usarás ProvCons?</h2>
            <p>Llena la tarjeta que corresponde a tu empresa y regístrate.</p>
            <div className="plan-grid">
              {PLANS.map((plan) => (
                <RegisterCard
                  key={plan.role}
                  plan={plan}
                  sending={signupRole === plan.role}
                  disabled={signupRole !== null}
                  error={signupError?.role === plan.role ? signupError.message : ""}
                  onSubmit={(data) => handleSignup(data, plan.role)}
                />
              ))}
            </div>
            <small className="legal">Al continuar aceptas los términos de servicio y la política de privacidad.</small>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <AuthStory />
      <main className="auth-main">
        <div className="auth-card">
          {step === "forgot" ? (
            <button className="auth-back" onClick={() => goTo("login")}>
              <Icon name="arrow" size={16} /> Volver
            </button>
          ) : (
            <Link className="auth-back" href="/"><Icon name="arrow" size={16} /> Volver al inicio</Link>
          )}
          <p className="eyebrow">{heading.eyebrow}</p>
          <h2>{heading.title}</h2>
          <p>{heading.text}</p>
          {error && <div style={{ color: "var(--danger)", marginBottom: "1rem", fontSize: 12 }}>{error}</div>}
          {step === "forgot" ? (
            forgotMessage ? (
              <>
                <div className="auth-notice" role="status"><Icon name="check" size={16} /> <span>{forgotMessage}</span></div>
                <Button wide onClick={() => goTo("login")}>Volver a ingresar</Button>
              </>
            ) : (
              <>
                <label>Correo corporativo<input type="email" placeholder="nombre@empresa.com" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleForgot()} disabled={loading} autoFocus /></label>
                <Button wide onClick={handleForgot} disabled={loading}>{loading ? "Enviando..." : "Enviarme el enlace"}</Button>
              </>
            )
          ) : (
            <>
              <label>Correo corporativo<input type="email" placeholder="nombre@empresa.com" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} disabled={loading} /></label>
              <label>Contraseña<div className="password-field"><input type={showPassword ? "text" : "password"} value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleLogin()} disabled={loading} /><button type="button" onClick={() => setShowPassword((v) => !v)}>{showPassword ? "Ocultar" : "Mostrar"}</button></div></label>
              <div className="login-options">
                <span />
                <button type="button" onClick={() => { setForgotEmail(loginEmail); goTo("forgot"); }}>Olvidé mi contraseña</button>
              </div>
              <Button wide onClick={handleLogin} disabled={loading}>{loading ? "Ingresando..." : "Ingresar a ProvCons"}</Button>
              <div className="auth-divider"><span /> o <span /></div>
              <button className="create-account" onClick={() => goTo("register")} disabled={loading}>Crear una organización nueva <Icon name="arrow" size={15} /></button>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

// Panel izquierdo de ingreso y registro. En el registro muestra la excavadora en 3D.
function AuthStory({ withExcavator = false }: { withExcavator?: boolean }) {
  return (
    <aside className="auth-story">
      <Brand />
      <div className="auth-story-content">
        <p className="eyebrow">COMPRAS Y VENTAS, SIN SUPOSICIONES</p>
        <h1>Construye acuerdos con más confianza.</h1>
        <p>Compara oportunidades, entiende cada recomendación y toma mejores decisiones con información clara.</p>
        {withExcavator && <Excavator3D />}
        <div className="auth-proof">
          <span><Icon name="shield" /></span>
          <div><strong>IA explicable y segura</strong><p>Siempre sabrás por qué recomendamos una opción.</p></div>
        </div>
      </div>
      <small>ProvCons · Plataforma B2B para el sector construcción</small>
    </aside>
  );
}

type Plan = (typeof PLANS)[number];

const EMPTY_FORM = { organization_name: "", full_name: "", tax_id: "", email: "", confirm_email: "", password: "", confirm_password: "" };
type FormField = keyof typeof EMPTY_FORM;

// Casillas del Figma: el nombre del campo va escrito dentro de cada una
const FIELDS: { name: FormField; placeholder: string; type?: string; autoComplete?: string }[] = [
  { name: "organization_name", placeholder: "Nombre de la empresa", autoComplete: "organization" },
  { name: "full_name", placeholder: "Tu nombre completo", autoComplete: "name" },
  { name: "tax_id", placeholder: "NIT" },
  { name: "email", placeholder: "Correo", type: "email", autoComplete: "email" },
  { name: "confirm_email", placeholder: "Confirmar correo", type: "email", autoComplete: "off" },
  { name: "password", placeholder: "Contraseña", type: "password", autoComplete: "new-password" },
  { name: "confirm_password", placeholder: "Confirmar contraseña", type: "password", autoComplete: "new-password" },
];

// Una tarjeta del registro con su propio formulario y botón
function RegisterCard({ plan, sending, disabled, error, onSubmit }: {
  plan: Plan; sending: boolean; disabled: boolean; error: string;
  onSubmit: (data: Omit<SignupPayload, "organization_type">) => void;
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [check, setCheck] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const empty = FIELDS.find((f) => !form[f.name].trim());
    if (empty) return setCheck(`Completa: ${empty.placeholder}.`);
    if (form.email.trim().toLowerCase() !== form.confirm_email.trim().toLowerCase()) return setCheck("Los correos no coinciden.");
    if (form.password.length < 8) return setCheck("La contraseña debe tener al menos 8 caracteres.");
    if (form.password !== form.confirm_password) return setCheck("Las contraseñas no coinciden.");
    setCheck("");
    onSubmit({
      organization_name: form.organization_name.trim(), full_name: form.full_name.trim(),
      tax_id: form.tax_id.trim(), email: form.email.trim(), password: form.password,
    });
  };

  const message = check || error;
  return (
    <form className="plan-card" onSubmit={submit} noValidate aria-label={`Registro de ${plan.title}`}>
      <p className="plan-tag">{plan.tag}</p>
      <h3>{plan.title}</h3>
      <span className="plan-chip"><Icon name={plan.icon} size={14} /> {plan.chip}</span>
      <div className="plan-fields">
        {FIELDS.map((f) => (
          <input
            key={f.name}
            type={f.type ?? "text"}
            placeholder={f.placeholder}
            aria-label={f.placeholder}
            autoComplete={f.autoComplete}
            value={form[f.name]}
            onChange={(e) => setForm((v) => ({ ...v, [f.name]: e.target.value }))}
            disabled={disabled}
          />
        ))}
      </div>
      {message && <p className="plan-error" role="alert">{message}</p>}
      <button type="submit" className="plan-button" disabled={disabled}>{sending ? "Registrando..." : `Registrarme como ${plan.title.toLowerCase()}`}</button>
      <p className="plan-section"><Icon name="spark" size={18} /> Con IA de ProvCons</p>
      <ul className="plan-features">
        {plan.features.map((feature) => <li key={feature}><Icon name="check" size={16} /> {feature}</li>)}
      </ul>
    </form>
  );
}
