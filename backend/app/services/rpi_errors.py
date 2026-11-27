"""Exceções de domínio da coleta da RPI (US08, US09), com mensagens prontas para o usuário.

A causa técnica (exceção original) fica no log ou em __cause__, nunca na mensagem.
"""


class RpiError(Exception):
    """Erro da coleta da RPI, com mensagem pronta para o usuário."""


class RpiDownloadError(RpiError):
    """Não foi possível baixar um arquivo da RPI."""


class RpiNotPublishedError(RpiDownloadError):
    """A edição pedida ainda não foi publicada pelo INPI."""


class RpiInvalidFileError(RpiDownloadError):
    """O arquivo baixado está incompleto, corrompido ou fora do formato esperado."""


class RpiParseError(RpiError):
    """O XML da RPI não pôde ser lido."""
