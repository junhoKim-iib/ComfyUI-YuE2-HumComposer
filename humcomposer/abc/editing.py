"""Exact interval edits that preserve other source spans and contexts."""
from dataclasses import dataclass
from fractions import Fraction

from .model import Note, NoteStack, Rest, SourceSpan
from .parser import parse_abc
from .serializer import TextEdit, serialize, rewrite_measures
from .validation import require_valid


@dataclass(frozen=True)
class Tone:
    start: Fraction
    end: Fraction
    midi: int | None


def _tones(voice) -> list[Tone]:
    tones = []
    active = {}
    for bar in voice.measures:
        for event in bar.events:
            if isinstance(event, Rest):
                tones.append(Tone(event.onset, event.onset + event.duration, None))
                active = {}
            elif isinstance(event, (Note, NoteStack)):
                pending = {}
                for note in event.notes if isinstance(event, NoteStack) else (event,):
                    if note.tie_from_previous:
                        index = active[note.midi]
                        tones[index] = Tone(tones[index].start, note.onset + note.duration, note.midi)
                    else:
                        index = len(tones)
                        tones.append(Tone(note.onset, note.onset + note.duration, note.midi))
                    if note.tie_to_next:
                        pending[note.midi] = index
                active = pending
    return sorted(tones, key=lambda tone: (tone.start, -1 if tone.midi is None else tone.midi))


def _cut(tones: list[Tone], start: Fraction, end: Fraction, only_pitch: int | None = None) -> list[Tone]:
    result = []
    for tone in tones:
        if tone.end <= start or tone.start >= end or (only_pitch is not None and tone.midi not in (None, only_pitch)):
            result.append(tone)
        else:
            if tone.start < start:
                result.append(Tone(tone.start, start, tone.midi))
            if tone.end > end:
                result.append(Tone(end, tone.end, tone.midi))
    return result


def _paint(tones: list[Tone], start: Fraction, end: Fraction, midi: int | None,
           additive: bool = False, erase_pitch: int | None = None) -> list[Tone]:
    result = _cut(tones, start, end, midi if additive and midi is not None else erase_pitch)
    if midi is not None:
        result.append(Tone(start, end, midi))
    return sorted(result, key=lambda tone: (tone.start, -1 if tone.midi is None else tone.midi))


def _parts(tones: list[Tone], start: Fraction, end: Fraction) -> list[tuple]:
    return [(max(start, t.start), min(end, t.end), t.midi,
             t.midi is not None and t.start < start, t.midi is not None and t.end > end)
            for t in tones if t.start < end and t.end > start]


def _unit_at(score, voice: str, onset: Fraction) -> Fraction:
    return next(c.value for c in reversed(score.changes)
                if c.kind == 'L' and c.voice_id in (None, voice) and c.onset <= onset)


def _pitch(midi: int | None) -> str:
    if midi is None:
        return 'z'
    name = ('=C', '^C', '=D', '_E', '=E', '=F', '^F', '=G', '_A', '=A', '_B', '=B')[midi % 12]
    octave = midi // 12 - 1
    return name[:-1] + name[-1].lower() + "'" * (octave - 5) if octave >= 5 else name + ',' * (4 - octave)


def _token(midi: int | None, duration: Fraction, unit: Fraction, tie: bool) -> str:
    length = duration / unit
    suffix = '' if length == 1 else str(length)
    return _pitch(midi) + suffix + ('-' if midi is not None and tie else '')


def _render_interval(tones: list[Tone], start: Fraction, end: Fraction, score, voice: str) -> str:
    overlapping = [tone for tone in tones if tone.start < end and tone.end > start]
    boundaries = sorted({start, end} | {max(start, tone.start) for tone in overlapping} |
                        {min(end, tone.end) for tone in overlapping})
    tokens = []
    for left, right in zip(boundaries, boundaries[1:]):
        sounding = sorted((tone for tone in overlapping if tone.midi is not None and
                           tone.start <= left and tone.end >= right), key=lambda tone: tone.midi)
        unit = _unit_at(score, voice, left)
        if len(sounding) < 2:
            tone = sounding[0] if sounding else Tone(left, right, None)
            tokens.append(_token(tone.midi, right - left, unit, tone.end > right))
        else:
            length = (right - left) / unit
            pitches = ''.join(_pitch(tone.midi) + ('-' if tone.end > right else '') for tone in sounding)
            tokens.append('[' + pitches + ']' + ('' if length == 1 else str(length)))
    return ''.join(tokens)


