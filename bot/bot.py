import os
import csv
import json
import asyncio
import websockets
import requests


async def receive(websocket):
    """
    Waits for a message to arrive to the websocket, and parses a json out of it.
    :param websocket: The websocket to read a message from.
    :return: A json dictionary, or None if there was an error in parsing or a non-dictionary JSON.
    """

    try:
        obj = json.loads(await websocket.recv())
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
        await websocket.send(json.dumps({'type': 'list'}))
        result = await receive(websocket)
        if result is None or result.get('type') != 'notification' or result.get('code') != 'list' or not result.get('list'):
            raise RuntimeError("Unexpected message after 'list' operation: received %s instead of a "
                               "non-empty list notification" % (
                                   "a malformed message" if result is None else str(result)
                               ))
        else:
            rooms = [room['name'] for room in result.get('list', [])]
    for room in rooms:
        print(">>> finbot: joining room " + room)
        await websocket.send(json.dumps({'type': 'join', 'room_name': room}))


def ask_stock(asset):
    """
    Asks the price of a particular asset in stooq.
    :param asset: The assset code to ask
    :return: Its price.
    """

    url = 'https://stooq.com/q/l/?s=%s&f=sd2t2ohlcv&h&e=csv' % asset.lower()
    response = requests.get(url)
    if response.status_code != 200:
        print(">>> finbot: WARNING unexpected HTTP code %s for symbol: %s" % (response.status_code, asset))
        return None, None
    else:
        reader = csv.DictReader(response.text.split('\n'))
        try:
            row = next(reader)
            if row['Close'] == 'N/D':
                print(">>> finbot: WARNING bad or unavailable stock symbol: %s" % asset)
                return None, None
            return row['Symbol'], row['Close']
        except StopIteration:
            print(">>> finbot: WARNING empty data for stock: %s" % asset)
            return None, None


async def bot(token, host, rooms):
    """
    The whole bot lifecycle in the websocket.
    :param token: The token to init the lifecycle with.
    """

    print(">>> finbot: Starting websocket connection.")
    try:
        uri = "ws://%s/ws/chat/?token=%s" % (host, token)
        async with websockets.connect(uri) as websocket:
            # Wait for the greeting.
            await asyncio.sleep(1)
            # Process the greeting.
            greeting = await receive(websocket)
            if greeting is None or greeting.get('type') != "notification" or greeting.get('code') != "api-motd":
                print(">>> finbot: Expected MOTD message, but received %s. Aborting." % (
                    "a malformed message" if greeting is None else str(greeting),
                ))
                os._exit(1)
            # Connect to available rooms.
            await join_rooms(websocket, rooms)
            # Process the lifecycle.
            while not websocket.closed:
                received = await receive(websocket)
                if received:
                    custom = received.get('command')
                    room_name = received.get('room_name')
                    asset = received.get('payload')
                    print(">>> finbot: Received a message: %s" % (received,))
                    if room_name and custom == 'stock' and asset:
                        print(">>> finbot: A stock message. Processing...")
                        normalized_asset, price = ask_stock(asset)
                        if price:
                            print(">>> finbot: Parsed stooq data: %s %s" % (normalized_asset, price))
                            await websocket.send(json.dumps(
                                {"type": "message", "room_name": room_name,
                                 "body": "%s quote is $%s per share" % (normalized_asset, price)}
                            ))
                        else:
                            print(">>> finbot: Stooq data not found for: %s" % (asset,))
                            await websocket.send(json.dumps({"type": "message", "room_name": room_name,
                                                       "body": "I could not find stock data for %s" % asset}))
    except Exception as e:
        print(">>> finbot: Aborting due to exception: %s, %s" % (type(e).__name__, e.args))
        os._exit(1)


if __name__ == '__main__':
    print(">>> finbot: Starting")
    host = os.environ.get('FINBOT_HOST', 'localhost:8000')
    response = requests.post('http://%s/login' % host, json={
        "username": os.environ['FINBOT_USERNAME'],
        "password": os.environ['FINBOT_PASSWORD']
    })
    if response.status_code != 200:
        print(">>> finbot: Login failed. Unexpected status code: %d. Terminating." % response.status_code)
        os._exit(1)
    else:
        print(">>> finbot: Successful login")
        asyncio.get_event_loop().run_until_complete(bot(response.json()['token'], host, os.getenv('FINBOT_ROOMS', '')))
