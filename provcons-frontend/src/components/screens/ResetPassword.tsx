"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Brand } from "@/components/screens/Auth";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { resetPassword } from "@/lib/api";

const MIN_LENGTH = 8;
const MAX_LENGTH = 72;

// Página a la que lleva el enlace del correo: /restablecer?token=...
export function ResetPassword() {
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const submit = async () => {
    setError("");
    if (password.length < MIN_LENGTH || password.length > MAX_LENGTH) {
      setError(`La contraseña debe tener entre ${MIN_LENGTH} y ${MAX_LENGTH} caracteres.`);
      return;
    }
    if (password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      setDone(await resetPassword(token, password));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <aside className="auth-story">
        <Brand />
        <div className="auth-story-content">
          <p className="eyebrow">RECUPERAR ACCESO</p>
          <h1>Crea una contraseña nueva.</h1>
          <p>El enlace que recibiste sirve una sola vez y vence en 30 minutos. Después de cambiarla, ingresa con la nueva.</p>
        </div>
        <small>ProvCons · Plataforma B2B para el sector construcción</small>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <Link className="auth-back" href="/login"><Icon name="arrow" size={16} /> Volver al ingreso</Link>
          {done ? (
            <>
              <p className="eyebrow">LISTO</p>
              <h2>Contraseña actualizada</h2>
              <div className="auth-notice" role="status"><Icon name="check" size={16} /> <span>{done}</span></div>
              <Link href="/login" className="btn btn-primary btn-wide">Ir a ingresar</Link>
            </>
          ) : !token ? (
            <>
              <p className="eyebrow">ENLACE INCOMPLETO</p>
              <h2>Falta el código del enlace</h2>
              <p>Abre el enlace completo que te llegó al correo, o pide uno nuevo desde &ldquo;Olvidé mi contraseña&rdquo;.</p>
              <Link href="/login" className="btn btn-primary btn-wide">Pedir un enlace nuevo</Link>
            </>
          ) : (
            <>
              <p className="eyebrow">NUEVA CONTRASEÑA</p>
              <h2>Elige tu nueva contraseña</h2>
              <p>Usa al menos {MIN_LENGTH} caracteres.</p>
              {error && (
                <div style={{ color: "var(--danger)", marginBottom: "1rem", fontSize: 12 }}>
                  {error}{" "}
                  {/(venció|usó|no es válido)/.test(error) && <Link href="/login" style={{ color: "var(--brand)", fontWeight: 700 }}>Pedir otro enlace</Link>}
                </div>
              )}
              <label>Nueva contraseña<div className="password-field"><input type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} disabled={loading} autoComplete="new-password" autoFocus /><button type="button" onClick={() => setShow((v) => !v)}>{show ? "Ocultar" : "Mostrar"}</button></div></label>
              <label>Repite la contraseña<input type={show ? "text" : "password"} value={confirm} onChange={(e) => setConfirm(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} disabled={loading} autoComplete="new-password" /></label>
              <Button wide onClick={submit} disabled={loading}>{loading ? "Guardando..." : "Guardar contraseña"}</Button>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
