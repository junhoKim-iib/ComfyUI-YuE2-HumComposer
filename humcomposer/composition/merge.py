"""Replace only selected voice measure spans; validate musical invariants after editing."""
from dataclasses import dataclass, replace
from fractions import Fraction

from ..abc.model import Score, Measure, Note, Rest, ChordSymbol, SourceSpan, Voice
from ..abc.parser import parse_abc, parse_key
from ..abc.serializer import rewrite_measures
from ..abc.validation import require_valid, validate_score, format_validation
from ..theory.harmony import parse_chord, score_chord_fit, build_progressions
from ..theory.key_detection import MelodyAnalysis
from .anchors import MelodyAnchor
from .variation import Tone, generate_variation

NATIVE_DURATIONS = (48,32,24,16,12,8,6,4,3,2,1)


@dataclass(frozen=True)
class CompositionResult:
    abc: str
    composition_report: str
    validation_report: str


def _tones(score: Score, source_voice: str) -> tuple[tuple[Tone, ...], tuple[Measure, ...]]:
    if source_voice == 'auto':
        sounding = [v for v in score.voices if any(b.notes for b in v.measures)]
        if len(sounding) != 1:
            raise ValueError('Select source_voice explicitly for ABC with multiple or no sounding voices')
        voice = sounding[0]
    else:
        voice = score.voice(source_voice)
    bars = voice.measures
    if not bars or not any(b.notes for b in bars):
        raise ValueError('Anchor source has no notes')
    tones: list[Tone] = []
    for bar in bars:
        for event in bar.events:
            if isinstance(event,ChordSymbol):
                continue
            if isinstance(event,Note) and event.tie_from_previous:
                previous = tones[-1]
                tones[-1] = replace(previous,duration=previous.duration+event.duration)
            else:
                tones.append(Tone(event.onset,event.duration,event.midi if isinstance(event,Note) else None))
    return tuple(tones),bars


def _fit(tones: tuple[Tone, ...], source: tuple[Measure, ...], target: tuple[Measure, ...], policy: str) -> tuple[Tone, ...]:
    actual = sum((b.duration for b in source),Fraction())
    expected = sum((b.duration for b in target),Fraction())
    if policy!='stretch_rhythm':
        source_grid = tuple((b.duration,b.meter) for b in source)
        target_grid = tuple((b.duration,b.meter) for b in target)
        if policy=='repeat' and expected/actual == int(expected/actual):
            compatible = source_grid*int(expected/actual)==target_grid
        elif policy=='truncate':
            compatible = source_grid[:len(target)]==target_grid
        else:
            compatible = source_grid==target_grid[:len(source)]
        if not compatible:
            raise ValueError('Strict length/meter mismatch: fit policy cannot silently change bar grids; use stretch_rhythm explicitly')
    if policy == 'strict':
        if actual!=expected or tuple((b.duration,b.meter) for b in source)!=tuple((b.duration,b.meter) for b in target):
            raise ValueError(f'Strict length/meter mismatch: anchor {len(source)} bars/{actual}, target {len(target)} bars/{expected}')
        return tones
    if policy == 'pad_rest':
        if actual>expected:
            raise ValueError('pad_rest cannot shorten an anchor')
        return tones + ((Tone(actual,expected-actual,None),) if actual<expected else ())
    if policy == 'repeat':
        ratio = expected/actual
        if ratio.denominator != 1:
            raise ValueError('repeat requires an integral number of complete motifs')
        return tuple(replace(t,onset=t.onset+i*actual) for i in range(int(ratio)) for t in tones)
    if policy == 'stretch_rhythm':
        factor = expected/actual
        return tuple(replace(t,onset=t.onset*factor,duration=t.duration*factor) for t in tones)
    if policy == 'truncate':
        if actual<expected:
            raise ValueError('truncate cannot lengthen an anchor')
        return tuple(replace(t,duration=min(t.duration,expected-t.onset)) for t in tones if t.onset<expected)
    raise ValueError(f'Unknown fit policy {policy}')


def _unit_at(score: Score, voice_id: str, onset: Fraction) -> Fraction:
    unit = None
    for c in score.changes:
        if c.kind=='L' and c.voice_id in (None,voice_id) and c.onset<=onset:
            unit = c.value
    if not isinstance(unit,Fraction):
        raise ValueError('No active L: value')
    return unit


