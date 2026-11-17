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
                             'voice': (['auto','Vocal','Ins'],)},
                'optional': {'enabled': ('BOOLEAN', {'default': True,
                    'tooltip': 'Use this melody. False skips upstream audio validation and transcription.'}),
                             'source_report': ('STRING', {'forceInput': True})}}

    def analyze(self, abc: str, voice: str = 'auto', enabled: bool = True, source_report: str = '') -> tuple:
        if not enabled or not abc.strip():
            return None,'No melody input; the generated base plan is retained.',''
        analysis = analyze_melody(abc,voice)
        summary = analysis_report(analysis)
        if source_report:
            summary += '\n\n' + source_report
        return analysis,summary,serialize(analysis.score)


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
        if analysis is None:
            return (),'No melody input; no key or mode candidates.'
        candidates = rank_keys(analysis,include_modes,candidate_count)
        return candidates,key_report(candidates)
