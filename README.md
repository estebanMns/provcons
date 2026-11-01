# ProvCons

Plataforma B2B para el sector construcción que conecta constructoras con proveedores de materiales.

- **Constructora:** sube su lista de materiales en PDF, Excel o foto. La app compara proveedores por precio, stock y cobertura, le recomienda a quién comprarle, **predice qué pasará a futuro con cada opción** (si el proveedor cumplirá, cuándo llegará el pedido y cuánto costará de verdad) y le permite crear la orden.
- **Proveedor:** sube su catálogo en el mismo formato. Ve las oportunidades de venta en las cotizaciones abiertas y confirma y despacha las órdenes que recibe.

## Contenido

1. [Cómo funciona](#cómo-funciona)
2. [Arquitectura](#arquitectura)
3. [Predicción con IA](#predicción-con-ia)
4. [Principios SOLID, patrones y buenas prácticas](#principios-solid-patrones-y-buenas-prácticas)
5. [gRPC: el motor de comparación](#grpc-el-motor-de-comparación)
6. [Event loop y concurrencia](#event-loop-y-concurrencia)
7. [Métricas de rendimiento](#métricas-de-rendimiento)
8. [Patrones de rendering](#patrones-de-rendering)
9. [Web Workers](#web-workers)
10. [Correr el proyecto en local](#correr-el-proyecto-en-local)
11. [Pruebas](#pruebas)

## Cómo funciona

1. **Lectura con IA (Gemini).** Extrae materiales, cantidades, unidades y precios de cada archivo. Los Excel se convierten a texto antes de enviarlos.
2. **Comparación de materiales.** Compara nombres sin importar mayúsculas, tildes ni plurales, y respeta las medidas: una varilla de 1/2" no es una de 3/8". Este cálculo lo hace un microservicio gRPC. Después, una revisión con IA encuentra sinónimos ("acero de refuerzo" = "varilla corrugada") y descarta lo que solo se parece en el nombre.
3. **Comparación de proveedores.** Califica cada oferta por compatibilidad, disponibilidad y precio frente a los demás proveedores. Arma un ranking, una recomendación y la "mejor combinación" (comprar cada material al más conveniente).
4. **Predicción a futuro.** Para cada opción de compra estima la probabilidad de que el proveedor cumpla, los días de entrega y el costo esperado contando el riesgo. Gemini lo explica en lenguaje claro. Ver [Predicción con IA](#predicción-con-ia).
5. **Cuentas.** Cada organización tiene sus usuarios. Si alguien olvida su contraseña, recibe un correo (Resend) con un enlace que vence en 30 minutos y sirve una sola vez.
6. **Órdenes.** Se crea una orden por proveedor, que guarda los precios del momento de la compra. El proveedor confirma, despacha y entrega. Todo queda en el historial de actividad.

## Arquitectura

Son tres capas más un servicio externo. Todo se publica con planes gratuitos; ver [DEPLOY.md](DEPLOY.md).

```
                 HTTPS · REST/JSON · sesión con JWT
 Navegador ───────────────────────────────────────────────►  FastAPI (Render)
 Next.js (Vercel)                                              │   │   │
  · SSG + ISR  (página pública)                                │   │   └── gRPC (localhost:50051) ──► Motor de comparación
  · CSR        (pantallas privadas)                            │   │                                   (proceso aparte, mismo contenedor)
  · Web Workers (archivos, CSV)                                │   └────── HTTPS ──► Google Gemini (IA)
  · Web Vitals ──► /api/metrics                                └────────── asyncpg ──► PostgreSQL (AWS RDS)
```

| Parte | Stack |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| API | Python 3.11, FastAPI (asyncio, uvloop en Linux), SQLAlchemy 2 async, Alembic |
| Microservicio | gRPC (`grpcio`, `grpc.aio`) con contrato Protocol Buffers ([`proto/matching_engine.proto`](proto/matching_engine.proto)) |
| Datos | PostgreSQL en AWS RDS |
| IA | Google Gemini (`google-genai`) |
| Observabilidad | `prometheus-client` (`/metrics`) y Web Vitals |

**El backend es un monolito modular más un microservicio.** La API es un solo servicio desplegable, dividido en módulos por tema. Cada módulo tiene las mismas capas:

```
app/
  core/            configuración, seguridad, auditoría, métricas, excepciones de dominio
  infrastructure/  adaptadores externos: cliente de IA, cliente gRPC, lectura de archivos
  grpc_engine/     microservicio gRPC (servidor + código generado del .proto)
  modules/
    users/         registro, login y sesión
    documents_ai/  inventario de proveedores
    matching/      cotizaciones, comparación de materiales y de proveedores
    transactions/  órdenes de compra
    audit/         historial de actividad
    dashboard/     indicadores del resumen
    observability/ métricas de rendimiento y Web Vitals
    public/        cifras públicas para la página de presentación
  └─ cada módulo:  router.py → service.py → repository.py → models.py  (+ schemas.py)
proto/             contrato gRPC
alembic/           migraciones versionadas de la base de datos
tests/             pruebas automáticas (pytest)
provcons-frontend/ aplicación Next.js (src/app, src/components, src/lib, src/workers)
```

## Predicción con IA

La comparación dice quién es más barato **hoy**. La predicción responde qué le pasará a la constructora **después** de elegir: si el proveedor va a cumplir, cuándo llegará el pedido y cuánto terminará costando. Se ve en el panel "Predicción a futuro" de cada comparación y la entrega `GET /api/matching/quotations/{id}/forecast`.

**Cómo se reparten el trabajo la estadística y la IA:**
- **Las cifras las calcula el backend** ([`predictors.py`](app/modules/forecast/predictors.py)) con el historial real de órdenes. Son deterministas y verificables: los mismos datos dan siempre el mismo resultado.
- **Gemini solo redacta** ([`narrator.py`](app/modules/forecast/narrator.py)): recibe las cifras ya calculadas y explica qué pasará con cada opción, sus riesgos y un consejo. La pantalla muestra siempre los números del backend, así que una cifra inventada por el modelo nunca llega al usuario.
- **Sin IA también funciona:** si no hay API key o Gemini falla, `TemplateNarrator` arma la explicación con plantillas.

**Qué se predice y cómo:**

| Predicción | Cálculo | Fuente |
|---|---|---|
| Probabilidad de que el proveedor cumpla | `(entregadas + 3) / (entregadas + rechazadas + 4)`: un prior Beta, para que un proveedor nuevo arranque en 75 % y no en 0 % ni 100 % | Órdenes y rechazos (`audit_logs`, acción `order.rejected`) |
| Confianza | `baja` con menos de 3 órdenes cerradas, `media` con menos de 10, `alta` con 10 o más | Órdenes cerradas |
| Días de entrega | Mediana y rango p25–p75 | Tiempo entre la creación de la orden y `order.entregada` |
| Tendencia de precio | Recta de mínimos cuadrados sobre los precios normalizados por material, en % cada 30 días | Precios congelados en `order_items` del último año |
| Faltantes | Lo que el proveedor no tiene en stock se compra al siguiente más barato | Stock de la comparación |
| **Costo esperado** | `costo hoy + faltantes + (1 − p) × sobrecosto de recomprar de urgencia al alternativo (+10 %)` | Todo lo anterior |
| Escenarios | Optimista (cumple), probable (costo esperado) y pesimista (falla y se recompra, p75 + 3 días) | Todo lo anterior |

Cada "opción" es un plan para comprar el pedido completo. Elegir un proveedor significa comprarle lo que tiene y completar lo que le falta con el más barato de los demás, así que todas las opciones son comparables. También se evalúa la mejor combinación. La **mejor opción a futuro** es la de menor costo esperado. Si no coincide con la recomendación de hoy, el panel explica por qué: por ejemplo, un proveedor 10 % más barato que rechaza la mitad de sus órdenes termina costando más.

**Por qué estadística más LLM y no un modelo de ML entrenado:** hoy hay poco historial, y un modelo entrenado necesitaría datos que no existen o datos sintéticos. Además, el plan gratuito de Render tiene 512 MB de memoria. Este enfoque es explicable, se puede probar y mejora solo: la confianza sube a medida que se cierran órdenes. Si algún día hay datos suficientes, basta con otra implementación de `ForecastModel`.

**Cuota gratuita de Gemini:** la predicción se guarda 15 minutos en una caché en memoria ([`service.py`](app/modules/forecast/service.py)). Reabrir la misma comparación no vuelve a llamar a la IA, y si las ofertas cambian la caché se invalida sola.

## Principios SOLID, patrones y buenas prácticas

### SOLID

| Principio | Dónde está | Cómo se aplica |
|---|---|---|
| **S** — Responsabilidad única | Capas de cada módulo (`app/modules/*/router.py`, `service.py`, `repository.py`) | El router solo traduce HTTP, el service aplica las reglas de negocio y el repository solo habla con la base. Cada capa cambia por un único motivo. |
| **O** — Abierto/cerrado | [`scoring.py`](app/modules/matching/scoring.py) (`ScoringStrategy`), [`matchers.py`](app/modules/matching/matchers.py) (`MaterialMatcher`), [`predictors.py`](app/modules/forecast/predictors.py) (`ForecastModel`) | Para cambiar el algoritmo de puntaje, la forma de comparar o el modelo de predicción se agrega una implementación nueva; los servicios no se tocan. |
| **L** — Sustitución de Liskov | `GrpcMaterialMatcher` y `LocalMaterialMatcher` | Son intercambiables y dan el mismo resultado: la prueba [`test_grpc_engine.py`](tests/matching/test_grpc_engine.py) lo verifica. |
| **I** — Segregación de interfaces | Protocolos pequeños (`MaterialMatcher.compute`, `ScoringStrategy.calculate`) | Cada componente depende solo del método que usa, no de clases grandes. |
| **D** — Inversión de dependencias | `MatchingService`, `OrderService`, `InventoryService` y `ForecastService` reciben repositorios, matcher, IA y auditoría por constructor | Las reglas de negocio no dependen de gRPC, de Gemini ni de la base de datos concretos. Por eso las pruebas usan versiones falsas. |

### Patrones de diseño

| Patrón | Dónde está | Para qué |
|---|---|---|
| Repository | `app/modules/*/repository.py` | Aísla el acceso a datos de las reglas de negocio. |
| Strategy | `ScoringStrategy` → `ComparativeScoringStrategy`; `ForecastModel` → `StatisticalForecastModel`; `EmailSender` → Resend o consola | Algoritmos de puntaje y de predicción, y formas de enviar correo, intercambiables. |
| Adapter | [`ai_client.py`](app/infrastructure/ai_client.py), [`matching_engine_client.py`](app/infrastructure/matching_engine_client.py), `AIForecastNarrator`, `ResendEmailSender` ([`email.py`](app/infrastructure/email.py)) | Ocultan las APIs de Gemini y de gRPC detrás de interfaces propias. |
| Factory | `get_matching_service`, `get_forecast_service`, `get_order_service` (routers) | Arman cada servicio con sus dependencias concretas. |
| Facade | [`DashboardService`](app/modules/dashboard/service.py) | Una sola entrada para muchos cálculos del resumen. |
| Circuit breaker simple / respaldo | `ResilientMatcher`, `AIForecastNarrator` → `TemplateNarrator` | Si el motor gRPC no responde, la comparación se calcula localmente; si Gemini falla, la predicción se explica con plantillas. La app sigue funcionando. |
| Singleton | `metrics` ([`metrics.py`](app/core/metrics.py)), caché de predicciones | Un único registro de métricas y una única caché por proceso. |
| Chain of Responsibility (middleware) | [`main.py`](app/main.py): CORS y métricas | Cada petición pasa por una cadena de procesadores. |
| Observer (callback) | `ResilientMatcher(on_fallback=...)` | Notifica a las métricas cuando se usa el respaldo, sin acoplarse a ellas. |
| DTO | `app/modules/*/schemas.py` (Pydantic) | Validan y documentan lo que entra y sale de la API. |
| Excepciones de dominio | [`exceptions.py`](app/core/exceptions.py) | Los services lanzan errores de negocio; se traducen a HTTP en un solo lugar. |

### Buenas prácticas

- **Pruebas sin dependencias externas.** Las pruebas (`tests/`) usan repositorios y clientes de IA falsos; la de gRPC levanta un servidor real en un puerto libre.
- **Secretos solo en variables de entorno.** Ver `.env.example`; `.env` está en `.gitignore`.
- **Migraciones de base de datos versionadas** con Alembic.
- **DRY.** Por ejemplo `lib/format.ts`, `lib/orderStatus.ts` y un único método de reintentos en `AIClient`.
- **YAGNI.** Se eliminó el código muerto y los datos de ejemplo.
- **Reglas de hooks de React:** ESLint sin errores.
- **Commits pequeños** y con mensaje descriptivo.

## gRPC: el motor de comparación

El cálculo más pesado del sistema es comparar cada material pedido contra cada producto del catálogo (materiales × productos). Es lógica pura, así que vive en un **microservicio gRPC** aparte.

- **Contrato:** [`proto/matching_engine.proto`](proto/matching_engine.proto) define `MatchingEngine.ComputeSimilarities`. El código Python se genera con `scripts/gen_proto.ps1` y está incluido en el repositorio.
- **Servidor:** [`app/grpc_engine/server.py`](app/grpc_engine/server.py), con `grpc.aio`. Implementa el *health check* estándar de gRPC (`grpc.health.v1`).
- **Cliente:** `GrpcMaterialMatcher` usa un canal reutilizable con *deadline* (tiempo límite).
- **Respaldo:** `ResilientMatcher` calcula localmente si el motor no responde.
- **Despliegue gratis:** en Render solo hay un servicio, así que [`scripts/start.sh`](scripts/start.sh) arranca el motor y la API como dos procesos en el mismo contenedor, comunicados por `localhost`. `/health` informa el estado del motor.
- **Configuración:** `MATCHING_ENGINE_MODE` acepta `grpc` (por defecto) o `local`.

En local se arranca con `python -m app.grpc_engine.server`. Si no está corriendo, la API funciona igual gracias al respaldo local.

## Event loop y concurrencia

FastAPI corre sobre el **event loop de asyncio** (uvloop en Linux): un solo hilo atiende muchas peticiones a la vez, porque mientras una espera la base de datos, la IA o gRPC, el loop atiende otra.

- **Todo lo de entrada/salida es asíncrono:** PostgreSQL con `asyncpg`, Gemini con `client.aio` y gRPC con `grpc.aio`.
- **El trabajo de CPU sale del loop:** la lectura de Excel y la comparación local van en `asyncio.to_thread`, y el servidor gRPC usa `run_in_executor`.
- **Tiempos límite:** `asyncio.wait_for` por cada intento a Gemini y *deadline* en gRPC. Las esperas entre reintentos usan `asyncio.sleep`, que no bloquea.
- **Medición del retraso del event loop:** una tarea de fondo creada en el `lifespan` ([`monitor_event_loop_lag`](app/core/metrics.py)) duerme 0,5 s y mide cuánto se atrasa. Si algo bloquea el loop, el retraso sube. Una prueba bloquea el loop a propósito para verificarlo.

## Métricas de rendimiento

- **`GET /metrics`** (formato Prometheus) incluye:
  - Duración de cada petición por plantilla de ruta.
  - Llamadas a Gemini y al motor gRPC.
  - Retraso del event loop.
  - Respaldos locales del motor.
  - Web Vitals.
- **`GET /api/metrics/summary`** entrega p50, p95 y p99 calculados sobre una ventana en memoria. Requiere sesión.
- **Web Vitals:** el navegador mide LCP, INP, CLS, FCP y TTFB con `useReportWebVitals` y los envía a `POST /api/metrics/web-vitals`.
- **Pantalla "Rendimiento"** en la app: todo lo anterior en vivo, con los Web Vitals evaluados contra los umbrales de Google (bueno, mejorable o malo).

## Patrones de rendering

| Patrón | Dónde | Por qué |
|---|---|---|
| **SSG** (generación estática) | `/` ([`src/app/page.tsx`](provcons-frontend/src/app/page.tsx)) y `/login` | El HTML se genera en el build y carga al instante, sin esperar al servidor. |
| **ISR** (regeneración incremental) | `/` con `revalidate = 300` | Las cifras públicas de la plataforma se actualizan cada 5 minutos sin volver a desplegar. |
| **CSR** (renderizado en el cliente) | Pantallas privadas (`src/app/(app)/*`) | Los datos son de cada usuario y la sesión vive en el navegador, así que no tiene sentido renderizarlas en el servidor. |
| Protección en el servidor | [`src/proxy.ts`](provcons-frontend/src/proxy.ts) | Redirige al login antes de renderizar si no hay sesión. |

`next build` lo confirma: `○ /  Revalidate 5m`.

## Web Workers

Las tareas pesadas del navegador corren en hilos aparte ([`src/workers`](provcons-frontend/src/workers)), así la pantalla no se congela:

- **`file-check.worker.ts`:** antes de subir un archivo revisa su tipo real por la firma de bytes (un `.pdf` que en realidad es texto se rechaza antes de gastar una llamada a la IA) y el tamaño. También calcula su SHA-256, para avisar si ya se subió el mismo archivo.
- **`csv.worker.ts`:** genera el CSV del historial de actividad.
- **[`src/lib/workers.ts`](provcons-frontend/src/lib/workers.ts):** crea cada worker con `new URL(..., import.meta.url)`, para que Next lo empaquete aparte, y lo termina al acabar.

## Correr el proyecto en local

Requisitos: Python 3.11, Node.js 20 o superior y una base PostgreSQL.

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env               # y completa los valores
alembic upgrade head
python -m app.grpc_engine.server     # terminal 1: motor gRPC (opcional, hay respaldo local)
uvicorn app.main:app --reload        # terminal 2: API en http://localhost:8000

# Frontend (terminal 3)
cd provcons-frontend
npm install
npm run dev                          # http://localhost:3000
```

Con `ENVIRONMENT=development`, la documentación interactiva de la API está en http://localhost:8000/docs.

**Recuperación de contraseña:** con `RESEND_API_KEY` se envía un correo real. Sin ella, en desarrollo, el enlace aparece en la terminal del backend. Un administrador también puede restablecerla directamente:

```powershell
.\.venv\Scripts\python.exe scriptseset_password.py correo@empresa.com
```

Detalles y limitaciones de Resend sin dominio propio en [DEPLOY.md](DEPLOY.md#correo-de-recuperación-de-contraseña-resend).

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q          # backend (no necesita base de datos ni IA)
cd provcons-frontend; npx tsc --noEmit; npx eslint src; npx next build
```

Para regenerar el código gRPC después de cambiar el `.proto`: `pip install -r requirements-dev.txt` y luego `scripts/gen_proto.ps1`.
