"""Explicit musical evidence, without trained profiles or probability claims."""
from dataclasses import dataclass, replace
from fractions import Fraction

from ..abc.model import Score, Note, Meter
from ..abc.parser import parse_abc
from ..abc.validation import validate_score, require_valid
from .pitch import SCALES, NAMES

WEIGHTS = {'coverage': .36, 'tonic': .19, 'dominant': .07, 'ending': .23,
           'first': .04, 'leading': .06, 'long': .05}
MODE_DESCRIPTION = {
    'major':'장3도와 이끈음이 있는 조성 후보. 종지·리듬·음역에 따라 인상이 달라집니다.',
    'minor':'단3도 기반 후보. V 또는 V7의 이끈음을 강조하면 긴장과 해결을 강화할 수 있습니다.',
    'dorian':'단3도와 장6도를 결합하는 모드입니다.',
    'phrygian':'단3도와 낮은 2도가 특징인 모드입니다.',
    'lydian':'장3도와 높아진 4도가 특징인 모드입니다.',
    'mixolydian':'장3도와 낮은 7도를 사용하는 모드입니다.',
    'locrian':'단3도와 감5도로 으뜸 삼화음의 안정성이 약한 모드입니다.',
}


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
    beat = Fraction(3 if meter.denominator == 8 and meter.numerator % 3 == 0 else 1, meter.denominator)
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


def rank_keys(analysis: MelodyAnalysis, include_modes: bool = False, count: int = 5) -> tuple[KeyCandidate, ...]:
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
                                           tonic_support, MODE_DESCRIPTION[mode]))
    return tuple(sorted(candidates, key=lambda c:(-c.compatibility,c.tonic,c.mode))[:count])


def analysis_report(analysis: MelodyAnalysis) -> str:
    voice = analysis.score.voice(analysis.voice_id)
    pitches = [n.midi for n in analysis.notes]
    ordered = sorted(pitches)
    estimated = rank_keys(analysis)
    text = (f'Voice: {analysis.voice_id}\nNotes (ties merged): {len(pitches)}\n'
            f'Duration: {voice.duration} whole notes; bars: {len(voice.measures)}\n'
            f'Declared key: {analysis.declared_key}\nRange MIDI: {min(pitches)}–{max(pitches)}\n'
            f'Tessitura (10–90% MIDI): {ordered[len(ordered)//10]}–{ordered[min(len(ordered)-1,len(ordered)*9//10)]}\n'
            f'Pitch classes: {sorted(set(p%12 for p in pitches))}\n'
            f'Phrase finals: {analysis.phrase_finals}\n'
            f'Long notes (>=quarter): {sum(n.duration>=Fraction(1,4) for n in analysis.notes)}\n'
            f'Meters: {sorted({f"{b.meter.numerator}/{b.meter.denominator}" for b in voice.measures})}\n'
            f'Tempo: {[str(c.value) for c in analysis.score.changes if c.kind=="Q"]}\n'
            f'Estimated: {estimated[0].tonic} {estimated[0].mode}\n'
            f'Top score gap: {estimated[0].compatibility-estimated[1].compatibility:.3f} (small = ambiguous)')
    return text + ''.join('\nWARNING: '+w for w in analysis.warnings)


def key_report(candidates: tuple[KeyCandidate, ...]) -> str:
    return 'Heuristic compatibility; not statistical probability.\n' + '\n'.join(
        f'{i}. {c.tonic} {c.mode}: {c.compatibility:.3f}; scale {c.coverage:.0%}; '
        f'ending {c.ending_support:.0%}; tonic {c.tonic_support:.0%}\n   {c.explanation}'
        for i,c in enumerate(candidates,1))
