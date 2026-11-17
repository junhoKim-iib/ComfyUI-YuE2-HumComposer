"""Generate and check a base plan against the enabled melody inputs."""
import re

from ..humcomposer.abc.parser import parse_abc
from ..humcomposer.abc.validation import require_valid
from ..humcomposer.composition.anchors import MelodyAnchor
from ..humcomposer.composition.merge import _tones, compose_song
from ..humcomposer.composition.theme import plan_main_theme
from ..humcomposer.composition.structure import ensure_audio_sections
from ..humcomposer.theory.key_detection import MelodyAnalysis
from .analyze import CATEGORY


def generation_requirements(anchors, main_theme):
    if not isinstance(anchors, tuple) or not all(isinstance(anchor, MelodyAnchor) for anchor in anchors):
        raise TypeError('Expected an anchor collection')
    if main_theme is not None and not isinstance(main_theme, MelodyAnalysis):
        raise TypeError('main_theme must be a melody analysis')
    requirements = []
    sections = {}
    for anchor in anchors:
        if anchor.mode == 'AI':
            continue
        count = 1 if anchor.occurrence == 'all' else int(anchor.occurrence)
        sections[anchor.section] = max(sections.get(anchor.section, 0), count)
        description = f'% {anchor.section}: at least {count} occurrence(s)'
        if anchor.abc.strip():
            source = parse_abc(anchor.abc)
            require_valid(source)
            _, bars = _tones(source, anchor.source_voice)
            if anchor.fit_policy in ('strict', 'pad_rest'):
                length = 'exactly' if anchor.fit_policy == 'strict' else 'at least'
                description += f'; {length} {len(bars)} complete bars per target'
            meters = sorted({f'{bar.meter.numerator}/{bar.meter.denominator}' for bar in bars})
            description += '; melody meter ' + ', '.join(meters)
        requirements.append(description + f'; target voice {anchor.target_voice}; no ties across section boundaries.')
    if main_theme is not None:
        _, bars = _tones(main_theme.score, main_theme.voice_id)
        requirements.append(f'Main theme: leave complete melodic windows of {len(bars)} bars in Vocal or Ins '
                            'for statements and later returns. No particular section name is required for the main theme.')
    return sections, requirements


def constrain_prompt(style, lyrics, sections, requirements):
    if not requirements:
        return style, lyrics
    for section, count in sections.items():
        found = len(re.findall(r'^\s*\[' + re.escape(section) + r'\]\s*$', lyrics, re.MULTILINE | re.IGNORECASE))
        for _ in range(max(0, count - found)):
            tag = f'[{section}]\n'
            if section == 'intro':
                lyrics = tag + lyrics
            else:
                outro = re.search(r'^\s*\[outro\]\s*$', lyrics, re.MULTILINE | re.IGNORECASE)
                position = outro.start() if outro else len(lyrics)
                lyrics = lyrics[:position].rstrip() + '\n' + tag + lyrics[position:]
    directive = ('REQUIRED ABC STRUCTURE FOR ENABLED AUDIO INPUTS:\n'
                 'Include every requested section with explicit % section comments and both Vocal and Ins voices. '
                 'These requirements override any conflicting structure suggestion above. '
                 'Finish all required sections within the token budget; do not omit, rename or substitute them.\n')
    return style + '\n\n' + directive + '\n'.join(requirements), lyrics


def validate_plan(abc, anchors, main_theme):
    require_valid(parse_abc(abc), native=True)
    planned = anchors
    if main_theme is not None:
        planned += plan_main_theme(abc, main_theme.score.source, main_theme.voice_id, reserved=anchors).anchors
    # Dry-run the same merge so presence alone cannot hide incompatible lengths/ties.
    compose_song(abc, planned, transpose_policy='none')


