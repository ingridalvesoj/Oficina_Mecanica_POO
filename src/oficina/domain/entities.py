from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .enums import Perfil, StatusOS, StatusServico
from .exceptions import EstadoInvalidoError


@dataclass(frozen=True)
class Usuario(ABC):
    id: int
    nome: str
    login: str
    ativo: bool = True

    @property
    @abstractmethod
    def perfil(self) -> Perfil: ...

    @abstractmethod
    def permite(self, action: str, responsible_id: int | None = None) -> bool: ...


@dataclass(frozen=True)
class Administrador(Usuario):
    @property
    def perfil(self) -> Perfil:
        return Perfil.ADMIN

    def permite(self, action: str, responsible_id: int | None = None) -> bool:
        return self.ativo


@dataclass(frozen=True)
class Mecanico(Usuario):
    @property
    def perfil(self) -> Perfil:
        return Perfil.MECANICO

    def permite(self, action: str, responsible_id: int | None = None) -> bool:
        return self.ativo and action in {"visualizar", "executar"} and responsible_id == self.id


@dataclass(frozen=True)
class Cliente:
    id: int
    nome: str
    cpf: str
    telefone: str
    email: str
    ativo: bool


@dataclass(frozen=True)
class Veiculo:
    id: int
    cliente_id: int
    placa: str
    marca: str
    modelo: str
    ano: int
    ativo: bool


@dataclass(frozen=True)
class Peca:
    id: int
    descricao: str
    valor_centavos: int
    estoque: int
    ativo: bool


@dataclass(frozen=True)
class Servico:
    id: int
    descricao: str
    valor_centavos: int
    ativo: bool


@dataclass(frozen=True)
class ItemPeca:
    id: int
    peca_id: int
    descricao: str
    quantidade: int
    valor_centavos: int
    consumido: bool

    @property
    def subtotal(self) -> int:
        return self.quantidade * self.valor_centavos


@dataclass(frozen=True)
class ItemServico:
    id: int
    servico_id: int
    descricao: str
    valor_centavos: int
    status: StatusServico


@dataclass
class OrdemServico:
    id: int
    cliente_id: int
    veiculo_id: int
    mecanico_id: int | None
    problema: str
    status: StatusOS
    pecas: list[ItemPeca] = field(default_factory=list)
    servicos: list[ItemServico] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(p.subtotal for p in self.pecas) + sum(s.valor_centavos for s in self.servicos)

    def validar_edicao(self) -> None:
        if self.status in {StatusOS.CONCLUIDA, StatusOS.CANCELADA}:
            raise EstadoInvalidoError(
                "Não é possível alterar itens de uma OS concluída ou cancelada."
            )

    def validar_transicao(self, target: StatusOS) -> None:
        allowed = {
            StatusOS.ABERTA: {StatusOS.ORCAMENTO, StatusOS.CANCELADA},
            StatusOS.ORCAMENTO: {StatusOS.AGUARDANDO, StatusOS.CANCELADA},
            StatusOS.AGUARDANDO: {StatusOS.APROVADA, StatusOS.CANCELADA},
            StatusOS.APROVADA: {StatusOS.EXECUCAO, StatusOS.CANCELADA},
            StatusOS.EXECUCAO: {StatusOS.CONCLUIDA},
        }
        if target not in allowed.get(self.status, set()):
            raise EstadoInvalidoError(f"Não é permitido mudar de {self.status} para {target}.")
        if target in {StatusOS.AGUARDANDO, StatusOS.APROVADA, StatusOS.CONCLUIDA}:
            if not self.servicos:
                raise EstadoInvalidoError("Inclua pelo menos um serviço na OS.")
        if target == StatusOS.EXECUCAO and self.mecanico_id is None:
            raise EstadoInvalidoError("Atribua um mecânico antes de iniciar a execução.")
        if target == StatusOS.CONCLUIDA and any(
            s.status != StatusServico.FINALIZADO for s in self.servicos
        ):
            raise EstadoInvalidoError("Finalize todos os serviços antes de concluir a OS.")
