import httpx


class CapashinoError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class CapashinoClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_notification(
        self, message: str, reference_id: str, idempotency_key: str
    ) -> dict:
        body = {
            "message": message,
            "reference_id": reference_id,
            "idempotency_key": idempotency_key,
        }
        try:
            response = await self._client.post("/api/notifications", json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            raise CapashinoError(
                f"Capashino вернул {status}: {e.response.text}", status_code=status
            ) from e
        except httpx.RequestError as e:
            raise CapashinoError(f"Ошибка сети: {type(e).__name__}") from e
        return response.json()
