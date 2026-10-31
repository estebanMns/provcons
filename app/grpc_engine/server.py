"""Microservicio gRPC: motor de comparación de materiales.

Corre como un proceso aparte de la API (en Render, dentro del mismo
contenedor; ver scripts/start.sh). Uso local:

    python -m app.grpc_engine.server            # escucha en 127.0.0.1:50051
"""

import asyncio
import logging
import os
import signal

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from app.grpc_engine.generated import matching_engine_pb2 as pb
from app.grpc_engine.generated import matching_engine_pb2_grpc as pb_grpc
from app.modules.matching.matchers import compute_similarities

logger = logging.getLogger("provcons.grpc_engine")

SERVICE_NAME = "provcons.matching.v1.MatchingEngine"
# Catálogos grandes producen mensajes grandes; 16 MB deja margen de sobra
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


class MatchingEngineServicer(pb_grpc.MatchingEngineServicer):
    async def ComputeSimilarities(self, request: pb.SimilarityRequest, context) -> pb.SimilarityResponse:
        items = [(m.id, m.name) for m in request.items]
        products = [(m.id, m.name) for m in request.products]
        # El cálculo es CPU puro: se manda a un hilo para que el event loop del
        # servidor siga respondiendo otras llamadas (p. ej. el health check).
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, compute_similarities, items, products)
        logger.info("ComputeSimilarities: %s x %s -> %s pares", len(items), len(products), len(scores))
        return pb.SimilarityResponse(pairs=[
            pb.PairScore(item_id=item_id, product_id=product_id, similarity=s.similarity, specs_conflict=s.specs_conflict)
            for (item_id, product_id), s in scores.items()
        ])


def build_server(address: str) -> tuple[grpc.aio.Server, int]:
    """Crea el servidor con el servicio y su health check. Devuelve el puerto
    real (útil en pruebas con puerto 0 = cualquiera libre)."""
    server = grpc.aio.server(options=[
        ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
        ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
    ])
    pb_grpc.add_MatchingEngineServicer_to_server(MatchingEngineServicer(), server)

    health_servicer = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    port = server.add_insecure_port(address)
    server.health_servicer = health_servicer  # para marcarlo SERVING al arrancar
    return server, port


async def serve(address: str) -> None:
    server, port = build_server(address)
    await server.start()
    await server.health_servicer.set(SERVICE_NAME, health_pb2.HealthCheckResponse.SERVING)
    await server.health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    logger.info("Motor de comparación gRPC escuchando en %s (puerto %s)", address, port)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows: Ctrl+C llega como KeyboardInterrupt
            pass
    try:
        await stop.wait()
    finally:
        await server.stop(grace=3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    address = os.getenv("MATCHING_ENGINE_LISTEN", "127.0.0.1:50051")
    try:
        asyncio.run(serve(address))
    except KeyboardInterrupt:
        pass
