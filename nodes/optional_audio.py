"""Exclude unused melody audio paths before ComfyUI validates input files."""


def prepare_optional_audio(data: dict) -> dict:
    prompt = data.get('prompt')
    if not isinstance(prompt, dict):
        return data
    updated = None
    candidates = set()

    def collect_audio(node_id):
        node = prompt.get(node_id, {})
        if node_id in candidates or node.get('class_type') not in (
                'LoadAudio', 'AudioEncoderLoader', 'SheetSage2AudioToABC',
                'YuE2HumAudioInput', 'YuE2HumTranscribe'):
            return
        candidates.add(node_id)
        for value in node.get('inputs', {}).values():
            if isinstance(value, list) and len(value) == 2:
                collect_audio(value[0])

    for node_id, node in prompt.items():
        if node.get('class_type') != 'YuE2HumMelodyAnalyze':
            continue
        inputs = node.get('inputs', {})
        enabled = inputs.get('enabled', True)
        if isinstance(enabled, list) and len(enabled) == 2 and enabled[1] == 0:
            control = prompt.get(enabled[0], {})
            if control.get('class_type') == 'PrimitiveBoolean':
                enabled = control.get('inputs', {}).get('value')
        if enabled is not False:
            continue
        # Lazy execution alone cannot skip the native LoadAudio file validator.
        # Change only the queued copy; retain the user's canvas connections.
        if updated is None:
            updated = dict(prompt)
        disconnected = {**inputs, 'abc': ''}
        if 'source_report' in disconnected:
            disconnected['source_report'] = ''
        updated[node_id] = {**node, 'inputs': disconnected}
        abc = inputs.get('abc')
        if isinstance(abc, list) and len(abc) == 2:
            collect_audio(abc[0])

    for node_id, node in prompt.items():
        if node.get('class_type') != 'YuE2HumAudioInput':
            continue
        inputs = node.get('inputs', {})
        legacy_link = inputs.get('file_audio')
        if not isinstance(legacy_link, list) or len(legacy_link) != 2:
            continue
        source, audio = inputs.get('source'), inputs.get('audio')
        if source != 'microphone' and not (source == 'file' and isinstance(audio, str) and audio):
            continue
        if updated is None:
            updated = dict(prompt)
        updated[node_id] = {**node, 'inputs': {key: value for key, value in inputs.items() if key != 'file_audio'}}
        collect_audio(legacy_link[0])

    # Unused native loaders must also skip cache fingerprints of empty files.
    # Keep shared sources whenever any other consumer still references them.
    while updated is not None and candidates:
        referenced = {value[0] for node in updated.values() for value in node.get('inputs', {}).values()
                      if isinstance(value, list) and len(value) == 2}
        unused = candidates - referenced
        if not unused:
            break
        for node_id in unused:
            updated.pop(node_id)
        candidates -= unused
    return {**data, 'prompt': updated} if updated is not None else data
