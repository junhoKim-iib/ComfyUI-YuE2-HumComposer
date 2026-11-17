"""ComfyUI V1 nodes with a local, dependency-free SVG score viewer."""
from .nodes.analyze import HumMelodyAnalyze, KeyModeCandidates
from .nodes.harmony import ChordProgressionRecommend
from .nodes.anchors import CreateMelodyAnchor, AppendMelodyAnchor
from .nodes.compose import HumSongComposer
from .nodes.validation import ABCValidate
from .nodes.score import ABCScoreViewer
from .nodes.editor import ABCScoreEditor
from .nodes.transcribe import HumTranscribe
from .nodes.generate import HumGenerateABC
from .web_api import register_routes

WEB_DIRECTORY = './web'
register_routes()

NODE_CLASS_MAPPINGS = {
    'YuE2HumMelodyAnalyze': HumMelodyAnalyze,
    'YuE2KeyModeCandidates': KeyModeCandidates,
    'YuE2ChordProgressionRecommend': ChordProgressionRecommend,
    'YuE2MelodyAnchor': CreateMelodyAnchor,
    'YuE2AppendMelodyAnchor': AppendMelodyAnchor,
    'YuE2HumSongComposer': HumSongComposer,
    'YuE2ABCValidate': ABCValidate,
    'YuE2ABCScoreViewer': ABCScoreViewer,
    'YuE2ABCScoreEditor': ABCScoreEditor,
    'YuE2HumTranscribe': HumTranscribe,
    'YuE2HumGenerateABC': HumGenerateABC,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'YuE2HumMelodyAnalyze': 'YuE2 Hum Melody Analyze',
    'YuE2KeyModeCandidates': 'YuE2 Key & Mode Candidates',
    'YuE2ChordProgressionRecommend': 'YuE2 Chord Progression Recommend',
    'YuE2MelodyAnchor': 'YuE2 Melody Anchor',
    'YuE2AppendMelodyAnchor': 'YuE2 Append Melody Anchor',
    'YuE2HumSongComposer': 'YuE2 Hum Song Composer',
    'YuE2ABCValidate': 'YuE2 ABC Validate',
    'YuE2ABCScoreViewer': 'YuE2 ABC Score Viewer',
    'YuE2ABCScoreEditor': 'YuE2 ABC Score Editor',
    'YuE2HumTranscribe': 'YuE2 Hum Transcribe',
    'YuE2HumGenerateABC': 'YuE2 Hum Generate Required ABC',
}
