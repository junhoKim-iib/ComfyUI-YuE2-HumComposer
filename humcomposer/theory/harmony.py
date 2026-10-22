"""Melody-aware chord compatibility with contextual non-chord-tone allowance."""
from dataclasses import dataclass
from fractions import Fraction
import re

from ..abc.model import Note, Meter
from .pitch import pitch_class, degree_name, normalize_mode, SCALES
from .key_detection import metric_weight, MelodyAnalysis

QUALITIES = {'':(0,4,7), 'm':(0,3,7), 'dim':(0,3,6), 'aug':(0,4,8),
             '7':(0,4,7,10), 'maj7':(0,4,7,11), 'm7':(0,3,7,10),
             'dim7':(0,3,6,9), 'm7b5':(0,3,6,10), 'sus4':(0,5,7),
             'sus2':(0,2,7), '6':(0,4,7,9), 'm6':(0,3,7,9),
             '7sus4':(0,5,7,10), 'm(maj7)':(0,3,7,11)}
ROMANS = ('I','II','III','IV','V','VI','VII')
TEMPLATES = {
    'major': (('I','V','vi','IV'),('vi','IV','I','V'),('ii','V','I','I'),('I','IV','V','I'),('I','vi','ii','V')),
    'minor': (('i','VI','III','VII'),('i','iv','VI','V'),('i','VII','VI','V'),('i','iv','V','i'),('i','VI','iv','V')),
    'modal': (('i','IV','i','VII'),('I','VII','IV','I'),('i','II','VII','i'),('I','II','V','I')),
}


@dataclass(frozen=True)
class Chord:
    name: str
    root: int
    tones: frozenset[int]


@dataclass(frozen=True)
class Progression:
    roman: tuple[str, ...]
    chords: tuple[Chord, ...]
    compatibility: float
    explanation: str


def parse_chord(symbol: str) -> Chord:
    match = re.fullmatch(r'([A-G](?:##|bb|#|b)?)([^/]*)(?:/([A-G](?:##|bb|#|b)?))?',symbol)
    if not match or match[2] not in QUALITIES:
        raise ValueError(f'Unsupported native chord {symbol!r}')
    root = pitch_class(match[1])
    tones = {(root+i)%12 for i in QUALITIES[match[2]]}
    if match[3]:
        tones.add(pitch_class(match[3]))
    return Chord(symbol,root,frozenset(tones))


def resolve_roman(roman: str, tonic: str, mode: str) -> Chord:
    mode = normalize_mode(mode)
    match = re.fullmatch(r'([ivIV]+)([oø]?)(7?)',roman)
    if not match or match[1].upper() not in ROMANS:
        raise ValueError(f'Unsupported Roman numeral {roman!r}')
    degree = ROMANS.index(match[1].upper())
    name = degree_name(tonic,mode,degree)
    quality = 'dim' if match[2] else ('m' if match[1].islower() else '')
    if match[3]:
        seventh = (SCALES[mode][(degree+6)%7]-SCALES[mode][degree])%12
        quality = {'m':'m7','dim':'m7b5' if match[2]=='ø' else 'dim7',
                   '':'7' if seventh==10 else 'maj7'}[quality]
    return parse_chord(name+quality)


def score_chord_fit(notes: tuple[Note, ...], chord: Chord, onset: Fraction,
                    duration: Fraction, meter: Meter) -> float:
    total = fit = 0.0
    for i,n in enumerate(notes):
        overlap = min(onset+duration,n.onset+n.duration)-max(onset,n.onset)
        if overlap <= 0:
            continue
        weight = float(overlap)*metric_weight(max(n.onset,onset)-onset,meter)
        value = 1.0 if n.pitch_class in chord.tones else .12
        if value < 1 and i and i+1 < len(notes):
            prev,nxt = notes[i-1],notes[i+1]
            a,b = n.midi-prev.midi,nxt.midi-n.midi
            connected = prev.onset+prev.duration == n.onset and n.onset+n.duration == nxt.onset
            if connected and abs(a) <= 2 and abs(b) <= 2 and prev.pitch_class in chord.tones and nxt.pitch_class in chord.tones:
                if n.duration <= Fraction(1,8):
                    value = .8  # Short stepwise passing or neighboring tone.
            if (n.tie_from_previous or n.onset<onset) and nxt.onset<onset+duration and nxt.pitch_class in chord.tones and b in (-1,-2):
                value = max(value,.65)
        total += weight
        fit += weight*value
    return fit/total if total else .5


def build_progressions(analysis: MelodyAnalysis, tonic: str, mode: str = 'major',
                       bars: int = 4, complexity: str = 'triads', count: int = 3) -> tuple[Progression, ...]:
    mode = normalize_mode(mode)
    pitch_class(tonic)
    if not 1 <= bars <= 256 or not 1 <= count <= 20 or complexity not in ('triads','sevenths'):
        raise ValueError('Invalid bars, candidate_count, or complexity')
    templates = TEMPLATES.get(mode,TEMPLATES['modal'])
    if mode not in ('major','minor'):
        scale = SCALES[mode]
        modal_templates = []
        for degrees in ((0,3,0,6),(0,6,3,0),(0,1,6,0),(0,1,4,0)):
            template = []
            for degree in degrees:
                third = (scale[(degree+2)%7]-scale[degree])%12
                fifth = (scale[(degree+4)%7]-scale[degree])%12
                roman = ROMANS[degree] if third==4 else ROMANS[degree].lower()
                if fifth==6:
                    roman += 'ø' if complexity=='sevenths' else 'o'
                template.append(roman)
            modal_templates.append(tuple(template))
        templates = tuple(modal_templates)
    measures = analysis.score.voice(analysis.voice_id).measures
    results = []
    for template in templates:
        roman = tuple(template[i%len(template)] for i in range(bars))
        if complexity == 'sevenths':
            roman = tuple(r+'7' for r in roman)
        chords = tuple(resolve_roman(r,tonic,mode) for r in roman)
        fits = [score_chord_fit(analysis.notes,c,b.onset,b.duration,b.meter)
                for c,b in zip(chords,measures)]
        motion = sum(min((b.root-a.root)%12,(a.root-b.root)%12) for a,b in zip(chords,chords[1:]))/max(1,bars-1)
        cadence = .1 if len(roman)>1 and roman[-2].rstrip('7')=='V' and roman[-1].rstrip('7') in ('I','i') else 0
        repetition = sum(a==b for a,b in zip(roman,roman[1:]))/max(1,bars-1)
        score = max(0,min(1,sum(fits)/len(fits)*.85 + cadence + .05*(1-motion/6)-.05*repetition))
        explanation = (f'Melody fit {sum(fits)/len(fits):.3f}; cadence bonus {cadence:.2f}; '
                       f'root-motion proxy {motion:.2f} semitones. '
                       f'{min(len(measures),bars)}/{bars} bars have melody evidence. '
                       'One chord per bar; non-chord tones may be intentional.')
        results.append(Progression(roman,chords,round(score,4),explanation))
    return tuple(sorted(results,key=lambda p:(-p.compatibility,p.roman))[:count])


def harmony_report(items: tuple[Progression, ...]) -> str:
    return 'Compatibility is heuristic, not probability.\n'+'\n'.join(
        f'{i}. {" - ".join(p.roman)}\n   {" - ".join(c.name for c in p.chords)}\n'
        f'   {p.compatibility:.3f}: {p.explanation}' for i,p in enumerate(items,1))
