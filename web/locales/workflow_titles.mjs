export const nodeTitles = [
    { type: 'YuE2HumAudioInput', key: 'workflow.node.mainAudioInput' },
    { type: 'YuE2HumAudioInput', key: 'workflow.node.introAudioInput' },
    { type: 'YuE2HumAudioInput', key: 'workflow.node.bridgeAudioInput' },
    {
        "type": "PrimitiveBoolean",
        "key": "workflow.node.mainAudioEnabled"
    },
    {
        "type": "LoadAudio",
        "key": "workflow.node.mainAudioFile"
    },
    {
        "type": "AudioEncoderLoader",
        "key": "workflow.node.encoderLoader"
    },
    {
        "type": "YuE2HumTranscribe",
        "key": "workflow.node.mainTranscribe"
    },
    {
        "type": "YuE2HumMelodyAnalyze",
        "key": "workflow.node.mainAnalysis"
    },
    {
        "type": "PrimitiveBoolean",
        "key": "workflow.node.introEnabled"
    },
    {
        "type": "LoadAudio",
        "key": "workflow.node.introAudio"
    },
    {
        "type": "YuE2HumTranscribe",
        "key": "workflow.node.introTranscribe"
    },
    {
        "type": "YuE2HumMelodyAnalyze",
        "key": "workflow.node.introAnalysis"
    },
    {
        "type": "PrimitiveBoolean",
        "key": "workflow.node.bridgeEnabled"
    },
    {
        "type": "LoadAudio",
        "key": "workflow.node.bridgeAudio"
    },
    {
        "type": "YuE2HumTranscribe",
        "key": "workflow.node.bridgeTranscribe"
    },
    {
        "type": "YuE2HumMelodyAnalyze",
        "key": "workflow.node.bridgeAnalysis"
    },
    {
        "type": "YuE2KeyModeCandidates",
        "key": "workflow.node.keyCandidates"
    },
    {
        "type": "YuE2ChordProgressionRecommend",
        "key": "workflow.node.chordRecommendation"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.keyReport"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.chordReport"
    },
    {
        "type": "YuE2MelodyAnchor",
        "key": "workflow.node.introAnchor"
    },
    {
        "type": "YuE2AppendMelodyAnchor",
        "key": "workflow.node.appendIntro"
    },
    {
        "type": "YuE2MelodyAnchor",
        "key": "workflow.node.bridgeAnchor"
    },
    {
        "type": "YuE2AppendMelodyAnchor",
        "key": "workflow.node.appendBridge"
    },
    {
        "type": "YuE2MelodyAnchor",
        "key": "workflow.node.verseAnchor"
    },
    {
        "type": "YuE2AppendMelodyAnchor",
        "key": "workflow.node.appendVerse"
    },
    {
        "type": "PrimitiveStringMultiline",
        "key": "workflow.node.style"
    },
    {
        "type": "PrimitiveStringMultiline",
        "key": "workflow.node.lyrics"
    },
    {
        "type": "StringConcatenate",
        "key": "workflow.node.styleWithChords"
    },
    {
        "type": "YuE2HumGenerateABC",
        "key": "workflow.node.generateAbc"
    },
    {
        "type": "YuE2HumSongComposer",
        "key": "workflow.node.compose"
    },
    {
        "type": "YuE2ABCValidate",
        "key": "workflow.node.validate"
    },
    {
        "type": "YuE2GenerateMusic",
        "key": "workflow.node.generateMusic"
    },
    {
        "type": "EmptyYuE2LatentAudio",
        "key": "workflow.node.latent"
    },
    {
        "type": "PreviewAudio",
        "key": "workflow.node.previewAudio"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.baseAbc"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.generationReport"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.compositionReport"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.finalAbc"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.mainReport"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.introReport"
    },
    {
        "type": "PreviewAny",
        "key": "workflow.node.bridgeReport"
    },
    {
        "type": "YuE2ABCScoreEditor",
        "key": "workflow.node.scoreEditor"
    },
    {
        "type": "LoadAudio",
        "key": "workflow.node.introAudioOptional"
    },
    {
        "type": "LoadAudio",
        "key": "workflow.node.bridgeAudioOptional"
    }
];

export const groupTitles = [
    "workflow.group.models",
    "workflow.group.audio",
    "workflow.group.harmony",
    "workflow.group.generate",
    "workflow.group.anchors",
    "workflow.group.compose",
    "workflow.group.music",
    "workflow.group.editor",
    "workflow.group.optionalAnchors"
];

export const previousWorkflowTitles = {
    "workflow.node.appendIntro": ["1. Intro anchor", "1. Intro 앵커"],
    "workflow.node.appendVerse": ["3. Selected anchors → merge", "3. 선택 앵커 → 병합"],
    "workflow.group.anchors": ["05 Section anchors · Intro / Bridge", "05 선택 구간 앵커 · Intro / Bridge"],
    "workflow.group.optionalAnchors": ["05 Optional section anchors · Intro / Bridge", "05 선택 구간 앵커 · Intro / Bridge (선택사항)"]
};
