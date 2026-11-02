# Publicar ProvCons

- **Backend (FastAPI):** Render, configurado en [`render.yaml`](render.yaml).
- **Frontend (Next.js):** Vercel.
- **Base de datos:** AWS RDS PostgreSQL (us-east-2), la misma que se usa en desarrollo.

Los secretos se cargan en los paneles de Render y Vercel, nunca en el repositorio.

## Costos: todo en planes gratuitos

| Pieza | Servicio y plan | Límites a tener en cuenta |
|---|---|---|
| Frontend | Vercel **Hobby** | Gratis para uso personal o académico, no comercial. |
| Backend + motor gRPC | Render **Free** (un solo servicio web) | 750 horas al mes y 512 MB de RAM. Se duerme tras 15 minutos sin uso. Los Background Workers y los servicios privados son de pago: por eso el motor gRPC corre dentro del mismo servicio (`scripts/start.sh`). |
| IA | Google Gemini, API key de AI Studio (plan gratuito) | Límite de peticiones por minuto y por día. En el plan gratuito Google puede usar los datos para mejorar sus modelos. |
| Base de datos | AWS RDS PostgreSQL `db.t4g.micro` | Gratis **solo mientras dure el plan gratuito de AWS**. Ver la sección siguiente. |

### Mantener AWS en $0

Las cuentas de AWS creadas después del 15 de julio de 2025 están en el **plan gratuito por créditos**: hasta USD 200 durante 6 meses desde que se creó la cuenta. RDS con IP pública gasta unos USD 15–20 al mes **de esos créditos**.

1. Revisa los créditos que quedan y la **fecha de fin del plan** en **AWS → Billing and Cost Management → Free Tier / Credits**. Anótala.
2. En **AWS Budgets**, crea una alerta de presupuesto de **USD 1** de costo real, para enterarte si algo empieza a cobrar.
3. Mantén la instancia en Single-AZ, con 20 GB de almacenamiento y respaldos de 1 día.
4. **Antes de que venza el plan**, muda la base a **Neon** (PostgreSQL gratis de 0,5 GB, sin vencimiento):

   ```powershell
   # Respaldo de RDS (pg_dump viene con PostgreSQL, o usa Docker: postgres:16)
   pg_dump --no-owner --no-acl -Fc "postgresql://USUARIO:CLAVE@HOST_RDS:5432/postgres" -f provcons.dump
   # Restaurar en Neon (usa la conexión directa, sin "-pooler")
   pg_restore --no-owner --no-acl -d "postgresql://USUARIO:CLAVE@HOST_NEON/neondb?sslmode=require" provcons.dump
   ```

   Después cambia `DATABASE_URL` en Render por la de Neon (con `postgresql+asyncpg://` y `?ssl=require`) y comprueba con `alembic current`.
   - Se descarta Render Postgres free, porque se borra a los 30 días.
   - Se descarta Supabase free, porque se pausa a los 7 días sin uso.

## 1. Backend en Render

1. En Render: **New → Blueprint** y elige el repositorio `estebanMns/provcons`. Render lee `render.yaml` y crea el servicio `provcons-api` en la región Ohio.
2. Cuando pida las variables marcadas como secretas, completa:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | La misma del `.env` local. Debe empezar con `postgresql+asyncpg://` |
   | `SECRET_KEY` | Una clave **nueva**, distinta de la local: `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `GEMINI_API_KEY` | La misma del `.env` local |
   | `RESEND_API_KEY` | La misma del `.env` local (recuperación de contraseña, ver más abajo) |

3. Crea el servicio y espera a que el deploy quede en verde.
4. Copia la URL del servicio, por ejemplo `https://provcons-api.onrender.com`. Para comprobar que responde, abre `https://provcons-api.onrender.com/health`: debe mostrar `{"status":"ok","matching_engine":"SERVING"}`. Si en lugar de `SERVING` dice `unreachable`, el motor gRPC no arrancó; la API funciona igual, comparando localmente, y el log de Render muestra el motivo.

El comando de inicio es `bash scripts/start.sh`: arranca el motor gRPC en segundo plano, espera a que acepte conexiones y luego inicia la API con uvloop.

## 2. Permitir que Render llegue a la base de datos (AWS)

Mientras no hagas esto, el backend arranca pero falla en cualquier consulta (timeout de conexión).