def _target(score, voice_id: str, measure: int):
    voice = score.voice(voice_id)
    if isinstance(measure, bool) or not isinstance(measure, int) or not 0 <= measure < len(voice.measures):
        raise ValueError('Unknown measure')
    return voice, voice.measures[measure]


def paint_interval(abc: str, voice_id: str, measure: int, offset: Fraction,
                   duration: Fraction, midi: int | None, move_from: tuple | None = None,
                   *, additive: bool = False, erase_pitch: int | None = None) -> str:
    score = parse_abc(abc, polyphonic=True)
    require_valid(score)
    voice, bar = _target(score, voice_id, measure)
    if midi is not None and (isinstance(midi, bool) or not isinstance(midi, int) or not 0 <= midi <= 127):
        raise ValueError('Pitch must be MIDI 0..127 or null for a rest')
    if erase_pitch is not None and (isinstance(erase_pitch, bool) or not isinstance(erase_pitch, int) or not 0 <= erase_pitch <= 127):
        raise ValueError('Source pitch must be MIDI 0..127')
    if offset < 0 or duration <= 0 or offset + duration > bar.duration:
        raise ValueError('The note must fit inside the selected measure')
    if bar.rest_group_count > 1:
        expanded = rewrite_measures(score, {(voice_id, measure): 'Z|'})
        return paint_interval(expanded, voice_id, measure, offset, duration, midi, move_from,
                              additive=additive, erase_pitch=erase_pitch)
    before = _tones(voice)
    after = before
    if move_from is not None:
        old_offset, old_duration = move_from
        if old_offset < 0 or old_duration <= 0 or old_offset + old_duration > bar.duration:
            raise ValueError('Invalid source interval')
        after = _cut(after, bar.onset + old_offset, bar.onset + old_offset + old_duration, erase_pitch)
    after = _paint(after, bar.onset + offset, bar.onset + offset + duration, midi,
                   additive, erase_pitch if move_from is None else None)
    edits = []
    nearby = voice.measures[max(0, measure - 1):measure + 2]
    start, end = nearby[0].onset, nearby[-1].onset + nearby[-1].duration
    before = [t for t in before if t.start < end and t.end > start]
    after = [t for t in after if t.start < end and t.end > start]
    for current in nearby:
        rhythmic = [e for e in current.events if isinstance(e, (Note, NoteStack, Rest))]
        if not any(_parts(before, e.onset, e.onset + e.duration) !=
                   _parts(after, e.onset, e.onset + e.duration) for e in rhythmic):
            continue
        # Explicit pitches throughout the touched bar prevent accidental carry from
        # changing untouched notes. Contexts, chord symbols, comments and spacing stay.
        for event in rhythmic:
            replacement = _render_interval(after, event.onset, event.onset + event.duration, score, voice_id)
            edits.append(TextEdit(event.span, replacement))
    result = serialize(score, edits)
    require_valid(parse_abc(result, polyphonic=True))
    return result


def edit_chord(abc: str, voice_id: str, measure: int, offset: Fraction, chord: str) -> str:
    if not isinstance(chord, str) or len(chord) > 128 or any(c in chord for c in '"\\\r\n'):
        raise ValueError('Chord text must be at most 128 characters without quotes, escapes or newlines')
    score = parse_abc(abc, polyphonic=True)
    require_valid(score)
    voice, bar = _target(score, voice_id, measure)
    if not 0 <= offset < bar.duration:
        raise ValueError('Chord position must be inside the measure')
    at = bar.onset + offset
    existing = next((c for c in bar.chords if c.onset == at), None)
    quoted = '"' + chord + '"' if chord else ''
    if existing:
        edits = [TextEdit(existing.span, quoted)]
    elif not chord:
        return abc
    elif bar.rest_group_count > 1:
        return edit_chord(rewrite_measures(score, {(voice_id, measure): 'Z|'}), voice_id, measure, offset, chord)
    else:
        event = next(e for e in bar.events if isinstance(e, (Note, NoteStack, Rest)) and e.onset <= at < e.onset + e.duration)
        if at == event.onset:
            edits = [TextEdit(type(event.span)(event.span.start, event.span.start), quoted)]
        else:
            edits = []
            tones = _tones(voice)
            body = (_render_interval(tones, event.onset, at, score, voice_id) + quoted +
                    _render_interval(tones, at, event.onset + event.duration, score, voice_id))
            for current in bar.events:
                if not isinstance(current, (Note, NoteStack, Rest)):
                    continue
                replacement = body if current is event else _render_interval(
                    tones, current.onset, current.onset + current.duration, score, voice_id)
                edits.append(TextEdit(current.span, replacement))
    result = serialize(score, edits)
    require_valid(parse_abc(result, polyphonic=True))
    return result


