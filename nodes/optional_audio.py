"""Optional file input that expands to official audio nodes only when selected."""
import os
from pathlib import Path
import sys

from .analyze import CATEGORY


def audio_files() -> list[str]:
    paths = sys.modules.get('folder_paths')
    if paths is None:  # Headless symbolic tools have no ComfyUI input directory.
        return []
    directory = paths.get_input_directory()
    if not os.path.isdir(directory):
        return []
    return sorted(paths.filter_files_content_types(os.listdir(directory),['audio','video']))


class OptionalAudioToABC:
    CATEGORY = CATEGORY
    FUNCTION = 'transcribe'
    RETURN_TYPES = ('STRING','BOOLEAN')
    RETURN_NAMES = ('abc','has_audio')
    DESCRIPTION = 'Leave audio empty for AI generation. A selected file uses official Load Audio and SheetSage2 nodes.'

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {'required': {
            'audio': (['',*audio_files()],{'default':'','audio_upload':True}),
            'mode': (['melody','full'],),
            'audio_encoder_name': ('STRING',{'default':'sheetsage2_bf16.safetensors'}),
        }}

    @classmethod
    def IS_CHANGED(cls, audio: str = '', **kwargs):
        # Native LoadAudio fingerprints the content; expand again to let it check.
        return float('nan') if audio else ''

    def transcribe(self, audio: str = '', mode: str = 'melody',
                   audio_encoder_name: str = 'sheetsage2_bf16.safetensors'):
        if not isinstance(audio,str) or mode not in ('melody','full'):
            raise ValueError('Expected an optional audio filename and melody/full mode')
        if not audio:
            return '',False
        if audio not in audio_files():
            raise ValueError('Select an existing uploaded audio file from the input directory')
        import folder_paths
        root = Path(folder_paths.get_input_directory()).resolve()
        path = (root/audio).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Audio must be a file inside the ComfyUI input directory')
        if audio_encoder_name not in folder_paths.get_filename_list('audio_encoders'):
            raise ValueError('Selected SheetSage2 audio encoder is not installed')
        from comfy_execution.graph_utils import GraphBuilder
        graph = GraphBuilder()
        loaded = graph.node('LoadAudio',audio=audio)
        encoder = graph.node('AudioEncoderLoader',audio_encoder_name=audio_encoder_name)
        transcribed = graph.node('SheetSage2AudioToABC',audio_encoder=encoder.out(0),audio=loaded.out(0),mode=mode)
        return {'result':(transcribed.out(0),True),'expand':graph.finalize()}
