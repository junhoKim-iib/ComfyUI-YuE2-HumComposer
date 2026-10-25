from ..humcomposer.composition.anchors import MelodyAnchor, append_anchor
from .analyze import CATEGORY


class CreateMelodyAnchor:
    CATEGORY = CATEGORY
    FUNCTION = 'create'
    RETURN_TYPES = ('YUE2_MELODY_ANCHOR',)
    RETURN_NAMES = ('anchor',)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {
            'abc': ('STRING',{'default':'','multiline':True}),
            'section': ('STRING',{'default':'chorus'}),
            'occurrence': ('STRING',{'default':'all'}),
            'mode': (['LOCK','VARIATION','AI'],),
            'strength': ('FLOAT',{'default':1.0,'min':0.0,'max':1.0,'step':.05}),
            'fit_policy': (['strict','pad_rest','repeat','stretch_rhythm','truncate'],),
            'transpose_policy': (['suggest','none','automatic_nearest'],),
            'harmony_policy': (['recommend_only','keep_base','remove_chords','reharmonize'],),
            'source_voice': (['auto','Vocal','Ins'],),
            'target_voice': (['Vocal','Ins'],),
            'variation_amount': ('FLOAT',{'default':.25,'min':0.0,'max':1.0,'step':.05}),
            'seed': ('INT',{'default':0,'min':0,'max':0xffffffffffffffff}),
            'source': ('STRING',{'default':'','tooltip':'Optional preceding anchor ID, e.g. chorus#1. Leave abc empty.'}),
        },'optional': {'enabled': ('BOOLEAN',{'default':True,'tooltip':'Disabled anchors do not require ABC and leave the base plan unchanged.'})}}

    def create(self, abc: str, section: str, occurrence: str = 'all', mode: str = 'LOCK',
               strength: float = 1, fit_policy: str = 'strict', transpose_policy: str = 'suggest',
               harmony_policy: str = 'recommend_only', source_voice: str = 'auto', target_voice: str = 'Vocal',
               variation_amount: float = .25, seed: int = 0, source: str = '', enabled: bool = True) -> tuple:
        if not enabled:
            return (None,)
        return (MelodyAnchor(section,occurrence,abc,mode,strength,fit_policy,transpose_policy,
                             harmony_policy,source_voice,target_voice,variation_amount,seed,source),)


class AppendMelodyAnchor:
    CATEGORY = CATEGORY
    FUNCTION = 'append'
    RETURN_TYPES = ('YUE2_ANCHORS',)
    RETURN_NAMES = ('anchors',)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {},'optional': {'anchor': ('YUE2_MELODY_ANCHOR',),'previous': ('YUE2_ANCHORS',)}}

    def append(self, anchor: MelodyAnchor | None = None, previous: tuple = ()) -> tuple:
        return (append_anchor(anchor,previous),)
