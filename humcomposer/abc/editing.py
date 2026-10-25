"""Exact, monophonic interval edits that preserve other source spans and contexts."""
from dataclasses import dataclass
from fractions import Fraction

from .model import Note, Rest, ChordSymbol
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
    for bar in voice.measures:
        for event in bar.events:
            if isinstance(event, (Note, Rest)):
                if isinstance(event, Note) and event.tie_from_previous:
                    previous = tones.pop()
                    tones.append(Tone(previous.start, event.onset + event.duration, event.midi))
                else:
                    tones.append(Tone(event.onset, event.onset + event.duration,
                                      event.midi if isinstance(event, Note) else None))
    return tones


def _paint(tones: list[Tone], start: Fraction, end: Fraction, midi: int | None) -> list[Tone]:
    result = []
    for tone in tones:
        if tone.end <= start or tone.start >= end:
            result.append(tone)
        else:
            if tone.start < start:
                result.append(Tone(tone.start, start, tone.midi))
            if tone.end > end:
                result.append(Tone(end, tone.end, tone.midi))
    result.append(Tone(start, end, midi))
    return sorted(result, key=lambda tone: tone.start)


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


def _target(score, voice_id: str, measure: int):
    voice = score.voice(voice_id)
    if isinstance(measure, bool) or not isinstance(measure, int) or not 0 <= measure < len(voice.measures):
        raise ValueError('Unknown measure')
    return voice, voice.measures[measure]


def paint_interval(abc: str, voice_id: str, measure: int, offset: Fraction,
                   duration: Fraction, midi: int | None, move_from: tuple | None = None) -> str:
    score = parse_abc(abc)
    require_valid(score)
    voice, bar = _target(score, voice_id, measure)
    if midi is not None and (isinstance(midi, bool) or not isinstance(midi, int) or not 0 <= midi <= 127):
        raise ValueError('Pitch must be MIDI 0..127 or null for a rest')
    if offset < 0 or duration <= 0 or offset + duration > bar.duration:
        raise ValueError('The note must fit inside the selected measure')
    if bar.rest_group_count > 1:
        expanded = rewrite_measures(score, {(voice_id, measure): 'Z|'})
        return paint_interval(expanded, voice_id, measure, offset, duration, midi, move_from)
    before = _tones(voice)
    after = before
    if move_from is not None:
        old_offset, old_duration = move_from
        if old_offset < 0 or old_duration <= 0 or old_offset + old_duration > bar.duration:
            raise ValueError('Invalid source interval')
        after = _paint(after, bar.onset + old_offset, bar.onset + old_offset + old_duration, None)
    after = _paint(after, bar.onset + offset, bar.onset + offset + duration, midi)
    edits = []
    nearby = voice.measures[max(0, measure - 1):measure + 2]
    start, end = nearby[0].onset, nearby[-1].onset + nearby[-1].duration
    before = [t for t in before if t.start < end and t.end > start]
    after = [t for t in after if t.start < end and t.end > start]
    for current in nearby:
        rhythmic = [e for e in current.events if isinstance(e, (Note, Rest))]
        if not any(_parts(before, e.onset, e.onset + e.duration) !=
                   _parts(after, e.onset, e.onset + e.duration) for e in rhythmic):
            continue
        # Explicit pitches throughout the touched bar prevent accidental carry from
        # changing untouched notes. Contexts, chord symbols, comments and spacing stay.
        for event in rhythmic:
            replacement = ''.join(_token(pitch, end - start, _unit_at(score, voice_id, start), tie_out)
                                  for start, end, pitch, _, tie_out in
                                  _parts(after, event.onset, event.onset + event.duration))
            edits.append(TextEdit(event.span, replacement))
    result = serialize(score, edits)
    require_valid(parse_abc(result))
    return result


def edit_chord(abc: str, voice_id: str, measure: int, offset: Fraction, chord: str) -> str:
    if not isinstance(chord, str) or len(chord) > 128 or any(c in chord for c in '"\\\r\n'):
        raise ValueError('Chord text must be at most 128 characters without quotes, escapes or newlines')
    score = parse_abc(abc)
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
        event = next(e for e in bar.events if isinstance(e, (Note, Rest)) and e.onset <= at < e.onset + e.duration)
        if at == event.onset:
            edits = [TextEdit(type(event.span)(event.span.start, event.span.start), quoted)]
        else:
            tone = next(t for t in _tones(voice) if t.start <= at < t.end)
            unit = _unit_at(score, voice_id, at)
            body = (_token(tone.midi, at - event.onset, unit, tone.midi is not None) + quoted +
                    _token(tone.midi, event.onset + event.duration - at, unit, tone.end > event.onset + event.duration))
            edits = []
            tones = _tones(voice)
            for current in bar.events:
                if not isinstance(current, (Note, Rest)):
                    continue
                replacement = body if current is event else ''.join(
                    _token(midi, end - start, _unit_at(score, voice_id, start), tie_out)
                    for start, end, midi, _, tie_out in _parts(tones, current.onset, current.onset + current.duration))
                edits.append(TextEdit(current.span, replacement))
    result = serialize(score, edits)
    require_valid(parse_abc(result))
    return result


def append_measure(abc: str) -> str:
    score = parse_abc(abc)
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
    require_valid(parse_abc(result))
    return result
