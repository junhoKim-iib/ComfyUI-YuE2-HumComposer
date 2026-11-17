from ..humcomposer.composition.merge import compose_song
from ..humcomposer.composition.theme import plan_main_theme
from ..humcomposer.theory.key_detection import MelodyAnalysis
from .analyze import CATEGORY


class HumSongComposer:
    CATEGORY = CATEGORY
    FUNCTION = 'compose'
    RETURN_TYPES = ('STRING','STRING','STRING')
    RETURN_NAMES = ('final_abc','composition_report','validation_report')

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {
            'base_abc': ('STRING',{'multiline':True}),
            'global_key': ('STRING',{'default':'','tooltip':'Empty uses each target local key; e.g. C or A minor. Does not rewrite base key.'}),
            'transpose_policy': (['suggest','none','automatic_nearest'],),
            'strictness': (['strict','warnings_as_errors'],),
        },'optional': {'anchors': ('YUE2_ANCHORS',),
                      'main_theme': ('YUE2_HUM_ANALYSIS', {'tooltip': 'Main melody of the song; does not require a chorus or any particular section name.'})}}

    def compose(self, base_abc: str, anchors: tuple = (), global_key: str = '',
                transpose_policy: str = 'suggest', strictness: str = 'strict', main_theme=None) -> tuple:
        theme_report = ''
        if main_theme is not None:
            if not isinstance(main_theme, MelodyAnalysis):
                raise TypeError('main_theme must be a melody analysis from Hum Melody Analyze')
            plan = plan_main_theme(base_abc,main_theme.score.source,main_theme.voice_id,reserved=anchors)
            anchors = anchors + plan.anchors
            theme_report = plan.report + '\n\n'
        result = compose_song(base_abc,anchors,global_key,transpose_policy,strictness)
        return result.abc,theme_report+result.composition_report,result.validation_report
