"""Adapt the existing ABC model to the score widget; never rewrite the source."""
from fractions import Fraction
import re

from ..humcomposer.abc.model import ChordSymbol, Note, NoteStack, Rest
from ..humcomposer.abc.parser import ABCParseError, parse_abc
from ..humcomposer.abc.validation import validate_score
from .analyze import CATEGORY


def _rhythm(duration: Fraction) -> list[tuple[Fraction, int, int]]:
    candidates = sorted((
        (Fraction(2 ** (dots + 1) - 1, denominator * 2 ** dots), denominator, dots)
        for denominator in (1, 2, 4, 8, 16, 32, 64, 128) for dots in range(4)
    ), reverse=True)
    remaining = duration
    parts = []
    if duration <= 16:
        for value, denominator, dots in candidates:
            while value <= remaining:
                parts.append((value, denominator, dots))
                remaining -= value
    return parts if not remaining else [(duration, 0, 0)]


def _ratio(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _roll_tones(bar) -> list[dict]:
    tones = []
    active = {}
    for event in bar.events:
        if isinstance(event, Rest):
            tones.append({'offset': _ratio(event.onset - bar.onset), 'duration': _ratio(event.duration),
                          'midi': None})
            active = {}
        elif isinstance(event, (Note, NoteStack)):
            pending = {}
            for note in event.notes if isinstance(event, NoteStack) else (event,):
                if note.tie_from_previous and note.midi in active:
                    index = active[note.midi]
                    tones[index]['duration'] = _ratio(Fraction(*tones[index]['duration']) + note.duration)
                else:
                    index = len(tones)
                    tones.append({'offset': _ratio(note.onset - bar.onset), 'duration': _ratio(note.duration), 'midi': note.midi})
                if note.tie_to_next:
                    pending[note.midi] = index
            active = pending
    return tones


def _voice_metadata(score, voice_id: str) -> tuple[str, str]:
    name, clef = voice_id, 'treble'
    declared_clef = None
    for header in score.headers:
        if header.field != 'V' or header.value.split()[0] != voice_id:
            continue
        label = re.search(r'\bname\s*=\s*(?:"([^"]*)"|(\S+))', header.value)
        if label:
            name = label[1] if label[1] is not None else label[2]
        match = re.search(r'\bclef\s*=\s*(\S+)', header.value)
        if match:
            clef = match[1]
            if clef not in ('treble', 'bass'):
                raise ValueError(f'{voice_id}: unsupported clef {clef!r}; treble/bass only')
            if declared_clef is not None and clef != declared_clef:
                raise ValueError(f'{voice_id}: clef changes are not supported by the viewer')
            declared_clef = clef
    return name, clef


def _preview(abc: str) -> dict:
    score = parse_abc(abc, polyphonic=True)
    if not any(voice.measures for voice in score.voices):
        raise ValueError('No musical events found')
    messages = [f'{issue.severity.upper()} [{issue.code}] {issue.message}'
                for issue in validate_score(score) if issue.code != 'missing_sections']
    voices = []
    fractional_rhythm = False
    for voice in score.voices:
        if not voice.measures:
            continue
        name, clef = _voice_metadata(score, voice.id)
        changes = [c for c in score.changes if c.voice_id == voice.id and c.kind in ('K', 'Q')]
        change_index = 0
        measures = []
        for bar in voice.measures:
            events = []
            key = bar.key
            accidentals = {}
            while change_index < len(changes) and changes[change_index].onset < bar.onset:
                change_index += 1
            index = change_index
            while index < len(changes) and changes[index].onset < bar.onset + bar.duration:
                change = changes[index]
                if change.onset > bar.onset or change.kind == 'Q':
                    events.append((change.onset, change.span.start, change))
                index += 1
            change_index = index
            events.extend((item.onset, item.span.start, item) for event in bar.events
                          for item in (event.notes if isinstance(event, NoteStack) else (event,)))
            display = []
            for onset, _, event in sorted(events, key=lambda item: item[:2]):
                offset = onset - bar.onset
                if isinstance(event, ChordSymbol):
                    display.append({'kind': 'chord', 'offset': _ratio(offset), 'text': event.text})
                    continue
                if not isinstance(event, (Note, Rest)):
                    if event.kind == 'K':
                        display.append({'kind': 'key', 'offset': _ratio(offset),
                                        'fifths': event.value.fifths, 'previousFifths': key.fifths})
                        key = event.value
                        accidentals.clear()
                    else:
                        display.append({'kind': 'tempo', 'offset': _ratio(offset),
                                        'text': f'{event.value.beat} = {event.value.bpm}'})
                    continue
                note = {}
                if isinstance(event, Note):
                    # Written Cb and B# must keep their register even across MIDI octaves.
                    token = re.match(r'[\^_=]*([A-Ga-g])([,\x27]*)', event.span.text(abc))
                    letter = token[1].upper()
                    octave = (5 if token[1].islower() else 4) + token[2].count("'") - token[2].count(',')
                    step = (octave - 4) * 7 + 'CDEFGAB'.index(letter)
                    natural = 12 * (octave + 1) + {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[letter]
                    effective = event.midi - natural
                    expected = accidentals.get(step, key.accidentals.get(letter, 0))
                    accidental = effective if effective != expected and not event.tie_from_previous else None
                    accidentals[step] = effective
                    note = {'step': step, 'accidental': accidental, 'midi': event.midi}
                full_rest = isinstance(event, Rest) and event.duration == bar.meter.duration == bar.duration
                parts = [(event.duration, 1, 0)] if full_rest else _rhythm(event.duration)
                for part_index, (duration, denominator, dots) in enumerate(parts):
                    fractional_rhythm |= denominator == 0
                    display.append({'kind': 'note' if note else 'rest', 'offset': _ratio(offset),
                                    'sourceOffset': _ratio(event.onset - bar.onset),
                                    'sourceDuration': _ratio(event.duration),
                                    'duration': _ratio(duration), 'denominator': denominator, 'dots': dots,
                                    'fullRest': full_rest,
                                    'tieIn': bool(note) and (event.tie_from_previous or part_index > 0),
                                    'tieOut': bool(note) and (event.tie_to_next or part_index < len(parts) - 1),
                                    **(note if part_index == 0 else {**note, 'accidental': None})})
                    offset += duration
            measures.append({'index': bar.index, 'onset': _ratio(bar.onset), 'duration': _ratio(bar.duration),
                             'meter': [bar.meter.numerator, bar.meter.denominator], 'fifths': bar.key.fifths,
                             'section': bar.section_id, 'events': display,
                             'tones': _roll_tones(bar)})
        voices.append({'id': voice.id, 'name': name, 'clef': clef, 'measures': measures})
    grids = [[(bar.onset, bar.duration, bar.meter) for bar in voice.measures]
             for voice in score.voices if voice.measures]
    aligned = all(grid == grids[0] for grid in grids[1:])
    if not aligned:
        messages.append('성부의 마디 경계가 달라 성부별로 표시합니다.')
    if fractional_rhythm:
        messages.append('일반 음표로 나타낼 수 없는 음가는 마름모와 온음표 기준 분수로 표시합니다.')
    tempo = next((f'{c.value.beat} = {c.value.bpm}' for c in reversed(score.changes)
                  if c.kind == 'Q' and c.voice_id is None), '')
    return {'title': next((h.value for h in score.headers if h.field == 'T'), 'YuE2 Score'), 'tempo': tempo,
            'source': abc, 'voices': voices, 'aligned': aligned, 'messages': messages}


class ABCScoreViewer:
    CATEGORY = CATEGORY
    FUNCTION = 'preview'
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    DESCRIPTION = 'Display ABC as a local SVG staff score. Connect final_abc or SheetSage2 abc.'

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {'abc': ('STRING', {'forceInput': True})}}

    def preview(self, abc: str) -> dict:
        try:
            payload = _preview(abc)
        except (ABCParseError, ValueError) as error:
            payload = {'error': str(error), 'source': abc}
        return {'ui': {'score': [payload]}, 'result': ()}
