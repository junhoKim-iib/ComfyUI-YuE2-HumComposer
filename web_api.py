"""Stateless local preview/edit endpoint. No queue, model or filesystem operations."""
import asyncio
from fractions import Fraction
import sys

from .humcomposer.abc.editing import paint_interval, edit_chord, append_measure
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
    if action in ('paint', 'move'):
        origin = (_time(data, 'oldOffset'), _time(data, 'oldDuration')) if action == 'move' else None
        abc = paint_interval(abc, data.get('voice'), data.get('measure'), _time(data, 'offset'),
                             _time(data, 'duration'), data.get('midi'), origin)
    elif action == 'chord':
        abc = edit_chord(abc, data.get('voice'), data.get('measure'), _time(data, 'offset'), data.get('chord'))
    elif action == 'append':
        abc = append_measure(abc)
    elif action != 'preview':
        raise ValueError('Unknown score action')
    return _preview(abc)


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
