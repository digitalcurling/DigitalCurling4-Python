import json
import aiohttp.client_exceptions
import aiohttp
import asyncio
from aiohttp import BasicAuth
import logging

from load_secrets import username, password
from dcclient.send_data import ClientDataModel

URL = "http://localhost:5000/matches"
logger = logging.getLogger("Match_Maker")
logger.setLevel(level=logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s, %(name)s : %(levelname)s - %(message)s"
)
st_handler = logging.StreamHandler()
st_handler.setFormatter(formatter)
logger.addHandler(st_handler)


class MatchMaker:
    """
    MatchMaker class to handle match making for the DigitalCurling.
    This class is responsible for sending match data to the server
    and receiving the match_id for the next match.
    """
    def __init__(self):
        pass

    # こちらを試合開始前に実行してください
    # このプログラムを実行すると、match_id.jsonに次の試合で使用するmatch_idが生成されます
    # このmatch_idを使って試合を開始します
    async def main(self, data: ClientDataModel):
        async with aiohttp.ClientSession(
            auth=BasicAuth(login=username, password=password)) as session:
            try:
                async with session.post(
                    url=URL,
                    json=data.model_dump(),
                    ) as response:

                        if response.status == 200:
                            logger.debug(f"Success: {response.status}")
                            match_id = await response.json()
                            logger.info(f"match_id: {match_id}")
                            with open("match_id.json", "w") as f:
                                json.dump(match_id, f)
                        elif response.status == 400:
                            logger.error(f"Bad Request: {response}")
                        elif response.status == 401:
                            logger.error(f"Failed: {response}")
                        elif response.status == 422:
                            logger.error("Some of the setting are wrong. Please check the setting.json file.")
            except aiohttp.client_exceptions.ServerDisconnectedError:
                logger.error("Server is not running. Please contact the administrator")


if __name__ == "__main__":
    with open("md_setting.json", "r") as f:
    # with open("setting.json", "r") as f:
        data = json.load(f)
    data = ClientDataModel(**data)
    match_maker = MatchMaker()
    asyncio.run(match_maker.main(data))
