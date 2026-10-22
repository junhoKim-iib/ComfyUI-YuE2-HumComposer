from ..humcomposer.composition.merge import compose_song
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
            'anchors': ('YUE2_ANCHORS',),
            'global_key': ('STRING',{'default':'','tooltip':'Empty uses each target local key; e.g. C or A minor. Does not rewrite base key.'}),
            'transpose_policy': (['suggest','none','automatic_nearest'],),
            'strictness': (['strict','warnings_as_errors'],),
        }}

    def compose(self, base_abc: str, anchors: tuple, global_key: str = '',
                transpose_policy: str = 'suggest', strictness: str = 'strict') -> tuple:
        result = compose_song(base_abc,anchors,global_key,transpose_policy,strictness)
        return result.abc,result.composition_report,result.validation_report
