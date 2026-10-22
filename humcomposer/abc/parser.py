"""Conservative parser for the observed two-voice YuE2/SheetSage2 ABC dialect.

This is an independent implementation, not a complete ABC 2.1 interpreter.
Unrecognized timing syntax is an error instead of being silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
import re

from .model import (
    ChordSymbol, ContextChange, Event, Header, KeySignature, Measure, Meter,
    Note, Rest, Score, Section, SectionVoiceRange, SourceSpan, Tempo, Voice,
    score_fingerprint,
)


class ABCParseError(ValueError):
    def __init__(self, code: str, message: str, offset: int = 0):
        self.code = code
        self.offset = offset
        super().__init__(f"{code} at offset {offset}: {message}")


_MAJOR_FIFTHS = {"Cb": -7, "Gb": -6, "Db": -5, "Ab": -4, "Eb": -3,
                 "Bb": -2, "F": -1, "C": 0, "G": 1, "D": 2, "A": 3,
                 "E": 4, "B": 5, "F#": 6, "C#": 7}
_MINOR_FIFTHS = {"Ab": -7, "Eb": -6, "Bb": -5, "F": -4, "C": -3,
                 "G": -2, "D": -1, "A": 0, "E": 1, "B": 2, "F#": 3,
                 "C#": 4, "G#": 5, "D#": 6, "A#": 7}
_PITCHES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SECTIONS = frozenset({
    "silence", "intro", "outro", "verse", "chorus", "bridge", "pre-chorus",
    "post-chorus", "interlude", "fade-out", "loop", "rap", "preshot",
    "irregular", "instrumental", "intro and verse", "pre-chorus and chorus",
    "verse and pre-chorus", "solo", "theme", "development", "variation", "pre-outro", "custom",
})
_NOTE = re.compile(r"(?P<acc>\^{1,2}|_{1,2}|=)?(?P<letter>[A-Ga-gz])(?P<oct>[,']*)")
_LENGTH = re.compile(r"(?:\d+(?:/\d*|/{2,})?|/+\d*)")
_FIELD = re.compile(r"^([A-Za-z]):\s*(.*)$")
MAX_MEASURES = 16384
MAX_EVENTS = 100000
MAX_SOURCE_CHARS = 2000000


def normalize_section_name(value: str) -> str:
    normalized = " ".join(value.strip().lower().replace("_", " ").split())
    return {"pre chorus": "pre-chorus", "prechorus": "pre-chorus",
            "post chorus": "post-chorus", "postchorus": "post-chorus"}.get(normalized, normalized)


def parse_key(value: str, offset: int = 0) -> KeySignature:
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(?:\s*(maj(?:or)?|m|min(?:or)?))?", value.strip())
    if not match:
        raise ABCParseError("unsupported_key", f"Unsupported key {value!r}; major/minor only", offset)
    tonic = match[1].upper() + match[2]
    mode = "minor" if match[3] in {"m", "min", "minor"} else "major"
    table = _MINOR_FIFTHS if mode == "minor" else _MAJOR_FIFTHS
    if tonic not in table:
        raise ABCParseError("unsupported_key", f"Key {value!r} exceeds seven accidentals", offset)
    return KeySignature(tonic, mode, table[tonic])


def parse_meter(value: str, offset: int = 0) -> Meter:
    value = {"C": "4/4", "C|": "2/2"}.get(value.strip(), value.strip())
    match = re.fullmatch(r"(\d+)/(\d+)", value)
    if not match or int(match[1]) <= 0 or int(match[2]) <= 0:
        raise ABCParseError("unsupported_meter", f"Expected a positive meter, got {value!r}", offset)
    denominator = int(match[2])
    if denominator & (denominator - 1):
        raise ABCParseError("unsupported_meter", "Meter denominator must be a power of two", offset)
    return Meter(int(match[1]), denominator)


def _fraction(value: str, offset: int) -> Fraction:
    try:
        result = Fraction(value.strip())
    except (ValueError, ZeroDivisionError) as exc:
        raise ABCParseError("invalid_fraction", f"Invalid fraction {value!r}", offset) from exc
    if result <= 0:
        raise ABCParseError("invalid_fraction", "Duration/tempo must be positive", offset)
    return result


def parse_tempo(value: str, offset: int = 0) -> Tempo:
    match = re.fullmatch(r"\s*(?:(\d+/\d+)\s*=\s*)?(\d+(?:\.\d+)?)\s*", value)
    if not match:
        raise ABCParseError("unsupported_tempo", "Expected Q:1/4=120 or Q:120", offset)
    return Tempo(_fraction(match[1] or "1/4", offset), _fraction(match[2], offset))


def _length(value: str, offset: int) -> Fraction:
    if not value:
        return Fraction(1)
    if re.fullmatch(r"\d*/*", value) and "/" in value:
        numerator, _, slashes = value.partition("/")
        return _fraction(numerator or "1", offset) / (2 ** (1 + len(slashes)))
    if value.startswith("/"):
        if value.count("/") != 1:
            raise ABCParseError("unsupported_duration", f"Mixed repeated slash length {value!r}", offset)
        value = "1" + value
    return _fraction(value, offset)


@dataclass
class _VoiceState:
    id: str
    meter: Meter
    key: KeySignature
    unit: Fraction
    tempo: Tempo | None
    measures: list[Measure] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    onset: Fraction = Fraction()
    elapsed: Fraction = Fraction()
    start: int | None = None
    last_end: int = 0
    measure_key: KeySignature | None = None
    measure_meter: Meter | None = None
    accidentals: dict[str, int] = field(default_factory=dict)
    pending_tie: Note | None = None
    section_id: str = ""
    rest_count: int = 1


@dataclass
class _SectionState:
    name: str
    occurrence: int
    start: int

    @property
    def id(self) -> str:
        return f"{self.name}#{self.occurrence}"


class _Parser:
    def __init__(self, source: str):
        self.source = source
        self.headers: list[Header] = []
        self.changes: list[ContextChange] = []
        self.voices: dict[str, _VoiceState] = {}
        self.selected: str | None = None
        self.meter: Meter | None = None
        self.key: KeySignature | None = None
        self.unit: Fraction | None = None
        self.tempo: Tempo | None = None
        self.in_body = False
        self.seen_x = False
        self.sections: list[_SectionState] = []
        self.event_count = 0

    def current(self, offset: int) -> _VoiceState:
        if self.meter is None or self.key is None or self.unit is None:
            raise ABCParseError("missing_context", "M:, L:, and K: are required before music", offset)
        voice_id = self.selected or "1"
        if voice_id not in self.voices:
            if len(self.voices)>=16:
                raise ABCParseError('resource_limit', 'At most 16 voice streams are supported', offset)
            self.voices[voice_id] = _VoiceState(voice_id, self.meter, self.key, self.unit, self.tempo)
        self.selected = voice_id
        return self.voices[voice_id]

    def begin(self, state: _VoiceState, offset: int) -> None:
        self.event_count += 1
        if self.event_count>MAX_EVENTS:
            raise ABCParseError('resource_limit', 'ABC event limit exceeded', offset)
        if not self.sections:
            self.sections.append(_SectionState("unsectioned", 1, offset))
        if state.start is None:
            state.start = offset
            state.measure_key = state.key
            state.measure_meter = state.meter
            state.section_id = self.sections[-1].id

    def finish(self, state: _VoiceState, end: int) -> None:
        if not state.events:
            if state.start is not None:
                raise ABCParseError("empty_measure", "A context-only measure has no duration", state.start)
            return
        span = SourceSpan(state.start if state.start is not None else end, end)
        if len(state.measures)+state.rest_count>MAX_MEASURES:
            raise ABCParseError('resource_limit', 'Expanded measure limit exceeded', span.start)
        if state.rest_count > 1:
            rest = next(event for event in state.events if isinstance(event, Rest))
            for index in range(state.rest_count):
                onset = state.onset + index * state.meter.duration
                state.measures.append(Measure(
                    len(state.measures), onset, state.meter.duration, state.meter,
                    state.measure_key or state.key,
                    (Rest(onset, state.meter.duration, rest.span),), span,
                    state.section_id, index, state.rest_count,
                ))
        else:
            state.measures.append(Measure(
                len(state.measures), state.onset, state.elapsed,
                state.measure_meter or state.meter, state.measure_key or state.key,
                tuple(state.events), span, state.section_id,
            ))
        state.onset += state.elapsed
        state.elapsed = Fraction()
        state.events = []
        state.start = None
        state.measure_key = None
        state.measure_meter = None
        state.accidentals = {}
        state.rest_count = 1

    def section_marker(self, text: str, offset: int) -> None:
        label = normalize_section_name(text)
        explicit = label.startswith("section:")
        if explicit:
            label = normalize_section_name(label[8:])
            if not label:
                raise ABCParseError("invalid_section", "Explicit section label is empty", offset)
        if label not in _SECTIONS and not explicit:
            return
        if any(voice.events for voice in self.voices.values()):
            raise ABCParseError("section_inside_measure", "Section boundaries must be between complete bars", offset)
        occurrence = 1 + sum(section.name == label for section in self.sections)
        self.sections.append(_SectionState(label, occurrence, offset))

    def context(self, name: str, value: str, span: SourceSpan, inline: bool = False) -> None:
        if name == "M":
            parsed = parse_meter(value, span.start)
        elif name == "K":
            parsed = parse_key(value, span.start)
        elif name == "L":
            parsed = _fraction(value, span.start)
        else:
            parsed = parse_tempo(value, span.start)
        if not self.in_body:
            setattr(self, {"M": "meter", "K": "key", "L": "unit", "Q": "tempo"}[name], parsed)
            self.changes.append(ContextChange(None, name, parsed, Fraction(), span))
            if name == "K":
                self.in_body = True
            return
        state = self.current(span.start)
        if name == "M" and state.elapsed:
            raise ABCParseError("meter_inside_measure", "Meter changes must occur at bar boundaries", span.start)
        self.changes.append(ContextChange(state.id, name, parsed, state.onset + state.elapsed, span))
        setattr(state, {"M": "meter", "K": "key", "L": "unit", "Q": "tempo"}[name], parsed)
        if name == "K":
            state.accidentals = {}
            if not state.elapsed:
                state.measure_key = parsed
        if name == "M" and not state.elapsed:
            state.measure_meter = parsed

    def field_line(self, name: str, value: str, span: SourceSpan) -> None:
        self.headers.append(Header(name, value, span))
        if name == "X":
            if self.seen_x:
                raise ABCParseError("multiple_tunes", "Only one X: tune is supported", span.start)
            self.seen_x = True
        elif name == "V":
            if re.search(r"\b(?:octave|transpose|t)\s*=|[+-]8\b", value):
                raise ABCParseError("unsupported_voice_shift", "Voice pitch shifts must be resolved explicitly", span.start)
            match = re.match(r"([A-Za-z0-9_-]+)(?:\s+.*)?$", value.strip())
            if not match:
                raise ABCParseError("invalid_voice", f"Invalid voice declaration {value!r}", span.start)
            self.selected = match[1]
            # Header declarations select no musical stream; initial K closes the header.
            if self.in_body:
                self.current(span.start)
        elif name in {"M", "L", "K", "Q"}:
            self.context(name, value, span)
        elif name in {"P", "I", "U", "m", "w"}:
            raise ABCParseError("unsupported_field", f"Field {name}: may alter playback and is unsupported", span.start)

    def music(self, line: str, offset: int) -> None:
        state = self.current(offset)
        index = 0
        while index < len(line):
            char = line[index]
            position = offset + index
            if char.isspace():
                index += 1
                continue
            if char == "%":
                break
            if line.startswith(("|:", ":|", "::"), index):
                raise ABCParseError("unsupported_repeat", "Repeat playback is unsupported; expand repeats explicitly", position)
            if char == "|" or line.startswith("[|", index):
                end = index + (2 if line.startswith("[|", index) else 1)
                while end < len(line) and line[end] in "|]":
                    end += 1
                self.finish(state, offset + end)
                index = end
                continue
            if char == "[":
                match = re.match(r"\[([KMLQV]):([^\]]+)\]", line[index:])
                if not match:
                    raise ABCParseError("unsupported_bracket", "Note stacks, repeats, and unknown inline fields are unsupported", position)
                span = SourceSpan(position, position + len(match[0]))
                if match[1] == "V":
                    if state.events:
                        raise ABCParseError("voice_inside_measure", "Switch voices only at bar boundaries", position)
                    self.field_line("V", match[2], span)
                    state = self.current(position)
                else:
                    self.begin(state, position)
                    self.context(match[1], match[2], span, inline=True)
                index += len(match[0])
                state.last_end = offset + index
                continue
            self.begin(state, position)
            if char == '"':
                end = line.find('"', index + 1)
                if end < 0:
                    raise ABCParseError("unclosed_chord", "Unclosed quoted chord symbol", position)
                chord = line[index + 1:end]
                if not chord or "\\" in chord:
                    raise ABCParseError("unsupported_chord_text", "Empty/escaped quoted symbols are unsupported", position)
                state.events.append(ChordSymbol(chord, state.onset + state.elapsed, SourceSpan(position, offset + end + 1)))
                index = end + 1
                state.last_end = offset + index
                continue
            if char == "Z":
                match = re.match(r"Z(\d*)", line[index:])
                assert match is not None
                count = int(match[1] or "1")
                if count < 1:
                    raise ABCParseError("invalid_rest", "Full-bar rest count must be positive", position)
                if count>MAX_MEASURES:
                    raise ABCParseError('resource_limit', 'Compressed rest exceeds measure limit', position)
                if state.events or state.elapsed or state.pending_tie:
                    raise ABCParseError("invalid_multirest", "Z<n> must occupy otherwise empty complete bars", position)
                duration = state.meter.duration * count
                state.rest_count = count
                state.elapsed = duration
                state.events.append(Rest(state.onset, duration, SourceSpan(position, position + len(match[0]))))
                index += len(match[0])
                state.last_end = offset + index
                continue
            if state.rest_count > 1 or any(isinstance(event, Rest) and event.span.text(self.source).startswith("Z") for event in state.events):
                raise ABCParseError("invalid_multirest", "No music may follow Z<n> before its bar line", position)
            match = _NOTE.match(line, index)
            if not match:
                raise ABCParseError("unsupported_syntax", f"Unsupported rhythmic/music token {line[index:index + 12]!r}", position)
            end = match.end()
            length_match = _LENGTH.match(line, end)
            duration = state.unit * _length(length_match[0] if length_match else "", position)
            if length_match:
                end = length_match.end()
            tied = end < len(line) and line[end] == "-"
            if tied:
                end += 1
            span = SourceSpan(position, offset + end)
            onset = state.onset + state.elapsed
            if match["letter"] == "z":
                if match["acc"] or match["oct"] or tied or state.pending_tie:
                    raise ABCParseError("invalid_rest", "Rests cannot carry pitch modifiers or participate in ties", position)
                event = Rest(onset, duration, span)
            else:
                letter = match["letter"].upper()
                octave = 5 if match["letter"].islower() else 4
                octave += match["oct"].count("'") - match["oct"].count(",")
                accidental = None
                if match["acc"]:
                    accidental = match["acc"].count("^") - match["acc"].count("_")
                    state.accidentals[letter] = accidental
                natural = 12 * (octave + 1) + _PITCHES[letter]
                midi = natural + state.accidentals.get(letter, state.key.accidentals.get(letter, 0))
                previous = state.pending_tie
                if previous is not None:
                    if accidental is None and letter == previous.letter and abs(midi - previous.midi) <= 2:
                        midi = previous.midi
                    if midi != previous.midi:
                        raise ABCParseError("broken_tie", "A tied continuation must preserve the sounding pitch", position)
                if not 0 <= midi <= 127:
                    raise ABCParseError("pitch_out_of_range", f"Pitch {midi} is outside MIDI 0..127", position)
                event = Note(midi, letter, accidental, onset, duration, previous is not None, tied, span)
                state.pending_tie = event if tied else None
            state.events.append(event)
            state.elapsed += duration
            index = end
            state.last_end = offset + index

    def parse(self) -> Score:
        offset = 0
        for physical_line in self.source.splitlines(keepends=True):
            line = physical_line.rstrip("\r\n")
            stripped = line.lstrip()
            indentation = len(line) - len(stripped)
            if stripped.startswith("%%"):
                raise ABCParseError("unsupported_directive", "ABC directives require an explicit supported interpretation", offset + indentation)
            if stripped.startswith("%"):
                self.section_marker(stripped[1:].strip(), offset + indentation)
            elif stripped:
                match = _FIELD.match(stripped)
                if match:
                    value = match[2].split("%", 1)[0].rstrip()
                    self.field_line(match[1], value, SourceSpan(offset + indentation, offset + len(line)))
                else:
                    self.music(line, offset)
            offset += len(physical_line)
        for state in self.voices.values():
            if state.events:
                self.finish(state, state.last_end)
        voices = tuple(Voice(state.id, tuple(state.measures)) for state in self.voices.values())
        sections = []
        for index, section in enumerate(self.sections):
            ranges = []
            for voice in voices:
                indices = [measure.index for measure in voice.measures if measure.section_id == section.id]
                if indices:
                    ranges.append(SectionVoiceRange(voice.id, min(indices), max(indices) + 1))
            end = self.sections[index + 1].start if index + 1 < len(self.sections) else len(self.source)
            sections.append(Section(section.name, section.occurrence, SourceSpan(section.start, end), tuple(ranges)))
        score = Score(self.source, tuple(self.headers), voices, tuple(sections), tuple(self.changes))
        return replace(score, source_model_digest=score_fingerprint(score))


def parse_abc(source: str) -> Score:
    if not isinstance(source, str):
        raise TypeError("ABC source must be a string")
    if not source.strip():
        raise ABCParseError("empty_score", "ABC source is empty")
    if len(source)>MAX_SOURCE_CHARS:
        raise ABCParseError('resource_limit', 'ABC source exceeds 2,000,000 characters')
    return _Parser(source).parse()