def _note_name(midi: int | None) -> str:
    if midi is None:
        return 'z'
    names = ('=C','^C','=D','_E','=E','=F','^F','=G','_A','=A','_B','=B')
    name = names[midi%12]
    octave = midi//12-1
    if octave>=5:
        return name[:-1]+name[-1].lower()+"'"*(octave-5)
    return name+','*(4-octave)


def _emit_bar(bar: Measure, tones: tuple[Tone, ...], start: Fraction,
              unit: Fraction, chords: tuple[ChordSymbol, ...]) -> str:
    end = start+bar.duration
    points = {start,end}
    points.update(t.onset for t in tones if start<t.onset<end)
    points.update(t.onset+t.duration for t in tones if start<t.onset+t.duration<end)
    chord_map = {c.onset-bar.onset+start:c.text for c in chords}
    points.update(chord_map)
    positions = sorted(points)
    text = []
    for a,b in zip(positions,positions[1:]):
        if a in chord_map:
            text.append('"'+chord_map[a]+'"')
        tone = next((t for t in tones if t.onset<=a and t.onset+t.duration>=b),None)
        if tone is None:
            raise ValueError(f'Anchor has uncovered interval {a}..{b}')
        units = (b-a)/unit
        if units.denominator != 1:
            raise ValueError(f'Anchor duration {b-a} cannot use native base L:{unit}; finer grid required')
        remaining = int(units)
        while remaining:
            length = next(d for d in NATIVE_DURATIONS if d<=remaining)
            remaining -= length
            tied = tone.midi is not None and (remaining>0 or b<tone.onset+tone.duration)
            text.append(_note_name(tone.midi)+(str(length) if length!=1 else '')+('-' if tied else ''))
    return ''.join(text)+'|'


def _bar_signature(bar: Measure) -> tuple:
    return (bar.onset,bar.duration,bar.meter,bar.key,
            tuple((type(e).__name__,getattr(e,'midi',None),getattr(e,'text',None),e.onset,
                   getattr(e,'duration',None),getattr(e,'tie_from_previous',None),getattr(e,'tie_to_next',None)) for e in bar.events))


def _sounding_signature(bars: tuple[Measure, ...]) -> tuple:
    result = []
    for bar in bars:
        for n in bar.notes:
            if n.tie_from_previous:
                old = result[-1]
                result[-1] = (old[0],old[1],old[2]+n.duration)
            else:
                result.append((n.midi,n.onset,n.duration))
    return tuple(result)


def _harmony_fit(score: Score, voice_id: str, bars: tuple[Measure, ...], tones: tuple[Tone, ...]) -> tuple[float, list[str]]:
    active = None
    fits = []
    warnings = []
    start = bars[0].onset
    notes = tuple(Note(t.midi,'C',None,t.onset+start,t.duration,False,False,SourceSpan(0,0))
                  for t in tones if t.midi is not None)
    for bar in score.voice(voice_id).measures:
        points = [(bar.onset,active)]
        for c in bar.chords:
            active = c.text
            if points[-1][0]==c.onset:
                points[-1] = (c.onset,active)
            else:
                points.append((c.onset,active))
        if not bars[0].onset<=bar.onset<bars[-1].onset+bars[-1].duration:
            continue
        for i,(onset,name) in enumerate(points):
            if name is None:
                continue
            until = points[i+1][0] if i+1<len(points) else bar.onset+bar.duration
            chord = parse_chord(name)
            fit = score_chord_fit(notes,chord,onset,until-onset,bar.meter)
            fits.append(fit)
            if fit<.55:
                warnings.append(f'{voice_id} bar {bar.index+1}: low melody/chord fit {fit:.3f} over {name}')
    return (sum(fits)/len(fits) if fits else .5),warnings


def _analysis_of_fitted_tones(base: Score, bars: tuple[Measure, ...], tones: tuple[Tone, ...]) -> MelodyAnalysis:
    notes = tuple(Note(t.midi,'C',None,t.onset,t.duration,False,False,SourceSpan(0,0))
                  for t in tones if t.midi is not None)
    if not notes:
        raise ValueError('Fitted anchor has no sounding notes to harmonize')
    normalized_bars = tuple(replace(b,onset=b.onset-bars[0].onset) for b in bars)
    score = replace(base,voices=(Voice('melody',normalized_bars),))
    return MelodyAnalysis(score,'melody',notes,bars[0].key.text,(notes[-1].pitch_class,),())


