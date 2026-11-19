"""Select a file or a microphone take for the existing humming transcriber."""
import re

from .analyze import CATEGORY


_RECORDING = re.compile(
    r'humcomposer-recordings/hum-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.wav \[temp\]'
)


class HumAudioInput:
    CATEGORY = CATEGORY
    FUNCTION = 'select_audio'
    RETURN_TYPES = ('AUDIO',)

    @classmethod
    def INPUT_TYPES(cls):
        from comfy_extras.nodes_audio import LoadAudio

        files = LoadAudio.define_schema().inputs[0].options
        return {
            'required': {
                'source': (['file', 'microphone'],),
                'recording': ('STRING', {'default': ''}),
            },
            'optional': {
                'file_audio': ('AUDIO',),
                'audio': (['', *files], {'audio_upload': True}),
                'enabled': ('BOOLEAN', {'forceInput': True}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, source=None, recording=None, audio=None):
        if source is None:
            return True
        if source == 'file':
            if not audio:
                return True
            from comfy_extras.nodes_audio import LoadAudio

            return LoadAudio.validate_inputs(audio)
        if source != 'microphone':
            return 'Select file or microphone.'
        if not isinstance(recording, str) or not _RECORDING.fullmatch(recording):
            return 'Record and stop a microphone take before running.'
        import folder_paths

        if not folder_paths.exists_annotated_filepath(recording):
            return 'The microphone take is missing. Run the workflow again to resend it.'
        return True

    @classmethod
    def IS_CHANGED(cls, source=None, audio=None, **_inputs):
        if source == 'file' and audio:
            from comfy_extras.nodes_audio import LoadAudio

            return LoadAudio.fingerprint_inputs(audio)

    def select_audio(self, source, recording, file_audio=None, enabled=True, audio=None):
        if not enabled:
            raise ValueError('Enable the melody audio before using this input.')
        if source == 'file':
            if audio:
                from comfy_extras.nodes_audio import LoadAudio

                return LoadAudio.execute(audio).result
            if file_audio is not None:
                return (file_audio,)
            raise ValueError('Select or upload an audio file.')
        if source != 'microphone':
            raise ValueError('Select file or microphone.')

        valid = self.VALIDATE_INPUTS(source, recording)
        if valid is not True:
            raise ValueError(valid)
        from comfy_extras.nodes_audio import RecordAudio

        return (RecordAudio.execute(recording).result[0],)
