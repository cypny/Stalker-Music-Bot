import asyncio
import json
import string
import random
import aiohttp
from yandex_music import ClientAsync


async def get_current_track_data(ya_token: str, session: aiohttp.ClientSession) -> dict:
    device_id = "".join(random.choices(string.ascii_lowercase, k=16))
    ws_proto = {
        "Ynison-Device-Id": device_id,
        "Ynison-Device-Info": json.dumps({"app_name": "Chrome", "type": 1}),
    }

    async with session.ws_connect(
        "wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison",
        headers={
            "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
            "Origin": "http://music.yandex.ru",
            "Authorization": f"OAuth {ya_token}",
        },
    ) as ws:
        response = await ws.receive()
        data = json.loads(response.data)

    ws_proto["Ynison-Redirect-Ticket"] = data["redirect_ticket"]
    payload = {
        "update_full_state": {
            "player_state": {
                "player_queue": {
                    "current_playable_index": -1,
                    "entity_id": "",
                    "entity_type": "VARIOUS",
                    "playable_list": [],
                    "options": {"repeat_mode": "NONE"},
                    "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                    "version": {
                        "device_id": device_id,
                        "version": 9021243204784341000,
                        "timestamp_ms": 0,
                    },
                    "from_optional": "",
                },
                "status": {
                    "duration_ms": 0,
                    "paused": True,
                    "playback_speed": 1,
                    "progress_ms": 0,
                    "version": {
                        "device_id": device_id,
                        "version": 8321822175199937000,
                        "timestamp_ms": 0,
                    },
                },
            },
            "device": {
                "capabilities": {
                    "can_be_player": True,
                    "can_be_remote_controller": False,
                    "volume_granularity": 16,
                },
                "info": {
                    "device_id": device_id,
                    "type": "WEB",
                    "title": "Chrome Browser",
                    "app_name": "Chrome",
                },
                "volume_info": {"volume": 0},
                "is_shadow": True,
            },
            "is_currently_active": False,
        },
        "rid": "ac281c26-a047-4419-ad00-e4fbfda1cba3",
        "player_action_timestamp_ms": 0,
        "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT",
    }

    async with session.ws_connect(
        f"wss://{data['host']}/ynison_state.YnisonStateService/PutYnisonState",
        headers={
            "Sec-WebSocket-Protocol": f"Bearer, v2, {json.dumps(ws_proto)}",
            "Origin": "http://music.yandex.ru",
            "Authorization": f"OAuth {ya_token}",
        },
    ) as ws:
        await ws.send_str(json.dumps(payload))
        response = await ws.receive()
        ynison = json.loads(response.data)

    queue = ynison["player_state"]["player_queue"]
    track = queue["playable_list"][queue["current_playable_index"]]

    return {
        "paused": ynison["player_state"]["status"]["paused"],
        "duration_ms": ynison["player_state"]["status"]["duration_ms"],
        "progress_ms": ynison["player_state"]["status"]["progress_ms"],
        "entity_id": queue["entity_id"],
        "entity_type": queue["entity_type"],
        "track_id": track["playable_id"],
    }


def get_cover_url(cover_uri: str, size: str = "200x200") -> str:
    if not cover_uri:
        return None
    return f"https://{cover_uri.replace('%%', size)}"


async def get_track_info(track_id: int, ya_token: str) -> dict:
    client = ClientAsync(ya_token)
    await client.init()

    tracks = await client.tracks([f"{track_id}"])
    if not tracks:
        return {"error": "Трек не найден"}

    track = tracks[0]
    album_title = track.albums[0].title if track.albums else None

    return {
        "id": track.id,
        "title": track.title,
        "artists": [artist.name for artist in track.artists],
        "album": album_title,
        "duration": track.duration_ms,
        "cover_url": get_cover_url(track.cover_uri),
        "url": f"https://music.yandex.ru/track/{track_id}"
    }


async def get_current_track(ya_token: str):
    async with aiohttp.ClientSession() as session:
        try:
            current_track_data = await get_current_track_data(ya_token, session)
            track_id = current_track_data["track_id"]
            return await get_track_info(track_id, ya_token)
        except Exception as e:
            print(f"Ошибка получения текущего трека: {e}")
            return None