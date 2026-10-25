"""Immutable, source-backed ABC data; all musical times are whole-note units.

Use serializer text edits to modify a score. Replacing dataclass fields is useful
for calculations, but is deliberately not a supported way to serialize changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256


@dataclass(frozen=True, order=True)
class SourceSpan:
    start: int
    end: int

    def text(self, source: str) -> str:
        return source[self.start:self.end]


@dataclass(frozen=True)
class Meter:
    numerator: int
    denominator: int

    @property
    def duration(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @property
    def beat_duration(self) -> Fraction:
        """Conventional compound beat; irregular grouping stays unspecified."""
        return Fraction(3 if self.numerator>3 and self.numerator%3==0 else 1,self.denominator)


@dataclass(frozen=True)
class KeySignature:
    tonic: str
    mode: str
    fifths: int

    @property
    def accidentals(self) -> dict[str, int]:
        letters = "FCGDAEB" if self.fifths >= 0 else "BEADGCF"
        return {letter: (1 if self.fifths >= 0 else -1)
                for letter in letters[:abs(self.fifths)]}

    @property
    def text(self) -> str:
        return self.tonic + ("m" if self.mode == "minor" else "")

    @property
    def pitch_class(self) -> int:
        natural = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        return (natural[self.tonic[0]] + self.tonic[1:].count("#")
                - self.tonic[1:].count("b")) % 12


@dataclass(frozen=True)
class Tempo:
    beat: Fraction
    bpm: Fraction


@dataclass(frozen=True)
class Header:
    field: str
    value: str
    span: SourceSpan


@dataclass(frozen=True)
class Note:
    midi: int
    letter: str
    accidental: int | None
    onset: Fraction
    duration: Fraction
    tie_from_previous: bool
    tie_to_next: bool
    span: SourceSpan

    @property
    def pitch_class(self) -> int:
        return self.midi % 12

    @property
    def octave(self) -> int:
        return self.midi // 12 - 1


@dataclass(frozen=True)
class Rest:
    onset: Fraction
    duration: Fraction
    span: SourceSpan


@dataclass(frozen=True)
class ChordSymbol:
    text: str
    onset: Fraction
    span: SourceSpan


@dataclass(frozen=True)
class NoteStack:
    notes: tuple[Note, ...]
    onset: Fraction
    duration: Fraction
    span: SourceSpan


Event = Note | Rest | ChordSymbol | NoteStack


@dataclass(frozen=True)
class Measure:
    index: int
    onset: Fraction
    duration: Fraction
    meter: Meter
    key: KeySignature
    events: tuple[Event, ...]
    span: SourceSpan
    section_id: str
    rest_group_index: int = 0
    rest_group_count: int = 1

    @property
    def notes(self) -> tuple[Note, ...]:
        return tuple(note for event in self.events
                     for note in (event.notes if isinstance(event, NoteStack) else
                                  (event,) if isinstance(event, Note) else ()))

    @property
    def chords(self) -> tuple[ChordSymbol, ...]:
        return tuple(event for event in self.events if isinstance(event, ChordSymbol))


@dataclass(frozen=True)
class Voice:
    id: str
    measures: tuple[Measure, ...]

    @property
    def duration(self) -> Fraction:
        return sum((measure.duration for measure in self.measures), Fraction())


@dataclass(frozen=True)
class SectionVoiceRange:
    voice_id: str
    start_measure: int
    end_measure: int


@dataclass(frozen=True)
class Section:
    name: str
    occurrence: int
    span: SourceSpan
    voice_ranges: tuple[SectionVoiceRange, ...]

    @property
    def id(self) -> str:
        return f"{self.name}#{self.occurrence}"

    @property
    def start_measure(self) -> int:
        indices = {r.start_measure for r in self.voice_ranges}
        if len(indices)!=1:
            raise ValueError(f'{self.id}: section start is missing or voices are misaligned')
        return next(iter(indices))

    @property
    def end_measure(self) -> int:
        """Exclusive end index shared by aligned voices."""
        indices = {r.end_measure for r in self.voice_ranges}
        if len(indices)!=1:
            raise ValueError(f'{self.id}: section end is missing or voices are misaligned')
        return next(iter(indices))

    def range_for(self, voice_id: str) -> SectionVoiceRange:
        for voice_range in self.voice_ranges:
            if voice_range.voice_id == voice_id:
                return voice_range
        raise KeyError(f"Section {self.id!r} has no voice {voice_id!r}")


@dataclass(frozen=True)
class ContextChange:
    voice_id: str | None
    kind: str
    value: KeySignature | Meter | Tempo | Fraction
    onset: Fraction
    span: SourceSpan


@dataclass(frozen=True)
class Score:
    source: str
    headers: tuple[Header, ...]
    voices: tuple[Voice, ...]
    sections: tuple[Section, ...]
    changes: tuple[ContextChange, ...]
    source_model_digest: str = ""

    def voice(self, voice_id: str) -> Voice:
        for voice in self.voices:
            if voice.id == voice_id:
                return voice
        raise KeyError(f"Unknown voice {voice_id!r}")

    def section(self, name: str, occurrence: int = 1) -> Section:
        # Normalization is intentionally shared with the parser, without an import cycle.
        normalized = " ".join(name.strip().lower().replace("_", " ").split())
        normalized = {"pre chorus": "pre-chorus", "prechorus": "pre-chorus",
                      "post chorus": "post-chorus", "postchorus": "post-chorus"}.get(normalized, normalized)
        for section in self.sections:
            if section.name == normalized and section.occurrence == occurrence:
                return section
        raise KeyError(f"Unknown section {normalized}#{occurrence}")

    def section_measures(self, name: str, occurrence: int, voice_id: str) -> tuple[Measure, ...]:
        selected = self.section(name, occurrence).range_for(voice_id)
        return self.voice(voice_id).measures[selected.start_measure:selected.end_measure]


def score_fingerprint(score: Score) -> str:
    """Detect unsupported mutations of a source-backed model before serialization."""
    payload = repr((score.source, score.headers, score.voices, score.sections, score.changes))
    return sha256(payload.encode("utf-8")).hexdigest()
