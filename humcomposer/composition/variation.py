from dataclasses import dataclass, replace
from fractions import Fraction
import math
import random

from ..theory.pitch import SCALES, pitch_class, normalize_mode
from ..abc.model import Meter


@dataclass(frozen=True)
class Tone:
    onset: Fraction
    duration: Fraction
    midi: int | None


@dataclass(frozen=True)
class MotifSimilarity:
    overall: float
    contour: float
    rhythm: float
    important_retention: float
    ending_retained: bool


def _protected(tones: tuple[Tone, ...], meter_grid: tuple[tuple[Fraction,Meter], ...] = ()) -> set[int]:
    grid = meter_grid or ((Fraction(),Meter(4,4)),)
    if grid[0][0]!=0 or any(b[0]<=a[0] for a,b in zip(grid,grid[1:])):
        raise ValueError('Meter grid must start at zero and increase strictly')
    if any(m.numerator<=0 or m.denominator<=0 for _,m in grid):
        raise ValueError('Meter grid values must be positive')
    sounding = [i for i,t in enumerate(tones) if t.midi is not None]
    result = set()
    for j,i in enumerate(sounding):
        t = tones[i]
        origin,meter = next((item for item in reversed(grid) if item[0]<=t.onset),grid[0])
        if (j==0 or j==len(sounding)-1 or t.duration>=Fraction(1,4)
                or (t.onset-origin) % meter.beat_duration==0):
            result.add(i)
        if j and tones[sounding[j-1]].onset+tones[sounding[j-1]].duration<t.onset:
            result.update((i,sounding[j-1]))
    return result


def motif_similarity(before: tuple[Tone, ...], after: tuple[Tone, ...], *,
                     meter_grid: tuple[tuple[Fraction,Meter], ...] = ()) -> MotifSimilarity:
    a = [t for t in before if t.midi is not None]
    b = [t for t in after if t.midi is not None]
    if len(a) != len(b) or not a:
        raise ValueError('Motif comparison requires an equal number of sounding events')
    def sign(n: int) -> int:
        return (n>0)-(n<0)
    contour = (sum(sign(y.midi-x.midi)==sign(v.midi-u.midi)
                   for x,y,u,v in zip(a,a[1:],b,b[1:]))/(len(a)-1)) if len(a)>1 else 1.0
    rhythm = sum((x.onset,x.duration)==(y.onset,y.duration) for x,y in zip(a,b))/len(a)
    protected_times = {before[i].onset for i in _protected(before,meter_grid)}
    important = [i for i,t in enumerate(a) if t.onset in protected_times]
    retained = sum(a[i].midi==b[i].midi for i in important)/len(important)
    ending = a[-1].midi==b[-1].midi
    return MotifSimilarity(.4*contour+.3*rhythm+.3*retained,contour,rhythm,retained,ending)


def generate_variation(tones: tuple[Tone, ...], tonic: str, mode: str,
                       amount: float = .25, seed: int = 0, *,
                       meter_grid: tuple[tuple[Fraction,Meter], ...] = ()) -> tuple[tuple[Tone, ...], MotifSimilarity]:
    if not math.isfinite(amount) or not 0 <= amount <= 1:
        raise ValueError('variation_amount must be between 0 and 1')
    mode = normalize_mode(mode)
    pcs = {(pitch_class(tonic)+i)%12 for i in SCALES[mode]}
    sounding = [i for i,t in enumerate(tones) if t.midi is not None]
    protected = _protected(tones,meter_grid)
    eligible = [i for i in sounding if i not in protected]
    rng = random.Random(seed)
    rng.shuffle(eligible)
    result = list(tones)
    for i in eligible[:math.ceil(amount*len(eligible))]:
        n = tones[i]
        choices = [n.midi+d for d in (-2,-1,1,2) if 0<=n.midi+d<=127 and (n.midi+d)%12 in pcs]
        rng.shuffle(choices)
        for midi in choices:
            proposal = result.copy()
            proposal[i] = replace(n,midi=midi)
            if motif_similarity(tones,tuple(proposal),meter_grid=meter_grid).overall>=.75:
                result = proposal
                break
    final = tuple(result)
    return final,motif_similarity(tones,final,meter_grid=meter_grid)