class HumGenerateABC:
    CATEGORY = CATEGORY
    FUNCTION = 'generate'
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('abc', 'generation_report')

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'clip': ('CLIP',),
            'style': ('STRING', {'multiline': True}),
            'lyrics': ('STRING', {'multiline': True}),
            'seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff, 'control_after_generate': True}),
            'mode': (['full', 'melody'],),
            'max_abc_tokens': ('INT', {'default': 8192, 'min': 1, 'max': 20000}),
            'temperature': ('FLOAT', {'default': .7, 'min': 0.0, 'max': 5.0}),
            'top_p': ('FLOAT', {'default': .9, 'min': .01, 'max': 1.0}),
            'top_k': ('INT', {'default': 30, 'min': 1, 'max': 32768}),
            'repetition_penalty': ('FLOAT', {'default': 1.005, 'min': .01, 'max': 10.0}),
            'penalty_window': ('INT', {'default': 100, 'min': 1, 'max': 20000}),
            'max_attempts': ('INT', {'default': 3, 'min': 1, 'max': 5,
                'tooltip': 'Retry incompatible plans with consecutive seeds. Never silently drop an enabled audio section.'}),
        }, 'optional': {'anchors': ('YUE2_ANCHORS',), 'main_theme': ('YUE2_HUM_ANALYSIS',)}}

    def generate(self, clip, style, lyrics, seed=0, mode='full', max_abc_tokens=8192,
                 temperature=.7, top_p=.9, top_k=30, repetition_penalty=1.005,
                 penalty_window=100, max_attempts=3, anchors=(), main_theme=None):
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
            raise ValueError('max_attempts must be an integer from 1 to 5')
        sections, requirements = generation_requirements(anchors, main_theme)
        prompt_style, prompt_lyrics = constrain_prompt(style, lyrics, sections, requirements)
        failures = []
        for attempt in range(max_attempts):
            attempt_seed = (seed + attempt) % (2 ** 64)
            tokens = clip.tokenize(prompt_style, lyrics=prompt_lyrics, cot=mode, seed=attempt_seed,
                                   max_tokens=max_abc_tokens, penalty_window=penalty_window)
            ids = clip.generate(tokens, max_length=max_abc_tokens, temperature=temperature, top_p=top_p,
                                top_k=top_k, repetition_penalty=repetition_penalty, seed=attempt_seed)
            abc = clip.decode(ids)
            try:
                if not isinstance(abc, str) or not abc.strip():
                    raise ValueError('YuE2 returned no ABC text')
                abc, reserved = ensure_audio_sections(abc, anchors, main_theme)
                validate_plan(abc, anchors, main_theme)
            except ValueError as error:
                failures.append(f'Attempt {attempt + 1}, seed {attempt_seed}: {error}')
                continue
            report = ['BASE PLAN: required audio sections and melody placement verified.',
                      f'Accepted attempt {attempt + 1}/{max_attempts}; seed {attempt_seed}.',
                      *requirements, *reserved, *failures]
            return abc, '\n'.join(report)
        raise ValueError('YuE2 could not generate a compatible plan for the enabled audio inputs after '
                         f'{max_attempts} attempt(s). No enabled input was omitted.\n' + '\n'.join(failures))


def prepare_required_generation(data):
    """Upgrade the queued copy of existing direct native-generator connections."""
    prompt = data.get('prompt')
    if not isinstance(prompt, dict):
        return data
    requests = {}
    for node in prompt.values():
        if node.get('class_type') != 'YuE2HumSongComposer':
            continue
        inputs = node.get('inputs', {})
        base = inputs.get('base_abc')
        if not isinstance(base, list) or len(base) != 2 or base[1] != 0:
            continue
        origin = prompt.get(base[0], {})
        if origin.get('class_type') != 'YuE2GenerateABC':
            continue
        requirements = {name: inputs[name] for name in ('anchors', 'main_theme') if name in inputs}
        if not requirements:
            continue
        if base[0] in requests and requests[base[0]] != requirements:
            raise ValueError('A shared ABC generator has different melody requirements; use a separate generator per composer.')
        requests[base[0]] = requirements
    if not requests:
        return data
    for node_id, requirements in requests.items():
        pending = [value[0] for value in requirements.values() if isinstance(value, list) and len(value) == 2]
        visited = set()
        while pending:
            dependency = pending.pop()
            if dependency == node_id:
                raise ValueError('Melody requirements depend on the base generator; use independent audio/ABC inputs for required sections.')
            if dependency in visited:
                continue
            visited.add(dependency)
            pending.extend(value[0] for value in prompt.get(dependency, {}).get('inputs', {}).values()
                           if isinstance(value, list) and len(value) == 2)
    updated = dict(prompt)
    for node_id, requirements in requests.items():
        node = prompt[node_id]
        updated[node_id] = {**node, 'class_type': 'YuE2HumGenerateABC',
                            'inputs': {**node.get('inputs', {}), **requirements, 'max_attempts': 3}}
    return {**data, 'prompt': updated}
