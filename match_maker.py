import json
import aiohttp.client_exceptions
import aiohttp
import asyncio
from aiohttp import BasicAuth
import logging

from load_secrets import username, password
from dcclient.send_database import ClientDataModel

URL = "http://localhost:10000/start-match"
logger = logging.getLogger("Match_Maker")
logger.setLevel(level=logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s, %(name)s : %(levelname)s - %(message)s"
)
st_handler = logging.StreamHandler()
st_handler.setFormatter(formatter)
logger.addHandler(st_handler)

# こちらを試合開始前に実行してください
# このプログラムを実行すると、match_id.jsonに次の試合で使用するmatch_idが生成されます
# このmatch_idを使って試合を開始します
async def main(data: ClientDataModel):
    async with aiohttp.ClientSession(
        auth=BasicAuth(login=username, password=password)) as session:
        try:
            async with session.get(
                url=URL,
                json=data.model_dump(),
                ) as response:

                    if response.status == 200:
                        logger.debug(f"Success: {response.status}")
                        match_id = await response.json()
                        logger.info(f"match_id: {match_id}")
                        with open("match_id.json", "w") as f:
                            json.dump(match_id, f)
                    elif response.status == 401:
                        logger.error(f"Failed: {response}")
                    elif response.status == 404:
                        logger.error("Some of the setting are wrong. Please check the setting.json file.")
        except aiohttp.client_exceptions.ServerDisconnectedError:
            logger.error("Server is not running. Please contact the administrator")


if __name__ == "__main__":
    with open("setting.json", "r") as f:
        data = json.load(f)
    data = ClientDataModel(**data)
    asyncio.run(main(data))
