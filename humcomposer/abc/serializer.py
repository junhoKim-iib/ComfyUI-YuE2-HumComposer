"""Source-preserving edits. Musical changes must use explicit, checked spans."""
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from .model import Score, SourceSpan, score_fingerprint


@dataclass(frozen=True)
class TextEdit:
    span: SourceSpan
    replacement: str


def serialize(score: Score, edits: Sequence[TextEdit] = ()) -> str:
    if score.source_model_digest != score_fingerprint(score):
        raise ValueError("Source-backed model changed; use explicit text edits and reparse")
    ordered = sorted(edits, key=lambda edit: (edit.span.start, edit.span.end))
    previous_end = -1
    for edit in ordered:
        if not 0 <= edit.span.start <= edit.span.end <= len(score.source):
            raise ValueError("Edit span is outside source")
        if edit.span.start < previous_end:
            raise ValueError("Overlapping edits are not allowed")
        previous_end = edit.span.end
    text = score.source
    for edit in reversed(ordered):
        text = text[:edit.span.start] + edit.replacement + text[edit.span.end:]
    return text


def rewrite_measures(score: Score, replacements: Mapping[tuple[str, int], str]) -> str:
    groups: dict[SourceSpan, list[tuple[str, int]]] = {}
    for voice_id, index in replacements:
        voice = score.voice(voice_id)
        if not 0 <= index < len(voice.measures):
            raise ValueError(f"Unknown measure {voice_id}:{index}")
        bar = voice.measures[index]
        groups.setdefault(bar.span, []).append((voice_id, index))
    edits = []
    for span, selected in groups.items():
        voice_id, index = selected[0]
        bar = score.voice(voice_id).measures[index]
        if bar.rest_group_count > 1:
            first = index - bar.rest_group_index
            body = "".join(replacements.get((voice_id, i), "Z|")
                           for i in range(first, first + bar.rest_group_count))
        else:
            body = replacements[(voice_id, index)]
        if not body.rstrip().endswith("|"):
            raise ValueError("Replacement measures must end in a bar line")
        edits.append(TextEdit(span, body))
    return serialize(score, edits)
