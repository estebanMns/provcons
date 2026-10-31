from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Material(_message.Message):
    __slots__ = ("id", "name")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ...) -> None: ...

class SimilarityRequest(_message.Message):
    __slots__ = ("items", "products")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Material]
    products: _containers.RepeatedCompositeFieldContainer[Material]
    def __init__(self, items: _Optional[_Iterable[_Union[Material, _Mapping]]] = ..., products: _Optional[_Iterable[_Union[Material, _Mapping]]] = ...) -> None: ...

class PairScore(_message.Message):
    __slots__ = ("item_id", "product_id", "similarity", "specs_conflict")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    SIMILARITY_FIELD_NUMBER: _ClassVar[int]
    SPECS_CONFLICT_FIELD_NUMBER: _ClassVar[int]
    item_id: int
    product_id: int
    similarity: float
    specs_conflict: bool
    def __init__(self, item_id: _Optional[int] = ..., product_id: _Optional[int] = ..., similarity: _Optional[float] = ..., specs_conflict: _Optional[bool] = ...) -> None: ...

class SimilarityResponse(_message.Message):
    __slots__ = ("pairs",)
    PAIRS_FIELD_NUMBER: _ClassVar[int]
    pairs: _containers.RepeatedCompositeFieldContainer[PairScore]
    def __init__(self, pairs: _Optional[_Iterable[_Union[PairScore, _Mapping]]] = ...) -> None: ...
