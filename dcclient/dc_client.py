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

from dcclient.receive_database import (
    StateSchema,
)
from dcclient.send_database import (
    MatchNameModel,
    ShotInfoModel,
    TeamModel,
)

# クライアント側でこのホスト名とポート番号を代入できる形に変更したい。ただし、クライアント作成者が気にしなくても自動で設定される形にしたい。
TEAM_INFO_URL = "http://localhost:5000/store-team-config"
SHOT_INFO_URL = "http://localhost:5000/shots"
SSE_URL = "http://localhost:5000/matches"

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
        # 通信が切断された時刻（再接続までの時間計測用）
        self.disconnected_at = None

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
                player3 (PlayerModel): Player 3 information.
                player4 (PlayerModel): Player 4 information.
        """

        async with aiohttp.ClientSession(
            auth=BasicAuth(login=self.username, password=self.password)
        ) as session:
            try:
                async with session.post(
                    url=TEAM_INFO_URL,
                    params={
                        "match_id": self.match_id,
                        "expected_match_team_name": self.match_team_name.value,
                    },
                    json=team_info.model_dump(),
                ) as response:

                        # Successful response
                        if response.status == 200:
                            self.logger.info("Team information successfully sent.")
                            self.match_team_name = await response.json()
                            print(f"team_name: {self.match_team_name}")

                        # Unauthorized access
                        elif response.status == 401:
                            self.logger.error(f"response: {response}")
                            self.logger.error(
                                "Unauthorized access. Please check your credentials."
                            )
                        else:
                            self.logger.error("Failed to send team information.")
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.logger.error("Server is not running. Please contact the administrator.")

        return self.match_team_name

    async def send_shot_info_dc3(
        self,
        vx: float,
        vy: float,
        rotation: str
    ):
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
                    url=SHOT_INFO_URL,
                    params={"match_id": self.match_id},
                    json=shot_info.model_dump(),
                ) as response:
                    # Successful response
                    if response.status == 200:
                        self.logger.debug("Shot information successfully sent.")
                    # Unauthorized access
                    elif response.status == 401:
                        self.logger.error(f"response: {response}")
                        self.logger.error(
                            "Unauthorized access. Please check your credentials."
                        )
                    else:
                        self.logger.error(f"response: {response}")
                        self.logger.error("Failed to send shot information.")
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.logger.error("Server is not running. Please contact the administrator.")
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")


    async def receive_state_data(self) -> AsyncGenerator[StateSchema, None]:
        url = f"{SSE_URL}/{self.match_id}/stream"
        self.logger.info(f"Connecting to SSE URL: {url}")  # URLをログに出力
        while True:
            try:
                # 直前に切断されていた場合は、再接続までの時間を計測
                if self.disconnected_at is not None:
                    downtime = datetime.now() - self.disconnected_at
                    self.logger.info(
                        f"Reconnected after {downtime.total_seconds():.4f} seconds of disconnection."
                    )
                    self.disconnected_at = None

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
                # 切断時刻を記録
                self.disconnected_at = datetime.now()
                break
            except TimeoutError:
                self.logger.error("Timeout error occurred while receiving state data.")
                # タイムアウト発生時刻を記録（次のループで再接続までの経過時間を計測）
                self.disconnected_at = datetime.now()
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")
                # その他のエラーでも切断扱いとして計測を開始
                self.disconnected_at = datetime.now()
                await asyncio.sleep(5)

    def get_end_number(self):
        return self.state_data.end_number

    def get_shot_number(self):
        return self.state_data.total_shot_number

    def get_score(self):
        score = self.state_data.score
        return score.first_team_score, score.second_team_score

    def get_next_team(self):
        return self.state_data.next_shot_team

    def get_last_move(self):
        return self.state_data.last_move

    def get_winner_team(self):
        winner_team = self.state_data.winner_team
        return winner_team

    def get_stone_coordinates(self):
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
