"""Delegate transcription to the loaded encoder, with one explicit padding retry."""
from ..humcomposer.i18n import report_inputs, report_locale, translate
from .analyze import CATEGORY


class HumTranscribe:
    CATEGORY = CATEGORY
    FUNCTION = 'transcribe'
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('abc', 'transcription_report')
    OUTPUT_IS_LIST = (True, False)

    @classmethod
    def INPUT_TYPES(cls):
        return report_inputs({'required': {
            'audio_encoder': ('AUDIO_ENCODER',),
            'audio': ('AUDIO',),
            'mode': (['melody', 'full'],),
            'retry_tail_padding': ('BOOLEAN', {'default': True,
                'tooltip': 'Retry a known SheetSage2 export-grid error once with 0.5 s trailing silence. The recovered transcription may contain extra notes/bars; inspect the report.'}),
        }})

    def transcribe(self, audio_encoder, audio, mode='melody', retry_tail_padding=True, extra_pnginfo=None, unique_id=None, report_language=None):
        locale = report_locale(extra_pnginfo, unique_id, report_language)
        if mode not in ('melody', 'full'):
            raise ValueError('Transcription mode must be melody or full')
        if not isinstance(retry_tail_padding, bool):
            raise TypeError('retry_tail_padding must be a boolean')
        if not callable(getattr(audio_encoder, 'generate_abc', None)):
            raise TypeError('Connect a SheetSage2 audio encoder')
        waveform = audio['waveform']
        rate = audio['sample_rate']
        if (isinstance(rate, bool) or not isinstance(rate, int) or rate <= 0
                or len(waveform.shape) != 3 or not all(dimension > 0 for dimension in waveform.shape)):
            raise ValueError('Expected nonempty [batch, channels, samples] audio with a positive sample rate')
        report = translate('transcribe.original', locale)
        try:
            scores = audio_encoder.generate_abc(waveform, rate, melody_only=mode == 'melody')
        except ValueError as error:
            known_grid_error = (type(error).__name__ == 'MelodyVoiceError'
                                and type(error).__module__ == 'comfy.audio_encoders.sheetsage2_abc'
                                and 'cannot be represented on the decoded subbeat grid' in str(error))
            if not retry_tail_padding or not known_grid_error:
                raise
            extra = max(1, rate // 2)
            padded = waveform.new_zeros((*waveform.shape[:-1], waveform.shape[-1] + extra))
            padded[..., :waveform.shape[-1]] = waveform
            try:
                scores = audio_encoder.generate_abc(padded, rate, melody_only=mode == 'melody')
            except ValueError as retry_error:
                raise ValueError('SheetSage2 could not export the original audio or the single padded retry. '
                                 f'The input audio was retained. Original error: {error}; retry: {retry_error}') from retry_error
            report = translate('transcribe.recovered', locale, seconds=extra / rate, error=error)
        if (not isinstance(scores, list) or len(scores) != waveform.shape[0]
                or not all(isinstance(score, str) and score.strip() for score in scores)):
            raise ValueError('SheetSage2 did not return one nonempty ABC string per audio item')
        return scores, report
