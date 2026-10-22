from dataclasses import dataclass
import math

from ..abc.parser import normalize_section_name


@dataclass(frozen=True)
class MelodyAnchor:
    section: str
    occurrence: str
    abc: str
    mode: str = 'LOCK'
    strength: float = 1.0
    fit_policy: str = 'strict'
    transpose_policy: str = 'suggest'
    harmony_policy: str = 'recommend_only'
    source_voice: str = 'auto'
    target_voice: str = 'Vocal'
    variation_amount: float = .25
    seed: int = 0
    source: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self,'section',normalize_section_name(self.section))
        object.__setattr__(self,'occurrence',str(self.occurrence))
        if not self.section:
            raise ValueError('Anchor section must not be empty')
        if self.occurrence != 'all' and (not self.occurrence.isdigit() or int(self.occurrence)<1):
            raise ValueError('occurrence must be a positive integer or all')
        if self.mode not in ('LOCK','VARIATION','AI'):
            raise ValueError('Unknown anchor mode')
        if self.fit_policy not in ('strict','pad_rest','repeat','stretch_rhythm','truncate'):
            raise ValueError('Unknown fit_policy')
        if self.transpose_policy not in ('none','suggest','automatic_nearest'):
            raise ValueError('Unknown transpose_policy')
        if self.harmony_policy not in ('keep_base','recommend_only','remove_chords','reharmonize'):
            raise ValueError('Unknown harmony_policy')
        if self.target_voice not in ('Vocal','Ins'):
            raise ValueError('Target voice must be Vocal or Ins')
        if not all(math.isfinite(n) and 0 <= n <= 1 for n in (self.strength,self.variation_amount)):
            raise ValueError('strength and variation_amount must be finite values between 0 and 1')
        if self.mode == 'LOCK' and self.strength != 1:
            raise ValueError('LOCK requires strength=1; strength scales VARIATION only')
        if self.mode != 'AI' and not self.abc.strip() and not self.source:
            raise ValueError('Active anchor needs ABC or an explicit source anchor ID')


def append_anchor(anchor: MelodyAnchor, previous: tuple[MelodyAnchor, ...] = ()) -> tuple[MelodyAnchor, ...]:
    if not isinstance(anchor,MelodyAnchor) or not isinstance(previous,tuple) or not all(isinstance(a,MelodyAnchor) for a in previous):
        raise TypeError('Expected MelodyAnchor and an anchor collection')
    return previous+(anchor,)
