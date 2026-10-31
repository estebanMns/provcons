# Regenera el código Python del contrato gRPC (proto/matching_engine.proto).
# Requiere: pip install -r requirements-dev.txt
# El código generado se sube al repositorio para que el despliegue no tenga
# que compilar el .proto.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "app\grpc_engine\generated"
New-Item -ItemType Directory -Force $out | Out-Null

& (Join-Path $root ".venv\Scripts\python.exe") -m grpc_tools.protoc `
    -I (Join-Path $root "proto") `
    --python_out=$out --pyi_out=$out --grpc_python_out=$out `
    (Join-Path $root "proto\matching_engine.proto")

# protoc genera "import matching_engine_pb2" (absoluto); dentro del paquete
# debe ser relativo para que funcione como app.grpc_engine.generated.
$grpcFile = Join-Path $out "matching_engine_pb2_grpc.py"
(Get-Content $grpcFile -Raw) -replace '(?m)^import matching_engine_pb2', 'from . import matching_engine_pb2' |
    Set-Content $grpcFile -Encoding utf8 -NoNewline
"Código generado en $out"
