class ProviderError(Exception):
    """Базовая ошибка при работе с Events Provider."""


class ProviderUnauthorizedError(ProviderError):
    """Provider отклонил API-ключ (401/403)."""


class ProviderNotFoundError(ProviderError):
    """Ресурс не найден в Provider (404)."""


class ProviderBadRequestError(ProviderError):
    """Provider отклонил запрос (другие 4xx)."""


class ProviderUnavailableError(ProviderError):
    """Provider недоступен: таймаут, сеть, 5xx."""


class ProviderResponseError(ProviderError):
    """Ответ Provider не соответствует ожидаемому формату."""
