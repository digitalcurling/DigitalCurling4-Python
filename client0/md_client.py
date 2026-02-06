import asyncio
from datetime import datetime
import json
import numpy as np
import logging
from pathlib import Path

from load_secrets import username, password
from dcclient.dc_client import DCClient
from dcclient.send_data import TeamModel, MatchNameModel, PositionedStonesModel

# ログファイルの保存先ディレクトリを指定
par_dir = Path(__file__).parents[1]
log_dir = par_dir / "logs"

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file_name = f"dc3_5_{current_time}.log"
log_file_path = log_dir / log_file_name
formatter = logging.Formatter(
    "%(asctime)s, %(name)s : %(levelname)s - %(message)s"
)

async def main():
    # 最初のエンドにおいて、team0が先攻、team1が後攻です。
    # デフォルトではteam1となっており、先攻に切り替えたい場合は下記を
    # team_name=MatchNameModel.team0
    # に変更してください
    # なお、先に
    json_path = Path(__file__).parents[1] / "match_id.json"
    with open(json_path, "r") as f:
        match_id = json.load(f)
    client = DCClient(match_id=match_id, username=username, password=password, match_team_name=MatchNameModel.team0)
    client.set_server_address(host="localhost", port=5000)
    with open("md_team0_config.json", "r") as f:
        data = json.load(f)
    client_data = TeamModel(**data)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8", mode="w")
    file_handler.setFormatter(formatter)
    client.logger.addHandler(file_handler)
    client.logger.info(f"client_data.team_name: {client_data.team_name}")
    client.logger.debug(f"client_data: {client_data}")

    match_team_name: MatchNameModel = await client.send_team_info(client_data)

    async for state_data in client.receive_state_data():
        # client.logger.info(f"state_data: {state_data}")
        if (winner_team := client.get_winner_team()) is not None:
            client.logger.info(f"Winner: {winner_team}")
            break
        
        client.logger.info(f"state_data: {state_data}")

        next_shot_team = client.get_next_team()
        client.logger.info(f"next_shot_team: {next_shot_team}")

        if state_data.next_shot_team is None and state_data.mix_doubles_settings is not None:
            if state_data.mix_doubles_settings.end_setup_team == match_team_name:
                client.logger.info("You select the positioned stones.")
                # You can choose one of the following patterns:
                # PositionedStonesModel.center_guard -> Next End: Playing First
                # PositionedStonesModel.center_house -> Next End: Playing Second
                # PositionedStonesModel.pp_left      -> Next End: Positioned Stones on the Left and Playing Second
                # PositionedStonesModel.pp_right     -> Next End: Positioned Stones on the Right and Playing Second
                positioned_stones = PositionedStonesModel.center_house
                await client.send_positioned_stones_info(positioned_stones)
    
        if next_shot_team == match_team_name:
            await asyncio.sleep(2)  # 思考時間
            translational_velocity = 2.3
            angular_velocity = np.pi / 2
            shot_angle = np.pi / 2
            await client.send_shot_info(
                translational_velocity=translational_velocity,
                shot_angle=shot_angle,
                angular_velocity=angular_velocity,
            )

if __name__ == "__main__":
    asyncio.run(main())
