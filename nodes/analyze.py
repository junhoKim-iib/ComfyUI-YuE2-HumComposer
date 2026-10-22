from ..humcomposer.abc.serializer import serialize
from ..humcomposer.theory.key_detection import analyze_melody, analysis_report, rank_keys, key_report

CATEGORY = 'audio/YuE2/Hum Composer'


class HumMelodyAnalyze:
    CATEGORY = CATEGORY
    FUNCTION = 'analyze'
    RETURN_TYPES = ('YUE2_HUM_ANALYSIS','STRING','STRING')
    RETURN_NAMES = ('analysis','summary','normalized_abc')

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {'abc': ('STRING',{'multiline':True}),
                             'voice': (['auto','Vocal','Ins'],)}}

    def analyze(self, abc: str, voice: str = 'auto') -> tuple:
        analysis = analyze_melody(abc,voice)
        return analysis,analysis_report(analysis),serialize(analysis.score)


class KeyModeCandidates:
    CATEGORY = CATEGORY
    FUNCTION = 'recommend'
    RETURN_TYPES = ('YUE2_KEY_CANDIDATES','STRING')
    RETURN_NAMES = ('candidates','report')

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {'analysis': ('YUE2_HUM_ANALYSIS',),
                             'include_modes': ('BOOLEAN',{'default':False}),
                             'candidate_count': ('INT',{'default':5,'min':1,'max':84})}}

    def recommend(self, analysis, include_modes: bool = False, candidate_count: int = 5) -> tuple:
        candidates = rank_keys(analysis,include_modes,candidate_count)
        return candidates,key_report(candidates)