1. En Render, abre el servicio, ve a **Connect → Outbound** y copia las IPs de salida.
2. En AWS, ve a **RDS → provcons → Conectividad y seguridad** y abre el grupo de seguridad `sg-004f6ad8ca62d5cc1`.
3. En **Reglas de entrada → Editar**, agrega una regla por cada IP de Render: **PostgreSQL**, puerto **5432**, origen `IP/32`.
   - Si solo quieres probar rápido, puedes poner como origen `0.0.0.0/0`, pero cámbialo después por las IPs de Render.

## 3. Frontend en Vercel

1. En Vercel: **Add New → Project** e importa `estebanMns/provcons`.
2. En **Root Directory**, elige `provcons-frontend`. Vercel detecta Next.js solo.
3. En **Environment Variables**, agrega:

   | Variable | Valor |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://provcons-api.onrender.com/api` (la URL de Render más `/api`) |

4. Haz el deploy y copia la URL final, por ejemplo `https://provcons.vercel.app`.

## 4. Conectar los dos

`render.yaml` trae `CORS_ORIGINS='["https://provcons.vercel.app"]'` y `FRONTEND_URL=https://provcons.vercel.app`. Si Vercel te asignó otra URL, cambia las dos en **Render → Environment**: `CORS_ORIGINS` en el mismo formato de lista JSON y `FRONTEND_URL` como texto simple. `FRONTEND_URL` es a donde lleva el enlace del correo de recuperación. Guarda y Render se reinicia solo.

## Correo de recuperación de contraseña (Resend)

"Olvidé mi contraseña" envía un correo con un enlace que vence en 30 minutos y sirve una sola vez. Se usa **Resend** (gratis: 3.000 correos al mes) porque funciona por API HTTPS; el plan gratuito de Render bloquea el envío por SMTP (Gmail, Outlook).

1. Crea una cuenta en [resend.com](https://resend.com) y una **API key**. Ponla en `RESEND_API_KEY`, en el `.env` local y en Render.
2. **Sin dominio propio**, Resend solo envía desde `onboarding@resend.dev` y **solo al correo con el que creaste la cuenta**. Sirve para probar y para recuperar tu propia cuenta.
3. **Para enviar a cualquier usuario,** verifica un dominio en **Resend → Domains** (agregando los registros DNS que indica) y cambia `EMAIL_FROM` a algo como `ProvCons <no-responder@tu-dominio.com>`.
4. Si un correo no llega, el log de Render muestra el motivo que devolvió Resend. El usuario siempre ve el mismo mensaje, para no revelar qué correos están registrados.

**Restablecer una contraseña sin correo** (administrador, desde tu computador con el `.env` apuntando a la base):

```powershell
.\.venv\Scripts\python.exe scripts\reset_password.py correo@empresa.com
```

Pide la nueva contraseña dos veces sin mostrarla y queda registrada en el historial de actividad.

## Administrador de la app

La pantalla "Rendimiento" solo la ve el administrador de ProvCons. Para dártelo, desde tu computador, con el `.env` apuntando a la base:

```powershell
.\.venv\Scripts\python.exe scripts\make_admin.py tu-correo@empresa.com
```

Vuelve a cargar la página y aparece la sección "Administración". Para quitarlo, agrega `--quitar`. No se puede dar desde la web.

## Migraciones de base de datos

Render no corre migraciones automáticamente en el plan gratuito. Cuando haya una migración nueva, córrela desde tu computador, con el `.env` apuntando a RDS:

```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

## Avisos

- **El backend se duerme:** en el plan gratuito de Render se apaga tras 15 minutos sin uso. La primera petición después tarda unos 50 segundos; las siguientes son normales.
  - **Opcional, también gratis:** en [cron-job.org](https://cron-job.org) crea una tarea que llame a `https://<tu-servicio>.onrender.com/health` cada 14 minutos. Así no se duerme, y un solo servicio encendido todo el mes cabe en las 750 horas.
- **La página pública se regenera sola:** Vercel la genera estática en el build y la actualiza cada 5 minutos (ISR). Si el backend estaba dormido durante el build, las cifras aparecen como "—" hasta la siguiente regeneración.
- **Métricas:** `https://<tu-servicio>.onrender.com/metrics` (formato Prometheus) y la pantalla "Rendimiento" de la app. Las métricas viven en memoria: se reinician cuando el servicio se duerme o se vuelve a desplegar.
- **`/docs` está apagado en producción:** con `ENVIRONMENT=production` no se publica la documentación de la API. Es intencional.
- **Despliegue automático:** cada push a `main` vuelve a desplegar el backend y el frontend.
