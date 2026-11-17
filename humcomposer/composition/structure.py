"""Reserve complete missing audio sections without relabeling generated music."""
from fractions import Fraction

from ..abc.parser import parse_abc
from ..abc.validation import require_valid
from .anchors import MelodyAnchor
from .merge import _tones, compose_song
from .theme import plan_main_theme


def _insert_section(abc, name, bars):
    score = parse_abc(abc)
    require_valid(score, native=True)
    if name == 'intro':
        existing = [s for s in score.sections if s.name == 'intro']
        offset = existing[-1].span.end if existing else score.sections[0].span.start
        if offset == 0:
            offset = len(abc)
    else:
        following = [s for s in score.sections if s.name == 'outro' or name == 'theme' and s.name == 'bridge']
        offset = min((s.span.start for s in following), default=len(abc))
    # Section comments can occur inside a sustained note. Keep that transition
    # intact and reserve the new section after the completed generated music.
    protected_boundary = any(previous and previous[-1].notes and previous[-1].notes[-1].tie_to_next
                             for voice in score.voices
                             for previous in ([bar for bar in voice.measures if bar.span.end <= offset],))
    if protected_boundary:
        offset = len(abc)
    block = [f'% {name}']
    restore = []
    for voice in score.voices:
        block += [f'V: {voice.id}', 'L:1/16']
        for bar in bars:
            count = bar.duration * 16
            duration = str(count.numerator) if count.denominator == 1 else f'{count.numerator}/{count.denominator}'
            block.append(f'[M:{bar.meter.numerator}/{bar.meter.denominator}][K:{bar.key.text}]z{duration}|')
        following_bars = [bar for bar in voice.measures if bar.span.start >= offset]
        if following_bars:
            following = following_bars[0]
            units = [change.value for change in score.changes if change.kind == 'L'
                     and change.voice_id in (None, voice.id) and change.span.start < following.span.start]
            unit = units[-1] if units else Fraction(1, 8)
            restore += [f'V: {voice.id}', f'L:{unit.numerator}/{unit.denominator}',
                        f'M:{following.meter.numerator}/{following.meter.denominator}', f'K:{following.key.text}']
    previous_voice = [header.value.split()[0] for header in score.headers if header.field == 'V' and header.span.start < offset]
    if restore and previous_voice:
        restore.append('V: ' + previous_voice[-1])
    result = abc[:offset].rstrip() + '\n' + '\n'.join(block + restore) + '\n' + abc[offset:]
    require_valid(parse_abc(result), native=True)
    following_section = next((s.id for s in score.sections if s.span.start == offset), None)
    placement = 'before ' + following_section if following_section else 'after the generated music'
    if protected_boundary:
        placement += ' (the preferred boundary has a crossing tie)'
    return result, placement


def ensure_audio_sections(abc, anchors, main_theme=None):
    score = parse_abc(abc)
    require_valid(score, native=True)
    notes = []
    sources = {}
    for anchor in anchors:
        if anchor.mode == 'AI':
            continue
        source = anchor.abc if anchor.abc.strip() else sources.get(anchor.source, '')
        if not source:
            raise ValueError(f'Cannot reserve {anchor.section}: missing melody source {anchor.source!r}')
        source_score = parse_abc(source)
        require_valid(source_score)
        _, bars = _tones(source_score, anchor.source_voice)
        count = 1 if anchor.occurrence == 'all' else int(anchor.occurrence)
        present = sum(section.name == anchor.section for section in parse_abc(abc).sections)
        for occurrence in range(present + 1, count + 1):
            abc, placement = _insert_section(abc, anchor.section, bars)
            notes.append(f'Reserved missing {anchor.section}#{occurrence}: {len(bars)} complete bars; '
                         f'{placement}; the enabled audio fills its target voice during composition.')
        for section in parse_abc(abc).sections:
            if section.name == anchor.section and (anchor.occurrence == 'all' or section.occurrence == count):
                sources[section.id] = source
    if main_theme is not None:
        try:
            plan_main_theme(abc, main_theme.score.source, main_theme.voice_id, reserved=anchors)
        except ValueError as error:
            if not str(error).startswith('Main theme has '):
                raise
            _, bars = _tones(main_theme.score, main_theme.voice_id)
            occurrence = 1 + sum(s.name == 'theme' for s in parse_abc(abc).sections)
            abc, placement = _insert_section(abc, 'theme', bars * 2)
            # Give the new melodic space its actual theme, so the usual planner can
            # select it without replacing a generated instrumental passage.
            fill = MelodyAnchor('theme', str(occurrence), main_theme.score.source,
                fit_policy='repeat', transpose_policy='none', harmony_policy='keep_base',
                source_voice=main_theme.voice_id, target_voice='Vocal')
            abc = compose_song(abc, (fill,), transpose_policy='none').abc
            notes.append(f'Reserved theme#{occurrence}: {len(bars) * 2} bars for the complete main theme and a return; {placement}.')
    return abc, notes
