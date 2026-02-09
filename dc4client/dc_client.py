import aiohttp
from aiohttp import BasicAuth
import asyncio
import json
import logging
import pathlib
from datetime import datetime
from uuid import UUID
import aiohttp.client_exceptions
import numpy as np
from typing import AsyncGenerator
from aiohttp_sse_client2 import client
from typing import Any

from dcclient.receive_data import (
    StateSchema,
)
from dcclient.send_data import (
    MatchNameModel,
    ShotInfoModel,
    TeamModel,
    PositionedStonesModel
)

# クライアント側でこのホスト名とポート番号を代入できる形に変更したい。ただし、クライアント作成者が気にしなくても自動で設定される形にしたい。


# ログファイルの保存先ディレクトリを指定
par_dir = pathlib.Path(__file__).parents[1]
log_dir = par_dir / "logs"

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file_name = f"dc3_5_{current_time}.log"
log_file_path = log_dir / log_file_name


class DCClient:
    def __init__(
        self,
        match_id: UUID,
        username: str,
        password: str,
        log_level: int = logging.INFO,
        match_team_name: MatchNameModel = MatchNameModel.team1,
    ):
        """Initialize the DCClient.
            Args:
                match_id (UUID): To identify the match.
                username (str): Username for authentication.
                password (str): Password for authentication.
                log_level (int): Logging level.
                match_team_name (MatchNameModel): The name of the team in the match.
        """
        self.logger = logging.getLogger("DC_Client")
        self.logger.propagate = False
        self.logger.setLevel(log_level)

        formatter = logging.Formatter(
            "%(asctime)s, %(name)s : %(levelname)s - %(message)s"
        )
        # file_handler = logging.FileHandler(log_file_path, encoding="utf-8", mode="w")
        # file_handler.setFormatter(formatter)
        # self.logger.addHandler(file_handler)

        st_handler = logging.StreamHandler()
        st_handler.setFormatter(formatter)
        self.logger.addHandler(st_handler)

        self.match_id: UUID = match_id
        self.match_team_name: MatchNameModel = match_team_name
        self.username: str = username
        self.password: str = password
        self.state_data: StateSchema = None
        self.winner_team: MatchNameModel = None

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
            match_id (UUID): To identify the match.
            team_info (TeamModel):
                use_default_cinfig (bool): Whether to use default configuration.
                team_name (str): Your team name.
                match_team_name (MatchNameModel): The name of the team in the match.
                player1 (PlayerModel): Player 1 information.
                player2 (PlayerModel): Player 2 information.
                player3 (PlayerModel | None): Player 3 information (optional; may be None for Mix Doubles).
                player4 (PlayerModel | None): Player 4 information (optional; may be None for Mix Doubles).
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
                        self.logger.info("Team information successfully sent.")
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

        self.logger.debug(f"match_team_name: {self.match_team_name}")

        return self.match_team_name

    async def send_shot_info_dc3(
        self,
        vx: float,
        vy: float,
        rotation: str
    ):
        """Send shot information to the server for DC3.
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
    ):
        """
            This method is to support mix doubles positioned stones info.
            Send positioned stones information to the server.
            positioned_stones: PositionedStonesModel
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
        """Receive state data from the server using Server-Sent Events (SSE).
        Yields:
            StateSchema: The latest state data received from the server.
        """
        url = f"{self.sse_url}/{self.match_id}/stream"
        self.logger.info(f"Connecting to SSE URL: {url}")  # URLをログに出力

        while True:
            try:
                async with client.EventSource(
                    url=url, auth=BasicAuth(login=self.username, password=self.password), reconnection_time=5, max_connect_retry=5
                ) as sse_client:

                    async for event in sse_client:
                        if event.type == "latest_state_update":
                            latest_state_data: StateSchema = json.loads(event.data)
                            latest_state_data = StateSchema(**latest_state_data)
                            self.state_data = latest_state_data
                            self.logger.debug(f"Received latest state data: {latest_state_data}")
                            yield latest_state_data

                        elif event.type == "state_update":
                            state_data: StateSchema = json.loads(event.data)
                            state_data = StateSchema(**state_data)
                            self.logger.debug(f"Received state data: {state_data}")
                            
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.logger.error("Server is not running. Please contact the administrator.")
                break
            except TimeoutError:
                self.logger.error("Timeout error occurred while receiving state data.")
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")
                await asyncio.sleep(5)

    def get_end_number(self):
        """Get the current end number from the state data."""
        return self.state_data.end_number

    def get_shot_number(self):
        """Get the current shot number from the state data."""
        return self.state_data.total_shot_number

    def get_score(self):
        """Get the current score from the state data."""
        score = self.state_data.score
        return score.first_team_score, score.second_team_score

    def get_next_team(self):
        """Get the next team to shot from the state data."""
        return self.state_data.next_shot_team

    def get_last_move(self):
        """Get the last move information from the state data."""
        return self.state_data.last_move

    def get_winner_team(self):
        """Get the winner team from the state data."""
        winner_team = self.state_data.winner_team
        return winner_team

    def get_stone_coordinates(self):
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


async def main():
    pass

if __name__ == "__main__":
    asyncio.run(main())
