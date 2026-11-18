"""Explicit musical evidence, without trained profiles or probability claims."""
from dataclasses import dataclass, replace
from fractions import Fraction

from ..abc.model import Score, Note, Meter
from ..abc.parser import parse_abc
from ..abc.validation import validate_score, require_valid
from .pitch import SCALES, NAMES
from ..i18n import translate

WEIGHTS = {'coverage': .36, 'tonic': .19, 'dominant': .07, 'ending': .23,
           'first': .04, 'leading': .06, 'long': .05}
MODE_DESCRIPTION = {mode: translate(f'mode.{mode}') for mode in SCALES}


@dataclass(frozen=True)
class MelodyAnalysis:
    score: Score
    voice_id: str
    notes: tuple[Note, ...]
    declared_key: str
    phrase_finals: tuple[int, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class KeyCandidate:
    tonic: str
    mode: str
    compatibility: float
    coverage: float
    ending_support: float
    tonic_support: float
    explanation: str


def metric_weight(onset: Fraction, meter: Meter) -> float:
    if onset == 0:
        return 1.8
    beat = meter.beat_duration
    return 1.3 if onset % beat == 0 else 1.0


def analyze_melody(abc: str, voice_id: str = 'auto') -> MelodyAnalysis:
    score = parse_abc(abc)
    require_valid(score)
    if voice_id == 'auto':
        sounding = [v for v in score.voices if any(b.notes for b in v.measures)]
        if len(sounding) != 1:
            raise ValueError('Select Vocal or Ins explicitly when multiple or no voices contain notes')
        voice_id = sounding[0].id
    voice = score.voice(voice_id)
    tokens = [n for b in voice.measures for n in b.notes]
    if not tokens:
        raise ValueError(f'No melody notes in {voice_id}')
    notes: list[Note] = []
    for n in tokens:
        if n.tie_from_previous:
            notes[-1] = replace(notes[-1], duration=notes[-1].duration+n.duration, tie_to_next=n.tie_to_next)
        else:
            notes.append(n)
    ends = {notes[-1].onset}
    for i, n in enumerate(notes[:-1]):
        if notes[i+1].onset > n.onset + n.duration:
            ends.add(n.onset)
    for section in score.sections:
        try:
            r = section.range_for(voice_id)
        except KeyError:
            continue
        bars = voice.measures[r.start_measure:r.end_measure]
        if bars:
            final = [n for n in notes if bars[0].onset <= n.onset < bars[-1].onset + bars[-1].duration]
            if final:
                ends.add(final[-1].onset)
    warnings = [i.message for i in validate_score(score) if i.severity == 'warning']
    if len(notes) < 8 or len({n.pitch_class for n in notes}) < 4:
        warnings.append('Sparse melody: tonal evidence is limited; several keys may fit.')
    if len({b.key for b in voice.measures}) > 1:
        warnings.append('Key changes present: ranking is an aggregate, inspect each section separately.')
    return MelodyAnalysis(score, voice_id, tuple(notes), voice.measures[0].key.text,
                          tuple(n.pitch_class for n in notes if n.onset in ends), tuple(warnings))


def rank_keys(analysis: MelodyAnalysis, include_modes: bool = False, count: int = 5, locale: str = 'en') -> tuple[KeyCandidate, ...]:
    if not 1 <= count <= 84:
        raise ValueError('candidate_count must be between 1 and 84')
    notes = analysis.notes
    histogram = [0.0]*12
    long_histogram = [0.0]*12
    bars = analysis.score.voice(analysis.voice_id).measures
    for note in notes:
        bar = next(b for b in bars if b.onset <= note.onset < b.onset+b.duration)
        w = float(note.duration)*metric_weight(note.onset-bar.onset, bar.meter)
        histogram[note.pitch_class] += w
        if note.duration >= Fraction(1,4):
            long_histogram[note.pitch_class] += w
    total = sum(histogram)
    evidence = min(1.0, len(notes)/12, len({n.pitch_class for n in notes})/5)
    candidates = []
    modes = tuple(SCALES) if include_modes else ('major','minor')
    for tonic in range(12):
        for mode in modes:
            scale = {(tonic+i)%12 for i in SCALES[mode]}
            coverage = sum(histogram[pc] for pc in scale)/total
            tonic_support = histogram[tonic]/total
            ending = sum(pc == tonic for pc in analysis.phrase_finals)/len(analysis.phrase_finals)
            leading = sum(a.pitch_class == (tonic+11)%12 and b.pitch_class == tonic
                          for a,b in zip(notes,notes[1:]))/max(1,len(notes)-1)
            long = long_histogram[tonic]/max(sum(long_histogram),.001)
            raw = (WEIGHTS['coverage']*coverage + WEIGHTS['tonic']*min(1,tonic_support*3)
                   + WEIGHTS['dominant']*min(1,histogram[(tonic+7)%12]/total*3)
                   + WEIGHTS['ending']*ending + WEIGHTS['first']*(notes[0].pitch_class == tonic)
                   + WEIGHTS['leading']*min(1,leading*6) + WEIGHTS['long']*long)
            score = raw*(.35+.65*evidence)
            candidates.append(KeyCandidate(NAMES[tonic], mode, round(score,4), coverage, ending,
                                           tonic_support, translate(f'mode.{mode}', locale)))
    return tuple(sorted(candidates, key=lambda c:(-c.compatibility,c.tonic,c.mode))[:count])


def analysis_report(analysis: MelodyAnalysis, locale: str = 'en') -> str:
    voice = analysis.score.voice(analysis.voice_id)
    pitches = [n.midi for n in analysis.notes]
    ordered = sorted(pitches)
    estimated = rank_keys(analysis)
    def line(message_key, **params):
        return translate('analysis.' + message_key, locale, **params)
    lines = [
        line('voice', voice=analysis.voice_id),
        line('notes', count=len(pitches)),
        line('duration', duration=voice.duration, bars=len(voice.measures)),
        line('key', key=analysis.declared_key),
        line('range', low=min(pitches), high=max(pitches)),
        line('tessitura', low=ordered[len(ordered)//10], high=ordered[min(len(ordered)-1,len(ordered)*9//10)]),
        line('pitchClasses', values=sorted(set(p%12 for p in pitches))),
        line('finals', values=analysis.phrase_finals),
        line('longNotes', count=sum(n.duration>=Fraction(1,4) for n in analysis.notes)),
        line('meters', values=sorted({f"{b.meter.numerator}/{b.meter.denominator}" for b in voice.measures})),
        line('tempo', values=[str(c.value) for c in analysis.score.changes if c.kind=='Q']),
        line('estimated', tonic=estimated[0].tonic, mode=estimated[0].mode),
        line('gap', gap=estimated[0].compatibility-estimated[1].compatibility),
    ]
    warnings = {translate(key): key for key in ('warning.sparse', 'warning.keyChanges')}
    for warning in analysis.warnings:
        message = translate(warnings[warning], locale) if warning in warnings else warning
        lines.append(line('warning', message=message))
    return '\n'.join(lines)


def key_report(candidates: tuple[KeyCandidate, ...], locale: str = 'en') -> str:
    return translate('keys.heading', locale) + '\n' + '\n'.join(
        translate('keys.item', locale, index=i, tonic=c.tonic, mode=c.mode, score=c.compatibility,
                  coverage=c.coverage, ending=c.ending_support, support=c.tonic_support,
                  description=translate(f'mode.{c.mode}', locale))
        for i,c in enumerate(candidates,1))
