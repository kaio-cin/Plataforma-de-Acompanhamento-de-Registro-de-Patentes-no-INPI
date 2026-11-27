"""Limites de tamanho dos campos, compartilhados pelo banco (models) e pela API (schemas).

Cada regra mora em um só lugar: o máximo de um campo é ao mesmo tempo o tamanho da coluna e o
máximo aceito no cadastro, então não há como os dois divergirem.
"""

# Ativo (US04)
TITLE_MIN_LENGTH = 3
TITLE_MAX_LENGTH = 500
PROCESS_NUMBER_MIN_LENGTH = 5
PROCESS_NUMBER_MAX_LENGTH = 50
STATUS_MIN_LENGTH = 2
STATUS_MAX_LENGTH = 100
AUTHORS_MIN_LENGTH = 2
AUTHORS_MAX_LENGTH = 1000
ASSET_TYPE_MAX_LENGTH = 40

# Usuário (US01–US03)
EMAIL_MAX_LENGTH = 255
PASSWORD_HASH_MAX_LENGTH = 255
USER_ROLE_MAX_LENGTH = 20

# Edição da RPI e despachos (US08–US10)
RPI_STATUS_MAX_LENGTH = 20
RPI_FILE_PATH_MAX_LENGTH = 500
RPI_ERROR_MESSAGE_MAX_LENGTH = 1000
DISPATCH_CODE_MAX_LENGTH = 10
DISPATCH_DESCRIPTION_MAX_LENGTH = 500
DISPATCH_PLAIN_DESCRIPTION_MAX_LENGTH = 1000
