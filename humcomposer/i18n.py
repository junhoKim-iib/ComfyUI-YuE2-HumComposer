"""Report translation with an explicit, request-local language."""
from functools import lru_cache
import json
from pathlib import Path


def normalize_locale(value) -> str:
    language = value.lower().replace('_', '-').split('-')[0] if isinstance(value, str) else 'en'
    return language if language in ('en', 'ko') else 'en'


@lru_cache(maxsize=2)
def _catalog(locale: str) -> dict:
    return json.loads((Path(__file__).parent / 'locales' / f'{locale}.json').read_text(encoding='utf-8'))


def translate(message_key: str, locale: str = 'en', **params) -> str:
    template = _catalog(normalize_locale(locale)).get(message_key, _catalog('en').get(message_key, message_key))
    return template.format(**params)


def report_inputs(schema: dict) -> dict:
    return {**schema, 'hidden': {**schema.get('hidden', {}),
                               'extra_pnginfo': 'EXTRA_PNGINFO', 'unique_id': 'UNIQUE_ID',
                               'report_language': ('STRING',)}}


def report_locale(extra_pnginfo=None, unique_id=None, report_language=None) -> str:
    if report_language is not None:
        return normalize_locale(report_language)
    if not isinstance(extra_pnginfo, dict) or not isinstance(extra_pnginfo.get('workflow'), dict):
        return 'en'
    nodes = extra_pnginfo['workflow'].get('nodes', [])
    if not isinstance(nodes, list):
        return 'en'
    for node in nodes:
        if not isinstance(node, dict) or str(node.get('id')) != str(unique_id):
            continue
        properties = node.get('properties', {})
        return normalize_locale(properties.get('humcomposer_locale')) if isinstance(properties, dict) else 'en'
    return 'en'


def prepare_report_language(data: dict) -> dict:
    """Add a hidden constant to the queued prompt so ComfyUI can cache per language.

    EXTRA_PNGINFO is unavailable during IS_CHANGED evaluation on ComfyUI V1 nodes.
    The saved workflow and the caller's prompt are left untouched.
    """
    node_types = {'YuE2HumMelodyAnalyze', 'YuE2KeyModeCandidates', 'YuE2ChordProgressionRecommend',
                  'YuE2HumSongComposer', 'YuE2ABCValidate', 'YuE2ABCScoreViewer',
                  'YuE2ABCScoreEditor', 'YuE2HumTranscribe', 'YuE2HumGenerateABC'}
    prompt = data.get('prompt')
    if not isinstance(prompt, dict):
        return data
    extra_data = data.get('extra_data', {})
    extra_pnginfo = extra_data.get('extra_pnginfo') if isinstance(extra_data, dict) else None
    workflow = extra_pnginfo.get('workflow') if isinstance(extra_pnginfo, dict) else None
    nodes = workflow.get('nodes') if isinstance(workflow, dict) else None
    locales = {}
    for node in nodes if isinstance(nodes, list) else []:
        properties = node.get('properties') if isinstance(node, dict) else None
        if isinstance(properties, dict) and 'humcomposer_locale' in properties:
            locales[str(node.get('id'))] = normalize_locale(properties['humcomposer_locale'])
    languages = set(locales.values())
    # Native generators upgraded by the earlier handler have no custom locale property.
    fallback = next(iter(languages)) if len(languages) == 1 else 'en'
    updated = dict(prompt)
    for node_id, node in prompt.items():
        if not isinstance(node, dict) or node.get('class_type') not in node_types:
            continue
        inputs = node.get('inputs', {})
        if not isinstance(inputs, dict):
            continue
        locale = normalize_locale(inputs['report_language']) if 'report_language' in inputs else locales.get(str(node_id), fallback)
        updated[node_id] = {**node, 'inputs': {**inputs, 'report_language': locale}}
    return {**data, 'prompt': updated}
