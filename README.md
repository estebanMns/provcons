# ProvCons

Plataforma B2B para el sector construcción que conecta constructoras con proveedores de materiales.

- **Constructora:** sube su lista de materiales en PDF, Excel o foto. La app compara proveedores por precio, stock y cobertura, le recomienda a quién comprarle y le permite crear la orden.
- **Proveedor:** sube su catálogo en el mismo formato. Ve las oportunidades de venta en las cotizaciones abiertas y confirma y despacha las órdenes que recibe.

## Cómo funciona

1. **Lectura con IA (Gemini).** Extrae materiales, cantidades, unidades y precios de cada archivo. Los Excel se convierten a texto antes de enviarlos.
2. **Comparación de materiales.** Compara nombres sin importar mayúsculas, tildes ni plurales, y respeta las medidas: una varilla de 1/2" no es una de 3/8". Después, una revisión con IA encuentra sinónimos ("acero de refuerzo" = "varilla corrugada") y descarta lo que solo se parece en el nombre.
3. **Comparación de proveedores.** Califica cada oferta por compatibilidad, disponibilidad y precio frente a los demás proveedores. Arma un ranking, una recomendación y la "mejor combinación" (comprar cada material al más conveniente).
4. **Órdenes.** Se crea una orden por proveedor, que guarda los precios del momento de la compra. El proveedor confirma, despacha y entrega. Todo queda en el historial de actividad.

## Tecnología

| Parte | Stack |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL (AWS RDS) |
| IA | Google Gemini (`google-genai`) |
| Frontend | Next.js 16, React 19, TypeScript |
| Publicación | Render (backend) y Vercel (frontend). Ver [DEPLOY.md](DEPLOY.md) |

Estructura:

```
app/
  core/            configuración, seguridad, auditoría, excepciones
  infrastructure/  cliente de IA y lectura de archivos (PDF, imagen, Excel)
  modules/
    users/         registro, login y sesión
    documents_ai/  inventario de proveedores
    matching/      cotizaciones, comparación de materiales y de proveedores
    transactions/  órdenes de compra
    audit/         historial de actividad
    dashboard/     indicadores del resumen
alembic/           migraciones de base de datos
tests/             pruebas automáticas (pytest)
provcons-frontend/ aplicación Next.js
```

## Correr el proyecto en local

Requisitos: Python 3.11, Node.js 20 o superior y una base PostgreSQL.

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # y completa los valores
alembic upgrade head
uvicorn app.main:app --reload
```

La API queda en http://localhost:8000. La documentación interactiva está en http://localhost:8000/docs, solo con `ENVIRONMENT=development`.

### Frontend

```powershell
cd provcons-frontend
npm install
npm run dev
```

La app queda en http://localhost:3000. Sin `NEXT_PUBLIC_API_URL`, usa la API en el mismo host, en el puerto 8000.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd provcons-frontend; npx tsc --noEmit; npx next build
```

Las pruebas del backend no necesitan base de datos ni IA: usan repositorios y un cliente de IA falsos.
