from ..humcomposer.i18n import report_inputs, report_locale
from ..humcomposer.abc.parser import parse_abc
from ..humcomposer.abc.validation import require_valid
from .score import _preview
from .analyze import CATEGORY

EMPTY_SCORE = 'X:1\nT:New melody\nM:4/4\nL:1/16\nQ:1/4=104\nV:Vocal clef=treble\nK:C\nZ4|\n'


class ABCScoreEditor:
    CATEGORY = CATEGORY
    FUNCTION = 'edit'
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('edited_abc',)
    OUTPUT_NODE = True
    DESCRIPTION = 'Live staff, ABC and piano-roll editor. Output the current draft to YuE2 Generate Music.'

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return report_inputs({'required': {
            'abc': ('STRING', {'default': EMPTY_SCORE, 'multiline': True}),
            'follow_input': ('BOOLEAN', {'default': True, 'label_on': 'Use input ABC', 'label_off': 'Use draft'}),
        }, 'optional': {'source_abc': ('STRING', {'forceInput': True})}})

    def edit(self, abc: str, follow_input: bool = True, source_abc: str = '', extra_pnginfo=None, unique_id=None, report_language=None) -> dict:
        output = source_abc if follow_input and source_abc else abc
        require_valid(parse_abc(output, polyphonic=True))
        payload = _preview(output, report_locale(extra_pnginfo, unique_id, report_language))
        payload.update(inputSource=source_abc, followInput=follow_input)
        return {'ui': {'editor': [payload]}, 'result': (output,)}
