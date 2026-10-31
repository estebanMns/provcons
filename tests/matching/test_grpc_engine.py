"""El microservicio gRPC real (servidor + cliente) contra el cálculo local."""
import asyncio

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from app.grpc_engine.server import SERVICE_NAME, build_server
from app.infrastructure.matching_engine_client import GrpcMaterialMatcher
from app.modules.matching.matchers import LocalMaterialMatcher, ResilientMatcher

ITEMS = [(1, "cemento gris"), (2, 'varilla corrugada 3/8"'), (3, "malla electrosoldada")]
PRODUCTS = [
    (10, "Cemento gris x 50kg"), (11, 'Varilla corrugada 3/8" x 6m'),
    (12, "varilla 1/2 x 6m"), (13, "Arena de rio (lavada)"),
]


async def _with_server(test):
    server, port = build_server("127.0.0.1:0")  # puerto libre cualquiera
    await server.start()
    await server.health_servicer.set(SERVICE_NAME, health_pb2.HealthCheckResponse.SERVING)
    try:
        return await test(f"127.0.0.1:{port}")
    finally:
        await server.stop(grace=None)


def test_grpc_da_el_mismo_resultado_que_el_calculo_local():
    async def test(address):
        matcher = GrpcMaterialMatcher(address, timeout_seconds=5)
        try:
            return await matcher.compute(ITEMS, PRODUCTS)
        finally:
            await matcher.close()

    remote = asyncio.run(_with_server(test))
    local = asyncio.run(LocalMaterialMatcher().compute(ITEMS, PRODUCTS))

    assert remote == local
    assert remote[(1, 10)].similarity == 1.0
    assert remote[(2, 12)].specs_conflict is True  # 3/8" vs 1/2"
    assert (3, 10) not in remote  # sin relación: no viaja en la respuesta


def test_health_check_estandar_de_grpc():
    async def test(address):
        async with grpc.aio.insecure_channel(address) as channel:
            response = await health_pb2_grpc.HealthStub(channel).Check(
                health_pb2.HealthCheckRequest(service=SERVICE_NAME), timeout=5,
            )
            return response.status

    assert asyncio.run(_with_server(test)) == health_pb2.HealthCheckResponse.SERVING


def test_si_el_motor_no_responde_se_calcula_localmente():
    fallbacks = []
    matcher = ResilientMatcher(
        primary=GrpcMaterialMatcher("127.0.0.1:1", timeout_seconds=1),  # nadie escucha ahí
        fallback=LocalMaterialMatcher(),
        on_fallback=lambda: fallbacks.append(1),
    )
    result = asyncio.run(matcher.compute(ITEMS, PRODUCTS))
    assert result == asyncio.run(LocalMaterialMatcher().compute(ITEMS, PRODUCTS))
    assert fallbacks == [1]
