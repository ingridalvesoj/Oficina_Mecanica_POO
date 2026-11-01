class OficinaError(Exception):
    """Erro seguro para exibição ao usuário."""


class CampoObrigatorioError(OficinaError):
    pass


class ValidacaoError(OficinaError):
    pass


class RegistroNaoEncontradoError(OficinaError):
    pass


class PersistenciaError(OficinaError):
    pass


class CarregamentoError(OficinaError):
    pass


class PermissaoNegadaError(OficinaError):
    pass


class EstadoInvalidoError(OficinaError):
    pass


class EstoqueInsuficienteError(OficinaError):
    pass
