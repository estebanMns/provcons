# Publicar ProvCons

- **Backend (FastAPI):** Render, configurado en [`render.yaml`](render.yaml).
- **Frontend (Next.js):** Vercel.
- **Base de datos:** AWS RDS PostgreSQL (us-east-2), la misma que se usa en desarrollo.

Los secretos se cargan en los paneles de Render y Vercel, nunca en el repositorio.

## 1. Backend en Render

1. En Render: **New → Blueprint** y elige el repositorio `estebanMns/provcons`. Render lee `render.yaml` y crea el servicio `provcons-api` en la región Ohio.
2. Cuando pida las variables marcadas como secretas, completa:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | La misma del `.env` local. Debe empezar con `postgresql+asyncpg://` |
   | `SECRET_KEY` | Una clave **nueva**, distinta de la local: `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `GEMINI_API_KEY` | La misma del `.env` local |

3. Crea el servicio y espera a que el deploy quede en verde.
4. Copia la URL del servicio, por ejemplo `https://provcons-api.onrender.com`. Para comprobar que responde, abre `https://provcons-api.onrender.com/health`: debe mostrar `{"status":"ok"}`.

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

`render.yaml` trae `CORS_ORIGINS='["https://provcons.vercel.app"]'`. Si Vercel te asignó otra URL, cámbiala en **Render → Environment → `CORS_ORIGINS`**, en el mismo formato de lista JSON, y guarda. Render se reinicia solo.

## Migraciones de base de datos

Render no corre migraciones automáticamente en el plan gratuito. Cuando haya una migración nueva, córrela desde tu computador, con el `.env` apuntando a RDS:

```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

## Avisos

- **El backend se duerme:** en el plan gratuito de Render se apaga tras 15 minutos sin uso. La primera petición después tarda unos 50 segundos; las siguientes son normales.
- **`/docs` está apagado en producción:** con `ENVIRONMENT=production` no se publica la documentación de la API. Es intencional.
- **Despliegue automático:** cada push a `main` vuelve a desplegar el backend y el frontend.
