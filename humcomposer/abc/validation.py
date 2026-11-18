"""Structural validation; warnings are distinct from fatal integrity errors."""
from dataclasses import dataclass
import re

from ..i18n import translate
from .model import Score, SourceSpan, Note, NoteStack


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    span: SourceSpan | None = None


def validate_score(score: Score, *, native: bool = False) -> tuple[ValidationIssue, ...]:
    issues = []
    def error(code: str, message: str, span: SourceSpan | None = None) -> None:
        issues.append(ValidationIssue("error", code, message, span))
    if not score.voices or not any(voice.measures for voice in score.voices):
        error("missing_music", "No musical events found")
    if not score.sections or all(s.name == "unsectioned" for s in score.sections):
        issues.append(ValidationIssue("warning", "missing_sections", "No named sections; anchors need section comments"))
    if native and not {"Vocal", "Ins"}.issubset({v.id for v in score.voices}):
        error("missing_voices", "Native song requires Vocal and Ins voices")
    if native and len(score.voices) > 2:
        issues.append(ValidationIssue('warning', 'additional_voices',
                      'Additional parts are preserved in ABC; native model reproduction has not been verified'))
    if native:
        fields = {h.field for h in score.headers}
        for field in ('X','T','Q'):
            if field not in fields:
                issues.append(ValidationIssue('warning','missing_header',f'Native exporter normally supplies {field}:; inspect source'))
    for voice in score.voices:
        pending = {}
        for bar in voice.measures:
            if bar.duration != bar.meter.duration:
                error("bar_duration", f"{voice.id} bar {bar.index + 1}: {bar.duration}, expected {bar.meter.duration}", bar.span)
            for event in bar.events:
                if hasattr(event, 'text') and native:
                    if not re.fullmatch(r'[A-G](?:##|bb|#|b)?(?:m\(maj7\)|7sus4|m7b5|maj7|dim7|dim|aug|sus4|sus2|m7|m6|m|7|6)?(?:/[A-G](?:##|bb|#|b)?)?',event.text):
                        error('unsupported_chord',f'Unsupported native chord {event.text!r}',event.span)
                    if voice.id != 'Vocal':
                        error('chord_voice','Native chords must be in Vocal voice',event.span)
                if hasattr(event, "duration") and event.duration <= 0:
                    error("invalid_duration", "Event duration must be positive", event.span)
                if isinstance(event, (Note, NoteStack)):
                    notes = event.notes if isinstance(event, NoteStack) else (event,)
                    continued = {note.midi for note in notes if note.tie_from_previous}
                    if continued != set(pending):
                        error("broken_tie", "Tie does not continue an equal pitch", event.span)
                    pending = {note.midi: note for note in notes if note.tie_to_next}
            if len({c.onset for c in bar.chords}) != len(bar.chords):
                error('duplicate_chord_onset',f'{voice.id} bar {bar.index+1}: simultaneous chord symbols',bar.span)
        if pending:
            error("unresolved_tie", f"{voice.id}: unresolved final tie", next(iter(pending.values())).span)
    for section in score.sections:
        grids = []
        for voice in score.voices:
            try:
                selected = section.range_for(voice.id)
            except KeyError:
                error("section_voice_missing", f"{section.id}: missing {voice.id}", section.span)
                continue
            bars = voice.measures[selected.start_measure:selected.end_measure]
            grids.append(tuple((b.onset, b.duration, b.meter) for b in bars))
        if grids and any(grid != grids[0] for grid in grids[1:]):
            error("section_alignment", f"{section.id}: voice bar grids differ", section.span)
    if len(score.voices) > 1:
        # Effective key/meter/tempo timelines must agree, including inline changes.
        for kind in ("K", "M", "Q"):
            timelines = []
            for voice in score.voices:
                timeline = {}
                for change in score.changes:
                    if change.kind == kind and change.voice_id in (None, voice.id):
                        timeline[change.onset] = change.value
                compact = []
                previous = None
                for onset, value in sorted(timeline.items()):
                    if value != previous:
                        compact.append((onset, value))
                        previous = value
                timelines.append(compact)
            if any(t != timelines[0] for t in timelines[1:]):
                error("context_alignment", f"Voice {kind}: changes differ in musical time")
    for section in score.sections:
        if not section.voice_ranges:
            error('empty_section',f'{section.id}: empty or duplicated section marker',section.span)
    return tuple(issues)


def format_validation(issues: tuple[ValidationIssue, ...], locale: str = 'en') -> str:
    valid = not any(issue.severity == "error" for issue in issues)
    return translate('validation.passed' if valid else 'validation.failed', locale) + "".join(
        f"\n{issue.severity.upper()} [{issue.code}] {issue.message}" for issue in issues)


def require_valid(score: Score, *, native: bool = False) -> None:
    issues = validate_score(score, native=native)
    if any(issue.severity == "error" for issue in issues):
        raise ValueError(format_validation(issues))
