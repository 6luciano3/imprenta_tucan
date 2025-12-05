from dataclasses import dataclass


@dataclass
class PedidoDTO:
    id: int
    cliente: str
    producto: str
    tiraje: int
    total: float
    estado: str
