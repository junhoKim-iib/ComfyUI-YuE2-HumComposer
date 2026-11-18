from ..humcomposer.i18n import report_inputs, report_locale, translate
from ..humcomposer.abc.parser import parse_abc, ABCParseError
from ..humcomposer.abc.validation import validate_score, format_validation
from .analyze import CATEGORY


class ABCValidate:
    CATEGORY = CATEGORY
    FUNCTION = 'validate'
    RETURN_TYPES = ('BOOLEAN','STRING')
    RETURN_NAMES = ('valid','report')
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return report_inputs({'required': {'abc': ('STRING',{'multiline':True}),
                             'native_song': ('BOOLEAN',{'default':True})}})

    def validate(self, abc: str, native_song: bool = True, extra_pnginfo=None, unique_id=None, report_language=None) -> dict:
        locale = report_locale(extra_pnginfo, unique_id, report_language)
        try:
            score = parse_abc(abc, polyphonic=True)
        except ABCParseError as error:
            report = translate('validation.failed', locale) + f'\nERROR [{error.code}] offset {error.offset}: {error}'
            return {'ui':{'text':[report]},'result':(False,report)}
        issues = validate_score(score,native=native_song)
        report = format_validation(issues, locale)
        return {'ui':{'text':[report]},'result':(not any(i.severity=='error' for i in issues),report)}
