from enum import StrEnum


class Perfil(StrEnum):
    ADMIN = "Administrador"
    MECANICO = "Mecânico"


class StatusOS(StrEnum):
    ABERTA = "Aberta"
    ORCAMENTO = "Em orçamento"
    AGUARDANDO = "Aguardando aprovação"
    APROVADA = "Aprovada"
    EXECUCAO = "Em execução"
    CONCLUIDA = "Concluída"
    CANCELADA = "Cancelada"


class StatusServico(StrEnum):
    PENDENTE = "Pendente"
    EXECUCAO = "Em execução"
    FINALIZADO = "Finalizado"
