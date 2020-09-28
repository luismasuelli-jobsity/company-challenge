import os
import csv
import json
import asyncio
import urllib.parse
import aiohttp


async def parse(message):
    """
    Parses a received websocket message.
    :param message: The message to parse.
    :return: A json dictionary if a valid json in binary/text format was received; None if there
      was an error in parsing or a non-dictionary JSON, or false if the mesasge was not of text
      or binary type.
    """

    if message.type not in {aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY}:
        return False

    try:
        obj = json.loads(message.data)
        if not isinstance(obj, dict):
            return None
        return obj
    except:
        return None


async def join_rooms(websocket, rooms):
    """
    Attempts to join all rooms defined in the FINBOT_ROOMS environment variable. If empty, lists
      all the rooms and attempts to join all of them.
    :param websocket: The websocket to use for the room(s) joining.
    :param rooms: The colon-separated list of rooms to join
    """

    rooms = [] if rooms == '' else rooms.split(':')

    if not rooms:
        await websocket.send_str(json.dumps({'type': 'list'}))
        result = await parse(await websocket.receive())
        # A {"type": "notification", "code": "list", "list": [{"name": ..., ...}, ...]} message is expected.
        # The room names will be extracted out of it.
        if result is None or result.get('type') != 'notification' or result.get('code') != 'list' or not result['list']:
            raise RuntimeError("Unexpected message after 'list' operation: received %s instead of a "
                               "non-empty list notification" % (
                                   "a malformed message" if result is None else str(result)
                               ))
        else:
            rooms = [room['name'] for room in result.get('list', [])]
    # For each room name, we attempt a join. It doesn't matter, with respect to the flow, if we fail to join.
    # Aside from the fact that there's no reason to fail unless an implementation error, it would mean that
    # the bot had already joined the room beforehand.
    for room in rooms:
        print(">>> finbot: joining room " + room)
        await websocket.send_str(json.dumps({'type': 'join', 'room_name': room}))


async def ask_stock(session, asset):
    """
    Asks the price of a particular asset in stooq.
    :param asset: The assset code to ask
    :return: Its price.
    """

    url = 'https://stooq.com/q/l/?s=%s&f=sd2t2ohlcv&h&e=csv' % (urllib.parse.quote(asset.lower()),)
    try:
        async with session.get(url) as response:
            if response.status != 200:
                print(">>> finbot: WARNING unexpected HTTP code %s for symbol %s" % (response.status_code, asset))
                return None, None
            else:
                reader = csv.DictReader((await response.text()).split('\n'))
                try:
                    row = next(reader)
                    if row['Close'] == 'N/D':
                        print(">>> finbot: WARNING bad or unavailable stock symbol %s" % asset)
                        return None, None
                    return row['Symbol'], row['Close']
                except StopIteration:
                    print(">>> finbot: WARNING empty data for symbol %s" % asset)
                    return None, None
    except Exception as e:
        print(">>> finbot: WARNING exception while trying to get data for symbol %s: %s, %s" % (asset, type(e).__name__, e.args))
        return None, None

async def lifecycle(session, token, host, rooms):
    """
    The whole bot lifecycle in the websocket.
    :param token: The token to init the lifecycle with.
    """

    print(">>> finbot: Starting websocket connection.")
    try:
        uri = "ws://%s/ws/chat/?token=%s" % (host, token)

        async with session.ws_connect(uri) as websocket:
            # Wait for the greeting.
            await asyncio.sleep(1)
            # Process the greeting (wait until a text/binary message).
            # The greeting is the first text/binary message that this
            # bot should receive. Otherwise, we consider an error in
            # our implementation or a session error (bad token or the
            # user is already connected to the chat).
            greeting = False
            while greeting is False:
                greeting = await parse(await websocket.receive())
            if greeting is None or greeting.get('type') != "notification" or greeting.get('code') != "api-motd":
                print(">>> finbot: Expected MOTD message, but received %s. Aborting." % (
                    "a malformed message" if greeting is None else str(greeting),
                ))
                os._exit(1)
            # Process the connection to all the specified or available
            # rooms (according to the FINBOT_ROOMS environment variable).
            await join_rooms(websocket, rooms)
            # Process the lifecycle.
            async for message in websocket:
                parsed = await parse(message)
                if parsed:
                    type_ = parsed.get('type')
                    code = parsed.get('code')
                    if type_ == 'room:notification' and code == 'custom':
                        print(">>> finbot: Received a message: %s" % (parsed,))
                        custom = parsed.get('command')
                        if custom == 'stock':
                            room_name = parsed.get('room_name')
                            asset = parsed.get('payload')
                            if room_name and asset:
                                print(">>> finbot: A stock message. Processing...")
                                normalized_asset, price = await ask_stock(session, asset)
                                if price:
                                    print(">>> finbot: Parsed stooq data: %s %s" % (normalized_asset, price))
                                    await websocket.send_str(json.dumps(
                                        {"type": "message", "room_name": room_name,
                                         "body": "%s quote is $%s per share" % (normalized_asset, price)}
                                    ))
                                else:
                                    print(">>> finbot: Stooq data not found for: %s" % (asset,))
                                    await websocket.send_str(json.dumps({"type": "message", "room_name": room_name,
                                                                         "body": "I could not find stock data for %s" % asset}))
                        else:
                            print(">>> finbot: I don't know about the command: %s" % custom)
    except Exception as e:
        print(">>> finbot: Aborting due to exception: %s, %s" % (type(e).__name__, e.args))
        os._exit(1)


async def bot():
    print(">>> finbot: Starting")
    host = os.environ.get('FINBOT_HOST', '') or 'localhost:8000'
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post('http://%s/login' % host, json={
                "username": os.environ['FINBOT_USERNAME'],
                "password": os.environ['FINBOT_PASSWORD']
            }) as response:
                if response.status != 200:
                    print(">>> finbot: Login failed. Unexpected status code: %d. Terminating." % response.status)
                    os._exit(1)
                else:
                    print(">>> finbot: Successful login")
                    await lifecycle(session, (await response.json())['token'], host, os.getenv('FINBOT_ROOMS', ''))
        except KeyError:
            print(">>> finbot: Misconfigured. Environment variables "
                  "FINBOT_USERNAME and FINBOT_PASSWORD are required. Terminating.")
            os._exit(1)
        except:
            print(">>> finbot: Network error while trying to hit the /login url. Terminating.")
            os._exit(1)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(bot())
