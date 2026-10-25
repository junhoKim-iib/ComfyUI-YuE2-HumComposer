"""Stateless local preview/edit endpoint. No queue, model or filesystem operations."""
import asyncio
from fractions import Fraction
import sys

from .humcomposer.abc.editing import paint_interval, edit_chord, append_measure, add_voice
from .nodes.score import _preview


def _time(data, key):
    value = data.get(key)
    if (not isinstance(value, list) or len(value) != 2 or
            any(isinstance(n, bool) or not isinstance(n, int) or abs(n) > 2 ** 31 for n in value) or value[1] <= 0):
        raise ValueError(f'{key} must be a [numerator, positive denominator] pair')
    return Fraction(*value)


def handle_score_request(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get('abc'), str):
        raise ValueError('Expected an ABC string')
    abc = data['abc']
    action = data.get('action', 'preview')
    added_voice = None
    if action in ('paint', 'add', 'move', 'erase'):
        origin = (_time(data, 'oldOffset'), _time(data, 'oldDuration')) if action == 'move' else None
        additive = data.get('additive', action == 'add')
        if not isinstance(additive, bool):
            raise ValueError('additive must be a boolean')
        abc = paint_interval(abc, data.get('voice'), data.get('measure'), _time(data, 'offset'),
                             _time(data, 'duration'), None if action == 'erase' else data.get('midi'), origin,
                             additive=additive, erase_pitch=data.get('erasePitch'))
    elif action == 'chord':
        abc = edit_chord(abc, data.get('voice'), data.get('measure'), _time(data, 'offset'), data.get('chord'))
    elif action == 'append':
        abc = append_measure(abc)
    elif action == 'add_voice':
        abc, added_voice = add_voice(abc, data.get('voice'), data.get('name', ''), data.get('clef', 'treble'))
    elif action != 'preview':
        raise ValueError('Unknown score action')
    payload = _preview(abc)
    if added_voice:
        payload['addedVoice'] = added_voice
    return payload


def register_routes() -> None:
    # Headless loader tests can import the nodes without a running PromptServer.
    server = sys.modules.get('server')
    if server is None or not hasattr(server.PromptServer, 'instance'):
        return
    from aiohttp import web

    @server.PromptServer.instance.routes.post('/humcomposer/score')
    async def score_request(request):
        if request.content_length is not None and request.content_length > 12_000_000:
            return web.json_response({'error': 'Score request is too large'}, status=413)
        try:
            data = await request.json()
            payload = await asyncio.to_thread(handle_score_request, data)
        except (ValueError, TypeError, KeyError, StopIteration) as error:
            return web.json_response({'error': str(error)}, status=400)
        return web.json_response(payload)
