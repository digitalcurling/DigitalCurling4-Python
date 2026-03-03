import aiohttp
from aiohttp import BasicAuth
import asyncio
import json
import logging
from uuid import UUID
import aiohttp.client_exceptions
import numpy as np
from typing import AsyncGenerator, Any, Optional, List, Dict
from aiohttp_sse_client2 import client
from pathlib import Path
from datetime import datetime
import base64  # Moved to top level
import random  # Moved to top level

from dc4client.receive_data import (
    StateSchema,
    ScoreSchema,
    ShotInfoSchema,
)
from dc4client.send_data import (
    MatchNameModel,
    ShotInfoModel,
    TeamModel,
    PositionedStonesModel
)


class MemoryBufferHandler(logging.Handler):
    """
    Custom logging handler that stores log records in a memory list
    instead of writing them to a file immediately.
    """
    def __init__(self):
        super().__init__()
        self.buffer: List[Dict[str, Any]] = []

    def emit(self, record: logging.LogRecord):
        """Record log data
        Args:
            record (logging.LogRecord): The log record to be buffered.
        """        
        try:
            # Convert log record to dictionary format
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
                "logger": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
            }
            if record.exc_info:
                # Format exception info if present
                log_entry["exception"] = self.format(record)
            
            self.buffer.append(log_entry)
        except Exception:
            self.handleError(record)


