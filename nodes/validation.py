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
        return {'required': {'abc': ('STRING',{'multiline':True}),
                             'native_song': ('BOOLEAN',{'default':True})}}

    def validate(self, abc: str, native_song: bool = True) -> dict:
        try:
            score = parse_abc(abc)
        except ABCParseError as error:
            report = f'FAIL\nERROR [{error.code}] offset {error.offset}: {error}'
            return {'ui':{'text':[report]},'result':(False,report)}
        issues = validate_score(score,native=native_song)
        report = format_validation(issues)
        return {'ui':{'text':[report]},'result':(not any(i.severity=='error' for i in issues),report)}
