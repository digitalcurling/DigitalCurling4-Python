import aiohttp
from aiohttp import BasicAuth
from typing import Any

from dcclient.send_data import ClientDataModel


class MatchMakerClient:
    """ Initialize the MatchMakerClient.
        Args:
            host (str): Server host address.
            port (int): Server port number.
            username (str): Username for authentication.
            password (str): Password for authentication.
    """    
    def __init__(self, host: str, port: int, username: str, password: str):
        self._base_url = f"http://{host}:{port}"
        self._auth = BasicAuth(login=username, password=password)

    async def create_match(self, data: ClientDataModel) -> Any:
        """Create a match on the server.

        Returns:
            Parsed JSON returned by the server (typically a match_id).

        Raises:
            RuntimeError: When the request fails (includes status/body).
        """
        url = f"{self._base_url}/matches"

        async with aiohttp.ClientSession(auth=self._auth) as session:
            async with session.post(url=url, json=data.model_dump()) as response:
                try:
                    body: Any = await response.json()
                except Exception:
                    body = await response.text()

                if response.status == 200:
                    return body

                raise RuntimeError(f"Create match failed: status={response.status}, body={body}")