class JsonLineFormatter(logging.Formatter):
    """Format log records as single-line JSON.
    Output keys match:
      {"timestamp": "...", "logger": "...", "level": "...", "message": "..."}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class DCClient:
    """Initialize the DCClient.
        Args:
            match_id (UUID): To identify the match.
            username (str): Username for authentication.
            password (str): Password for authentication.
            log_level (int): Logging level.
            match_team_name (MatchNameModel): The name of the team in the match.
            socket_read_timeout (int | None): Timeout in seconds for socket read. Defaults to 15. Set None to disable.
            enable_tcp_keepalive (bool): Whether to enable TCP Keep-Alive. Defaults to True.
            auto_save_log (bool): Whether to enable log buffering and saving. Defaults to True.
            log_dir (str): Directory to save logs. Defaults to "logs".
    """
    def __init__(
        self,
        match_id: UUID,
        username: str,
        password: str,
        log_level: int = logging.INFO,
        match_team_name: MatchNameModel = MatchNameModel.team1,
        socket_read_timeout: Optional[int] = 15,
        enable_tcp_keepalive: bool = True,
        auto_save_log: bool = True,
        log_dir: str = "logs" 
    ):
        # Initialize internal logger
        self.logger = logging.getLogger("DC_Client")
        self.logger.propagate = False
        self.logger.setLevel(log_level)

        # Initialize memory buffer handler for file saving
        self.auto_save_log = auto_save_log
        self.log_dir = Path(log_dir)
        existing_memory_handler = next(
            (h for h in self.logger.handlers if isinstance(h, MemoryBufferHandler)),
            None,
        )
        if existing_memory_handler is None:
            self.memory_handler = MemoryBufferHandler()
            self.logger.addHandler(self.memory_handler)
        else:
            self.memory_handler = existing_memory_handler

        self.match_id: UUID = match_id
        self.match_team_name: MatchNameModel = match_team_name
        self.username: str = username
        self.password: str = password
        self.state_data: StateSchema = None
        self.winner_team: MatchNameModel = None

        self.socket_read_timeout = socket_read_timeout
        self.enable_tcp_keepalive = enable_tcp_keepalive

        # Initialize URLs (defaults; can be overwritten by set_server_address)
        self.team_info_url = ""
        self.shot_info_url = ""
        self.sse_url = ""
        self.positioned_stones_url = ""

    def save_log_file(self) -> None:
        """Saves the buffered logs to a JSONL file."""
        if not self.auto_save_log or not self.memory_handler.buffer:
            return

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate file name including team name to avoid conflicts
            team_name = self.match_team_name.value if self.match_team_name else "unknown"
            if isinstance(team_name, MatchNameModel):
                 team_name = team_name.value
            
            safe_team_name = str(team_name).replace(" ", "_")
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"dc4_{safe_team_name}_{current_time}.jsonl"
            file_path = self.log_dir / file_name

            self.logger.debug(f"Saving log file to: {file_path}")

            with open(file_path, "w", encoding="utf-8") as f:
                for entry in self.memory_handler.buffer:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            
            # Print directly to stdout to ensure visibility
            print(f"Log file saved successfully: {file_path}")

        except Exception as e:
            import sys
            print(f"Failed to save log file: {e}", file=sys.stderr)


    def set_server_address(self, host: str, port: int) -> None:
        """Set the server address for the client.
            Args:
                host (str): The server host address.
                port (int): The server port number.
        """
        self.team_info_url = f"http://{host}:{port}/store-team-config"
        self.shot_info_url = f"http://{host}:{port}/shots"
        self.sse_url = f"http://{host}:{port}/matches"
        self.positioned_stones_url = f"http://{host}:{port}/matches"

    async def _read_response_body(self, response: aiohttp.ClientResponse) -> Any:
        try:
            return await response.json()
        except Exception:
            return await response.text()

    async def send_team_info(
        self, team_info: TeamModel
    ) -> MatchNameModel:
        """Send team information to the server.
        Args:
            team_info (TeamModel): Team information model.
        Returns:
            MatchNameModel: The assigned team name in the match.
        """

        async with aiohttp.ClientSession(
            auth=BasicAuth(login=self.username, password=self.password)
        ) as session:
            try:
                async with session.post(
                    url=self.team_info_url,
                    params={
                        "match_id": self.match_id,
                        "expected_match_team_name": self.match_team_name.value,
                    },
                    json=team_info.model_dump(),
                ) as response:
                    response_body = await self._read_response_body(response)

                    if response.status == 200:
                        self.logger.debug("Team information successfully sent.")
                        if isinstance(response_body, str):
                            self.match_team_name = MatchNameModel(response_body)
                        else:
                            self.match_team_name = response_body
                    elif response.status == 400:
                        self.logger.error(
                            f"Bad Request: status={response.status}, body={response_body}"
                        )
                    elif response.status == 401:
                        self.logger.error(
                            f"Unauthorized: status={response.status}, body={response_body}"
                        )
                    else:
                        self.logger.error(
                            f"Failed to send team information: status={response.status}, body={response_body}"
                        )
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.logger.error("Server is not running. Please contact the administrator.")
            except Exception as e:
                self.logger.error(f"Failed to connect to server: {e}")

        self.logger.debug(f"match_team_name: {self.match_team_name}")

        return self.match_team_name

    async def send_shot_info_dc3(
        self,
        vx: float,
        vy: float,
        rotation: str
    ):
        """Send shot information to the server for DC3 style input.
        Args:
            vx (float): The x-component of the velocity of the stone.
            vy (float): The y-component of the velocity of the stone.
            rotation (str): The rotation direction of the stone ("cw" for clockwise, "ccw" for counter-clockwise).
        """
        translational_velocity = np.sqrt(vx**2 + vy**2)
        shot_angle = np.arctan2(vy, vx)
        angular_velocity = np.pi / 2
        if rotation == "cw":
            angular_velocity = np.pi / 2
        elif rotation == "ccw":
            angular_velocity = -np.pi / 2
        else:
            pass
        await self.send_shot_info(
            translational_velocity=translational_velocity,
            shot_angle=shot_angle,
            angular_velocity=angular_velocity,
        )

    async def send_shot_info(
        self,
        translational_velocity: float,
        shot_angle: float,
        angular_velocity=np.pi / 2,
    ):
        """Send shot information to the server.
        Args:
            translational_velocity (float): The translational velocity of the stone.
            shot_angle (float): The shot angle of the stone in radians.
            angular_velocity (float): The angular velocity of the stone.
        """
        shot_info = ShotInfoModel(
            translational_velocity=translational_velocity,
            angular_velocity=angular_velocity,
            shot_angle=shot_angle,
        )
        
        async with aiohttp.ClientSession(
            auth=BasicAuth(login=self.username, password=self.password)
        ) as session:
            try:
                async with session.post(
                    url=self.shot_info_url,
                    params={"match_id": self.match_id},
                    json=shot_info.model_dump(),
                ) as response:
                    response_body = await self._read_response_body(response)
                    # Successful response
                    if response.status == 200:
                        self.logger.debug("Shot information successfully sent.")
                    # Unauthorized access
                    elif response.status == 401:
                        self.logger.error(
                            f"Unauthorized: status={response.status}, body={response_body}"
                        )
                    else:
                        self.logger.error(
                            f"Failed to send shot information: status={response.status}, body={response_body}"
                        )
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.logger.error("Server is not running. Please contact the administrator.")
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")

    # This method is for mix doubles positioned stones info
    async def send_positioned_stones_info(
        self,
        positioned_stones: PositionedStonesModel,
    ) -> None:
        """
            This method is to support mix doubles positioned stones info.
            Send positioned stones information to the server.
            Args:
                positioned_stones (PositionedStonesModel): Positioned stones information model.
        """
        url = f"{self.positioned_stones_url}/{self.match_id}/end-setup"

        async with aiohttp.ClientSession(
            auth=BasicAuth(login=self.username, password=self.password)
        ) as session:
            try:
                async with session.post(
                    url=url,
                    params={
                        "match_id": self.match_id,
                        "request": positioned_stones.value,
                    },
                ) as response:
                    response_body = await self._read_response_body(response)
                    # Successful response
                    if response.status == 200:
                        self.logger.debug("Positioned stones information successfully sent.")
                    # Bad Request
                    elif response.status == 400:
                        self.logger.error(
                            f"Bad Request: status={response.status}, body={response_body}"
                        )
                    # Unauthorized access
                    elif response.status == 401:
                        self.logger.error(
                            f"Unauthorized: status={response.status}, body={response_body}"
                        )
                    # Conflict error
                    elif response.status == 409:
                        self.logger.error(
                            f"Conflict: status={response.status}, body={response_body}"
                        )
                    # Other errors
                    else:
                        self.logger.error(
                            f"Failed to send positioned stones information: status={response.status}, body={response_body}"
                        )
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.logger.error("Server is not running. Please contact the administrator.")
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")

    async def receive_state_data(self) -> AsyncGenerator[StateSchema, None]:
        """
        Robust SSE receiver with:
          - explicit reconnect loop (exponential backoff + jitter)
          - Authorization header (Basic) for wider compatibility
          - TCP connector with keepalive options
          - clear logging for connect / disconnect / parse errors
        """
        # Note: 'base64' and 'random' are now imported at the top of the file
        
        url = f"{self.sse_url}/{self.match_id}/stream"
        self.logger.info(f"SSE loop start -> {url}")

        # Basic auth header construction
        credentials = f"{self.username}:{self.password}"
        b64 = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Basic {b64}",
        }

        # Application level timeout (Socket Read Timeout)
        timeout_settings = aiohttp.ClientTimeout(
            total=None, 
            sock_read=self.socket_read_timeout
        )

        backoff = 1.0
        max_backoff = 60.0
        consecutive_auth_errors = 0
        AUTH_ERROR_THRESHOLD = 5

        while True:
            self.logger.info(f"Attempting SSE connect (next retry in approx {backoff:.1f}s if fail)")
            
            # Create a new connector and session on each loop iteration
            connector = None
            if self.enable_tcp_keepalive:
                connector = aiohttp.TCPConnector(
                    ssl=False,
                    enable_cleanup_closed=True,
                    keepalive_timeout=30,
                    force_close=False,
                )

            try:
                # Create the session first and pass it into EventSource
                async with aiohttp.ClientSession(connector=connector, timeout=timeout_settings) as session:
                    async with client.EventSource(
                        url=url,
                        headers=headers,
                        session=session, # Pass the session here
                        reconnection_time=1,
                        max_connect_retry=None,
                    ) as sse_client:
                        
                        self.logger.debug("SSE connection established.")
                        has_received_valid_data = False

                        async for event in sse_client:
                            if not has_received_valid_data:
                                backoff = 1.0
                                consecutive_auth_errors = 0
                                has_received_valid_data = True
                                self.logger.debug("First packet received. Backoff reset.")

                            try:
                                payload = json.loads(event.data) if event.data else None

                                if event.type == "latest_state_update" and payload is not None:
                                    latest_state = StateSchema(**payload)
                                    self.state_data = latest_state
                                    # Log state data here. 
                                    self.logger.info(f"latest_state_data: {latest_state}")
                                    yield latest_state

                                elif event.type == "state_update" and payload is not None:
                                    state = StateSchema(**payload)
                                    self.state_data = state
                                    self.logger.info(f"state_data: {state}")
                                    yield state

                            except asyncio.CancelledError:
                                self.logger.debug("receive_state_data cancelled during processing.")
                                raise
                            except Exception:
                                self.logger.exception("Failed to parse/handle SSE event data")
                                continue

                # Exited async for => server closed the stream normally
                self.logger.warning("SSE stream closed by server. Reconnecting...")

            except asyncio.CancelledError:
                self.logger.warning("receive_state_data cancelled; exiting loop.")
                raise

            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                self.logger.warning(f"ClientResponseError: status={status}; {e}")
                
                if status in (401, 403):
                    consecutive_auth_errors += 1
                    self.logger.warning(f"Auth error count: {consecutive_auth_errors}")
                    if consecutive_auth_errors >= AUTH_ERROR_THRESHOLD:
                        backoff = min(max_backoff, backoff * 4)
                        self.logger.error("Too many auth errors. Check credentials.")
                
                sleep_time = backoff + random.uniform(0, 0.5 * backoff)
                await asyncio.sleep(sleep_time)
                backoff = min(max_backoff, backoff * 2)

            except (
                TimeoutError,
                asyncio.TimeoutError,
                aiohttp.client_exceptions.ServerTimeoutError,
                aiohttp.client_exceptions.ClientPayloadError,
                aiohttp.client_exceptions.ClientConnectorError,
                aiohttp.client_exceptions.ClientConnectionError,
                aiohttp.client_exceptions.ClientOSError,
                OSError,
                aiohttp.client_exceptions.ServerDisconnectedError,
            ) as e:
                sleep_time = backoff + random.uniform(0, 0.5 * backoff)
                self.logger.warning(f"Network error: {e!r}. Reconnecting in {sleep_time:.2f}s")
                
                await asyncio.sleep(sleep_time)
                backoff = min(max_backoff, backoff * 2)

            except Exception as e:
                sleep_time = backoff + random.uniform(0, 0.5 * backoff)
                self.logger.exception(f"Unexpected error: {e!r}. Reconnecting in {sleep_time:.2f}s")
                
                await asyncio.sleep(sleep_time)
                backoff = min(max_backoff, backoff * 2)

    def get_end_number(self) -> int:
        """Get the current end number from the state data."""
        return self.state_data.end_number

    def get_shot_number(self) -> int | None:
        """Get the current shot number from the state data."""
        return self.state_data.total_shot_number

    def get_score(self) ->  tuple[list, list] | None:
        """Get the current score from the state data."""
        score = self.state_data.score
        return score.team0, score.team1

    def get_next_team(self) -> str | None:
        """Get the next team to shot from the state data."""
        return self.state_data.next_shot_team

    def get_last_move(self) -> ShotInfoSchema | None:
        """Get the last move information from the state data."""
        return self.state_data.last_move

    def get_winner_team(self) -> str | None:
        """Get the winner team from the state data."""
        winner_team = self.state_data.winner_team
        return winner_team

    def get_stone_coordinates(self) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """Get the stone coordinates for both teams from the state data.
        Returns:
            Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]: 
                A tuple containing two lists of tuples.
                The first list contains the coordinates of team0's stones,
                and the second list contains the coordinates of team1's stones.
        """
        # Access the nested data properly from the StoneCoordinateSchema instance
        stone_coordinate_data = self.state_data.stone_coordinate.data
        # Extract coordinates for each team
        team0_stone_coordinate = stone_coordinate_data.get("team0", [])
        team1_stone_coordinate = stone_coordinate_data.get("team1", [])
        team0_coordinates = [(coord.x, coord.y) for coord in team0_stone_coordinate]
        team1_coordinates = [(coord.x, coord.y) for coord in team1_stone_coordinate]
        return team0_coordinates, team1_coordinates