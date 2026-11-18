from ..humcomposer.i18n import report_inputs, report_locale, translate
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
        return report_inputs({'required': {'abc': ('STRING',{'multiline':True}),
                             'voice': (['auto','Vocal','Ins'],)},
                'optional': {'enabled': ('BOOLEAN', {'default': True,
                    'tooltip': 'Use this melody. False skips upstream audio validation and transcription.'}),
                             'source_report': ('STRING', {'forceInput': True})}})

    def analyze(self, abc: str, voice: str = 'auto', enabled: bool = True, source_report: str = '',
                extra_pnginfo=None, unique_id=None, report_language=None) -> tuple:
        locale = report_locale(extra_pnginfo, unique_id, report_language)
        if not enabled or not abc.strip():
            return None,translate('analysis.empty', locale),''
        analysis = analyze_melody(abc,voice)
        summary = analysis_report(analysis, locale)
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
        return report_inputs({'required': {'analysis': ('YUE2_HUM_ANALYSIS',),
                             'include_modes': ('BOOLEAN',{'default':False}),
                             'candidate_count': ('INT',{'default':5,'min':1,'max':84})}})

    def recommend(self, analysis, include_modes: bool = False, candidate_count: int = 5, extra_pnginfo=None, unique_id=None, report_language=None) -> tuple:
        locale = report_locale(extra_pnginfo, unique_id, report_language)
        if analysis is None:
            return (),translate('keys.empty', locale)
        candidates = rank_keys(analysis,include_modes,candidate_count,locale)
        return candidates,key_report(candidates,locale)