def append_measure(abc: str) -> str:
    score = parse_abc(abc, polyphonic=True)
    require_valid(score)
    edits = []
    for voice in score.voices:
        if not voice.measures:
            continue
        bar = voice.measures[-1]
        end = bar.span.end
        meter = next(c.value for c in reversed(score.changes)
                     if c.kind == 'M' and c.voice_id in (None, voice.id) and c.onset <= voice.duration)
        token = _token(None, meter.duration, _unit_at(score, voice.id, voice.duration), False) + '|'
        if not bar.span.text(abc).rstrip().endswith(('|', ']')):
            token = '|' + token
        edits.append(TextEdit(type(bar.span)(end, end), token))
    result = serialize(score, edits)
    require_valid(parse_abc(result, polyphonic=True))
    return result


def add_voice(abc: str, source_voice: str, name: str = '', clef: str = 'treble') -> tuple[str, str]:
    if not isinstance(name, str) or len(name) > 64 or any(char in name for char in '"\\%\r\n'):
        raise ValueError('Part name must be at most 64 characters without quotes, escapes, percent signs or newlines')
    if clef not in ('treble', 'bass'):
        raise ValueError('Choose treble or bass clef')
    score = parse_abc(abc, polyphonic=True)
    require_valid(score)
    reference = score.voice(source_voice)
    ids = {voice.id for voice in score.voices}
    if len(ids) >= 16:
        raise ValueError('At most 16 parts are supported')
    voice_id = next((candidate for candidate in ('Vocal', 'Ins') if candidate not in ids), None)
    if voice_id is None:
        number = 1
        while f'Part{number}' in ids:
            number += 1
        voice_id = f'Part{number}'
    label = name.strip() or voice_id
    changes = [change for change in score.changes if change.voice_id in (None, source_voice)]
    current_context = {change.kind: change.value for change in score.changes if change.voice_id is None}

    def context(kind, value):
        if kind == 'K':
            value = value.text
        elif kind == 'M':
            value = f'{value.numerator}/{value.denominator}'
        elif kind == 'Q':
            value = f'{value.beat}={value.bpm}'
        return f'[{kind}:{value}]'

    edits = []
    for section in score.sections:
        selected = section.range_for(source_voice)
        bars = []
        for bar in reference.measures[selected.start_measure:selected.end_measure]:
            body = []
            for kind in ('M', 'L', 'Q', 'K'):
                active = next((change for change in reversed(changes) if change.kind == kind and change.onset <= bar.onset), None)
                if active is not None and active.value != current_context.get(kind):
                    body.append(context(kind, active.value))
                    current_context[kind] = active.value
            inside = [change for change in changes if bar.onset < change.onset < bar.onset + bar.duration]
            boundaries = sorted({bar.onset, bar.onset + bar.duration} | {change.onset for change in inside})
            for left, right in zip(boundaries, boundaries[1:]):
                for change in inside:
                    if change.onset == left and change.value != current_context.get(change.kind):
                        body.append(context(change.kind, change.value))
                        current_context[change.kind] = change.value
                body.append(_token(None, right - left, _unit_at(score, source_voice, left), False))
            bars.append(''.join(body) + '|')
        preceding = max((bar for voice in score.voices for bar in voice.measures
                         if bar.span.end <= section.span.end), key=lambda bar: bar.span.end)
        ending = preceding.span.text(abc).rstrip()
        separator = '\n' if ending.endswith(('|', '|]')) else '|\n'
        text = separator + f'V:{voice_id} clef={clef} name="{label}"\n' + '\n'.join(bars) + '\n'
        edits.append(TextEdit(SourceSpan(section.span.end, section.span.end), text))
    result = serialize(score, edits)
    require_valid(parse_abc(result, polyphonic=True))
    return result, voice_id
