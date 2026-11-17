"""Place a complete main motif without depending on verse/chorus naming."""
from dataclasses import dataclass

from ..abc.parser import parse_abc
from ..abc.validation import require_valid
from .anchors import MelodyAnchor
from .merge import _tones


@dataclass(frozen=True)
class MainThemePlan:
    anchors: tuple[MelodyAnchor, ...]
    report: str


def plan_main_theme(base_abc: str, theme_abc: str, source_voice: str = 'auto',
                    reserved: tuple[MelodyAnchor, ...] = (), target_voice: str = 'auto',
                    variation_amount: float = .25, seed: int = 0) -> MainThemePlan:
    if not isinstance(reserved, tuple) or not all(isinstance(anchor, MelodyAnchor) for anchor in reserved):
        raise TypeError('Expected an anchor collection')
    base = parse_abc(base_abc)
    require_valid(base, native=True)
    source = parse_abc(theme_abc)
    require_valid(source)
    _, motif = _tones(source, source_voice)
    grid = tuple((bar.duration, bar.meter) for bar in motif)
    size = len(motif)
    voices = [voice for voice in base.voices if voice.id in ('Vocal', 'Ins') and voice.measures]
    if target_voice == 'auto':
        if not voices:
            raise ValueError('Main theme needs a Vocal or Ins voice in the generated score')
        target = max(voices, key=lambda voice: sum(len(bar.notes) for bar in voice.measures))
    elif target_voice in ('Vocal', 'Ins'):
        target = base.voice(target_voice)
    else:
        raise ValueError('Main theme target_voice must be auto, Vocal, or Ins')
    occupied = set()
    for anchor in reserved:
        if anchor.mode == 'AI' or anchor.target_voice != target.id:
            continue
        for section in base.sections:
            if section.name != anchor.section or anchor.occurrence not in ('all', str(section.occurrence)):
                continue
            selected = section.range_for(target.id)
            occupied.update(range(anchor.start_measure if anchor.start_measure is not None else selected.start_measure,
                                  anchor.end_measure if anchor.end_measure is not None else selected.end_measure))
    sounding_sections = [section for section in base.sections
                         if any(bar.notes for bar in base.section_measures(section.name, section.occurrence, target.id))]
    sections = sounding_sections or list(base.sections)
    placements = []
    skipped = []
    has_melody = any(bar.notes for bar in target.measures)
    for section in sections:
        selected = section.range_for(target.id)
        candidates = []
        for start in range(selected.start_measure, selected.end_measure - size + 1):
            end = start + size
            bars = target.measures[start:end]
            if has_melody and not bars[0].notes:
                continue
            if any(index in occupied for index in range(start, end)):
                continue
            if tuple((bar.duration, bar.meter) for bar in bars) != grid:
                continue
            if (bars[0].notes and bars[0].notes[0].tie_from_previous
                    or bars[-1].notes and bars[-1].notes[-1].tie_to_next):
                continue
            if any(change.voice_id == target.id and change.kind not in ('K', 'M')
                   and any(bar.span.start <= change.span.start < bar.span.end for bar in bars)
                   for change in base.changes):
                continue
            candidates.append((start, end))
        if not candidates:
            skipped.append(section.id)
            continue
        chosen = [candidates[0]]
        # A later return leaves the intervening generated development intact.
        later = [span for span in candidates if span[0] >= chosen[0][1]]
        if later:
            chosen.append(later[-1])
        for start, end in chosen:
            bars = target.measures[start:end]
            stable_keys = (all(bar.key == motif[0].key for bar in motif)
                        and all(bar.key == bars[0].key for bar in bars)
                        and not any(change.kind == 'K' and change.onset > 0 for change in source.changes)
                        and not any(change.kind == 'K' and change.voice_id == target.id
                                    and bars[0].onset <= change.onset < bars[-1].onset + bars[-1].duration
                                    and change.value != bars[0].key for change in base.changes))
            mode = 'VARIATION' if placements and stable_keys else 'LOCK'
            placements.append(MelodyAnchor(section.name, str(section.occurrence), theme_abc,
                mode=mode, fit_policy='strict', transpose_policy='none', harmony_policy='recommend_only',
                source_voice=source_voice, target_voice=target.id, variation_amount=variation_amount,
                seed=seed + len(placements), start_measure=start, end_measure=end))
            occupied.update(range(start, end))
    if not placements:
        raise ValueError(f'Main theme has {size} bars but no complete matching, untied window is available '
                         f'in {target.id}. Use a shorter theme, a longer compatible score, or adjust explicit anchors.')
    report = ['MAIN THEME', f'Complete motif: {size} bars; voice: {target.id}; no section names required.',
              'First statement preserves the motif; later compatible statements use limited variation.',
              'Only listed measure ranges are replaced; section names and the remaining generated score are retained.']
    report.extend(f'{anchor.mode}: {anchor.section}#{anchor.occurrence}, {anchor.target_voice} '
                  f'bars {anchor.start_measure+1}-{anchor.end_measure}' for anchor in placements)
    if skipped:
        report.append('No safe complete window in: ' + ', '.join(skipped))
    return MainThemePlan(tuple(placements), '\n'.join(report))
