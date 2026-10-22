from ..humcomposer.theory.harmony import build_progressions, harmony_report
from ..humcomposer.theory.key_detection import rank_keys
from ..humcomposer.theory.pitch import SCALES
from .analyze import CATEGORY


class ChordProgressionRecommend:
    CATEGORY = CATEGORY
    FUNCTION = 'recommend'
    RETURN_TYPES = ('YUE2_CHORD_RECOMMENDATIONS','STRING')
    RETURN_NAMES = ('recommendations','report')

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {
            'analysis': ('YUE2_HUM_ANALYSIS',),
            'selected_key': ('STRING',{'default':'auto'}),
            'selected_mode': (['auto',*SCALES],),
            'bars': ('INT',{'default':4,'min':1,'max':256}),
            'complexity': (['triads','sevenths'],),
            'candidate_count': ('INT',{'default':3,'min':1,'max':20}),
            'candidate_index': ('INT',{'default':1,'min':1,'max':84}),
        },'optional': {'candidates': ('YUE2_KEY_CANDIDATES',)}}

    def recommend(self, analysis, selected_key: str = 'auto', selected_mode: str = 'auto',
                  bars: int = 4, complexity: str = 'triads', candidate_count: int = 3,
                  candidate_index: int = 1, candidates=None) -> tuple:
        if selected_key.strip()=='auto' or selected_mode=='auto':
            choices = candidates if candidates is not None else rank_keys(analysis,True,84)
            if not 1<=candidate_index<=len(choices):
                raise ValueError('candidate_index is outside the available key candidates')
            choice = choices[candidate_index-1]
            if selected_key.strip()=='auto':
                selected_key = choice.tonic
            if selected_mode=='auto':
                selected_mode = choice.mode
        results = build_progressions(analysis,selected_key,selected_mode,bars,complexity,candidate_count)
        return results,f'{selected_key} {selected_mode}\n'+harmony_report(results)
