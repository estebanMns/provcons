#!/usr/bin/env bash
# Arranque en producción (Render, plan gratuito = un solo servicio):
# el microservicio gRPC y la API corren como dos procesos en el mismo
# contenedor y se hablan por localhost.
set -euo pipefail

PORT="${PORT:-8000}"
export MATCHING_ENGINE_LISTEN="${MATCHING_ENGINE_LISTEN:-127.0.0.1:50051}"

# 1. Motor de comparación (gRPC) en segundo plano
python -m app.grpc_engine.server &
ENGINE_PID=$!

# Espera a que el motor acepte conexiones (máx. 15 s). Si no arranca, la API
# igual funciona: ResilientMatcher calcula localmente.
python - <<'EOF' || echo "Aviso: el motor gRPC no respondió a tiempo; la API usará el cálculo local"
import socket, time, os
host, port = os.environ["MATCHING_ENGINE_LISTEN"].rsplit(":", 1)
deadline = time.time() + 15
while time.time() < deadline:
    try:
        socket.create_connection((host, int(port)), timeout=1).close()
        print("Motor gRPC listo")
        break
    except OSError:
        time.sleep(0.3)
else:
    raise SystemExit(1)
EOF

# 2. API (FastAPI). uvloop: event loop más rápido, disponible en Linux.
LOOP="auto"
if python -c "import uvloop" 2>/dev/null; then LOOP="uvloop"; fi
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --loop "$LOOP" &
API_PID=$!

# Render detiene el servicio con SIGTERM: se reenvía a los dos procesos
trap 'kill -TERM "$API_PID" "$ENGINE_PID" 2>/dev/null || true' TERM INT
wait "$API_PID"
kill -TERM "$ENGINE_PID" 2>/dev/null || true
