import asyncio
import json
import numpy as np

from dcclient.dc_client import DCClient
from load_secrets import username, password
from dcclient.send_data import TeamModel, MatchNameModel


async def main():
    # 最初のエンドにおいて、team0が先攻、team1が後攻です。
    # デフォルトではteam1となっており、先攻に切り替えたい場合は下記を
    # team_name=MatchNameModel.team0
    # に変更してください
    # なお、後攻を希望したが先に対戦相手が後攻を選択した場合は、サーバ側が自動であなたを先攻に割り振ります。

    json_path = "match_id.json"
    with open(json_path, "r") as f:
        match_id = json.load(f)
    client = DCClient(match_id=match_id, username=username, password=password, match_team_name=MatchNameModel.team0)
    # client.logger.info(f"match_id: {match_id}")
    with open("team_config.json", "r") as f:
        data = json.load(f)
    client_data = TeamModel(**data)
    client.logger.info(f"client_data.team_name: {client_data.team_name}")
    client.logger.debug(f"client_data: {client_data}")

    match_team_name: MatchNameModel = await client.send_team_info(client_data)

    # 試合を開始します
    async for state_data in client.receive_state_data():
        # winner_teamが存在するかどうかで、試合の終了を判定します
        if (winner_team := client.get_winner_team()) is not None:
            client.logger.info(f"Winner: {winner_team}")
            break

        # 次のショットを打つチームを取得
        next_shot_team = client.get_next_team()
        client.logger.info(f"next_shot_team: {next_shot_team}")

        # AIによるショット情報を送信する際は、以下を変更してください
        if next_shot_team == match_team_name:
            await asyncio.sleep(2)  # 思考時間
            translational_velocity = 2.3
            angular_velocity = np.pi / 2
            shot_angle = np.pi / 180
            await client.send_shot_info(
                translational_velocity=translational_velocity,
                shot_angle=shot_angle,
                angular_velocity=angular_velocity,
            )

if __name__ == "__main__":
    asyncio.run(main())