def compose_song(base_abc: str, anchors: tuple[MelodyAnchor, ...], global_key: str = '',
                 transpose_policy: str = 'suggest', strictness: str = 'strict') -> CompositionResult:
    if strictness not in ('strict','warnings_as_errors'):
        raise ValueError('strictness must be strict or warnings_as_errors')
    if transpose_policy not in ('none','suggest','automatic_nearest'):
        raise ValueError('Unknown composer transpose_policy')
    if not isinstance(anchors,tuple) or not all(isinstance(a,MelodyAnchor) for a in anchors):
        raise TypeError('Expected an anchor collection')
    base = parse_abc(base_abc)
    require_valid(base,native=True)
    if not any(s.name!='unsectioned' for s in base.sections):
        raise ValueError('Base plan needs named sections from a complete YuE2 ABC plan')
    key = parse_key(global_key) if global_key.strip() else None
    report = ['GLOBAL KEY: '+(key.text if key else 'base local keys'), 'ANCHORS']
    warnings: list[str] = [i.message for i in validate_score(base,native=True) if i.severity=='warning']
    edits = {}
    expected: dict[tuple[str,int],tuple[Tone, ...]] = {}
    sources: dict[str,str] = {}
    for anchor in anchors:
        targets = [s for s in base.sections if s.name==anchor.section and (anchor.occurrence=='all' or s.occurrence==int(anchor.occurrence))]
        if not targets:
            raise ValueError(f'Anchor target not found: section={anchor.section}, occurrence={anchor.occurrence}')
        abc = anchor.abc
        if anchor.source and anchor.mode!='AI':
            if abc.strip():
                raise ValueError('Specify ABC or source anchor ID, not both')
            if anchor.source not in sources:
                raise ValueError(f'Source anchor must precede this anchor: {anchor.source}')
            abc = sources[anchor.source]
        for section in targets:
            report.append(f'{section.id} {anchor.mode} -> {anchor.target_voice}')
            if anchor.mode=='AI':
                continue
            if anchor.target_voice=='Ins' and anchor.harmony_policy in ('remove_chords','reharmonize'):
                raise ValueError('Harmony edits require target_voice=Vocal; Ins anchors support keep_base/recommend_only')
            sources[section.id] = abc
            selected = section.range_for(anchor.target_voice)
            bars = base.voice(anchor.target_voice).measures[selected.start_measure:selected.end_measure]
            if bars[0].notes and bars[0].notes[0].tie_from_previous or bars[-1].notes and bars[-1].notes[-1].tie_to_next:
                raise ValueError(f'{section.id}: tie crosses target boundary; cannot replace safely')
            if any((anchor.target_voice,b.index) in edits for b in bars):
                raise ValueError(f'Overlapping active anchors at {section.id}/{anchor.target_voice}')
            for c in base.changes:
                if c.voice_id==anchor.target_voice and any(b.span.start<=c.span.start<b.span.end for b in bars):
                    raise ValueError(f'{section.id}: inline {c.kind}: change in edited measure needs explicit adaptation')
            source = parse_abc(abc)
            require_valid(source)
            tones,source_bars = _tones(source,anchor.source_voice)
            source_tempos = [c.value for c in source.changes if c.kind=='Q']
            target_tempos = [c.value for c in base.changes if c.kind=='Q' and c.voice_id in (None,anchor.target_voice) and c.onset<=bars[0].onset]
            if source_tempos and target_tempos and source_tempos[0]!=target_tempos[-1]:
                warnings.append(f'{section.id}: anchor/base tempos differ; symbolic beat rhythm retained at base tempo')
            tones = _fit(tones,source_bars,bars,anchor.fit_policy)
            report.append(f'  LENGTH: {len(source_bars)}/{len(bars)} bars; fit_policy={anchor.fit_policy}')
            target_key = key or bars[0].key
            source_key = source_bars[0].key
            effective_key = source_key
            policy = anchor.transpose_policy if anchor.transpose_policy!='suggest' else transpose_policy
            delta = (target_key.pitch_class-source_key.pitch_class+6)%12-6
            if source_key.pitch_class!=target_key.pitch_class or source_key.mode!=target_key.mode:
                message = f'{section.id}: {source_key.text} -> {target_key.text}; suggested transpose {delta:+d} semitones'
                if policy=='automatic_nearest':
                    if source_key.mode!=target_key.mode or any(b.key!=source_key for b in source_bars):
                        raise ValueError('Automatic transposition requires one source key and equal source/target modes')
                    tones = tuple(replace(t,midi=t.midi+delta if t.midi is not None else None) for t in tones)
                    if any(t.midi is not None and not 0<=t.midi<=127 for t in tones):
                        raise ValueError('Transposition exceeds MIDI pitch range')
                    report.append('  TRANSPOSE APPLIED: '+message)
                    effective_key = target_key
                else:
                    warnings.append(message+'; pitch preserved ('+policy+')')
            if anchor.mode=='VARIATION':
                if any(b.key!=source_key for b in source_bars) or any(c.kind=='K' and c.onset>0 for c in source.changes):
                    raise ValueError('VARIATION requires a single source key; LOCK supports key-changing sources')
                before_variation = tones
                tones,metric = generate_variation(tones,effective_key.tonic,effective_key.mode,
                                                 anchor.variation_amount*anchor.strength,anchor.seed)
                report.append(f'  Motif similarity {metric.overall:.3f}; contour {metric.contour:.3f}; '
                              f'rhythm {metric.rhythm:.3f}; important notes {metric.important_retention:.3f}; '
                              f'ending retained={metric.ending_retained}; seed={anchor.seed}')
                report.append(f'  VARIATION changed {sum(a.midi!=b.midi for a,b in zip(before_variation,tones))} notes; protected-only motifs remain unchanged.')
            fit,conflicts = _harmony_fit(base,'Vocal',bars,tones)
            report.append(f'  BASE HARMONY compatibility {fit:.3f}; policy={anchor.harmony_policy}')
            if anchor.harmony_policy=='recommend_only':
                warnings.extend(f'{section.id}: {w}' for w in conflicts)
                if any(t.midi is not None for t in tones):
                    recommendation = build_progressions(_analysis_of_fitted_tones(base,bars,tones),
                                                       target_key.tonic,target_key.mode,len(bars),count=1)[0]
                    report.append('  HARMONY SUGGESTION (not applied): '+' - '.join(c.name for c in recommendation.chords))
                else:
                    report.append('  HARMONY SUGGESTION: no retained melody notes after fitting')
            reharmony = None
            if anchor.harmony_policy=='reharmonize':
                reharmony = build_progressions(_analysis_of_fitted_tones(base,bars,tones),target_key.tonic,target_key.mode,len(bars),count=1)[0]
                report.append('  REHARMONIZE APPLIED: '+' - '.join(c.name for c in reharmony.chords))
            start = Fraction()
            for i,b in enumerate(bars):
                chords = b.chords
                if anchor.harmony_policy=='remove_chords':
                    chords = ()
                elif reharmony is not None:
                    chords = (ChordSymbol(reharmony.chords[i].name,b.onset,SourceSpan(0,0)),)
                edits[(anchor.target_voice,b.index)] = _emit_bar(b,tones,start,_unit_at(base,anchor.target_voice,b.onset),chords)
                start += b.duration
            expected[(anchor.target_voice,selected.start_measure)] = tones
    result_text = rewrite_measures(base,edits)
    final = parse_abc(result_text)
    require_valid(final,native=True)
    if tuple((s.name,s.occurrence,s.voice_ranges) for s in final.sections)!=tuple((s.name,s.occurrence,s.voice_ranges) for s in base.sections):
        raise ValueError('Internal invariant failure: section structure changed')
    for v in base.voices:
        after = final.voice(v.id)
        for b in v.measures:
            if (v.id,b.index) not in edits and _bar_signature(b)!=_bar_signature(after.measures[b.index]):
                raise ValueError(f'Internal invariant failure: non-target {v.id} bar {b.index+1} changed')
    for (voice_id,index),tones in expected.items():
        section = next(s for s in final.sections if s.range_for(voice_id).start_measure==index)
        r = section.range_for(voice_id)
        bars = final.voice(voice_id).measures[r.start_measure:r.end_measure]
        wanted = tuple((t.midi,t.onset+bars[0].onset,t.duration) for t in tones if t.midi is not None)
        if _sounding_signature(bars)!=wanted:
            raise ValueError(f'Internal invariant failure: anchor melody changed in {section.id}')
    if warnings and strictness=='warnings_as_errors':
        raise ValueError('Composition warnings treated as errors:\n'+'\n'.join(warnings))
    report += ['WARNINGS']+ (warnings or ['none'])
    return CompositionResult(result_text,'\n'.join(report),format_validation(validate_score(final,native=True)))
