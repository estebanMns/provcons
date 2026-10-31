"""Cliente gRPC del motor de comparación (adaptador de MaterialMatcher)."""

import asyncio

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from app.grpc_engine.generated import matching_engine_pb2 as pb
from app.grpc_engine.generated import matching_engine_pb2_grpc as pb_grpc
from app.modules.matching.matchers import NamedItem, PairScore, Similarities

_MAX_MESSAGE_BYTES = 16 * 1024 * 1024


class GrpcMaterialMatcher:
    """Llama al microservicio por gRPC. El canal se reutiliza entre llamadas
    (abrir uno por petición sería lento) y se recrea si cambia el event loop,
    porque un canal grpc.aio queda atado al loop en que se creó."""

    def __init__(self, address: str, timeout_seconds: float = 10.0):
        self.address = address
        self.timeout_seconds = timeout_seconds
        self._channel: grpc.aio.Channel | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _stub(self) -> pb_grpc.MatchingEngineStub:
        loop = asyncio.get_running_loop()
        if self._channel is None or self._loop is not loop:
            self._channel = grpc.aio.insecure_channel(self.address, options=[
                ("grpc.max_receive_message_length", _MAX_MESSAGE_BYTES),
                ("grpc.max_send_message_length", _MAX_MESSAGE_BYTES),
            ])
            self._loop = loop
        return pb_grpc.MatchingEngineStub(self._channel)

    async def compute(self, items: list[NamedItem], products: list[NamedItem]) -> Similarities:
        request = pb.SimilarityRequest(
            items=[pb.Material(id=i, name=n) for i, n in items],
            products=[pb.Material(id=i, name=n) for i, n in products],
        )
        # timeout = deadline de gRPC: si el motor no responde a tiempo la
        # llamada falla y ResilientMatcher calcula localmente.
        response = await self._stub().ComputeSimilarities(request, timeout=self.timeout_seconds)
        return {
            (p.item_id, p.product_id): PairScore(similarity=round(p.similarity, 3), specs_conflict=p.specs_conflict)
            for p in response.pairs
        }

    async def health(self) -> str:
        """Estado según el health check estándar de gRPC: SERVING, NOT_SERVING
        o "unreachable" si no responde."""
        try:
            self._stub()  # asegura el canal en este loop
            response = await health_pb2_grpc.HealthStub(self._channel).Check(
                health_pb2.HealthCheckRequest(service="provcons.matching.v1.MatchingEngine"), timeout=2,
            )
            return health_pb2.HealthCheckResponse.ServingStatus.Name(response.status)
        except Exception:
            return "unreachable"

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
