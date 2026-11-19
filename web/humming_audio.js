import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';
import { onLocaleChange, t } from './i18n.mjs?v=20261119-i18n2';

const NODE_NAME = 'YuE2HumAudioInput';
const RECORDINGS = 'humcomposer-recordings';
const WORKLET_URL = new URL('./humming_capture_worklet.mjs', import.meta.url);

function stopTracks(stream) {
    for (const track of stream?.getTracks() ?? []) track.stop();
}

function makeWav(blocks, sampleRate) {
    const byteLength = blocks.reduce((total, block) => total + block.byteLength, 0);
    if (!byteLength) return null;
    const header = new DataView(new ArrayBuffer(44));
    header.setUint32(0, 0x52494646); // RIFF
    header.setUint32(4, byteLength + 36, true);
    header.setUint32(8, 0x57415645); // WAVE
    header.setUint32(12, 0x666d7420); // fmt
    header.setUint32(16, 16, true);
    header.setUint16(20, 1, true); // PCM
    header.setUint16(22, 1, true); // Mono
    header.setUint32(24, sampleRate, true);
    header.setUint32(28, sampleRate * 2, true);
    header.setUint16(32, 2, true);
    header.setUint16(34, 16, true);
    header.setUint32(36, 0x64617461); // data
    header.setUint32(40, byteLength, true);
    return new Blob([header.buffer, ...blocks], { type: 'audio/wav' });
}

function recordingError(error) {
    if (error.name === 'NotAllowedError' || error.name === 'SecurityError') return 'humming.permission';
    if (error.name === 'NotFoundError') return 'humming.deviceMissing';
    return 'humming.captureFailed';
}

async function uploadTake(take) {
    const body = new FormData();
    body.append('image', take.wav, take.name);
    body.append('type', 'temp');
    body.append('subfolder', RECORDINGS);
    const response = await api.fetchApi('/upload/image', { method: 'POST', body });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const { name, type, subfolder } = await response.json();
    if (name !== take.name || type !== 'temp' || subfolder !== RECORDINGS) {
        throw new Error('Unexpected recording upload response');
    }
    return `${subfolder}/${name} [temp]`;
}

function attachRecorder(node) {
    const source = node.widgets.find(widget => widget.name === 'source');
    const fileWidgets = node.widgets.filter(widget => ['audio', 'audioUI', 'upload'].includes(widget.name));
    const filePlayer = fileWidgets.find(widget => widget.name === 'audioUI').element;
    fileWidgets.find(widget => widget.name === 'upload').serialize = false;
    const recording = node.widgets.find(widget => widget.name === 'recording');
    recording.type = 'hidden';
    recording.computeSize = () => [0, -4];
    recording.serialize = false;

    const host = document.createElement('div');
    host.style.cssText = 'box-sizing:border-box;width:100%;padding:4px 0;color:var(--input-text);font:13px sans-serif';
    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px';
    const status = document.createElement('div');
    status.setAttribute('role', 'status');
    status.style.margin = '5px 0';
    const player = document.createElement('audio');
    player.controls = true;
    player.preload = 'none';
    player.style.cssText = 'width:100%;height:32px';
    host.append(actions, status, player);

    let session;
    let take;
    let errorKey;

    function button(handler) {
        const element = document.createElement('button');
        element.type = 'button';
        element.style.cssText = 'border:1px solid var(--border-color, #777);border-radius:5px;padding:4px 8px;color:inherit;background:var(--comfy-input-bg, #252525)';
        element.addEventListener('click', handler);
        actions.append(element);
        return element;
    }

    const start = button(startCapture);
    const stop = button(stopCapture);
    const cancel = button(() => {
        releaseCapture();
        errorKey = undefined;
        render();
    });
    const save = button(() => {
        if (!take) return;
        const link = document.createElement('a');
        link.href = take.url;
        link.download = take.name;
        link.click();
    });

    function render() {
        const microphone = source.value === 'microphone';
        for (const widget of fileWidgets) widget.hidden = microphone;
        recorderWidget.hidden = !microphone;
        host.hidden = !microphone;
        start.textContent = t(take ? 'humming.recordAgain' : 'humming.record');
        start.hidden = Boolean(session);
        stop.textContent = t('humming.stop');
        stop.hidden = session?.phase !== 'recording';
        cancel.textContent = t('humming.cancel');
        cancel.hidden = !session;
        save.textContent = t('humming.saveWav');
        save.hidden = !take;
        player.hidden = !microphone || !take;
        player.setAttribute('aria-label', t('humming.playback'));
        const recordingStatus = session ? `humming.${session.phase}` :
            take ? 'humming.ready' : 'humming.empty';
        status.textContent = t(errorKey ?? recordingStatus);
    }

    function releaseCapture() {
        if (!session) return;
        const capture = session;
        session = undefined;
        clearTimeout(capture.stopTimer);
        stopTracks(capture.stream);
        capture.worklet?.port.close();
        if (capture.context && capture.context.state !== 'closed') {
            capture.context.close().catch(error => console.warn('YuE2 microphone cleanup:', error));
        }
    }

    function failCapture(key) {
        releaseCapture();
        errorKey = key;
        render();
    }

    async function startCapture() {
        if (session) return;
        if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
            failCapture('humming.unsupported');
            return;
        }

        player.pause();
        errorKey = undefined;
        const capture = { phase: 'starting', blocks: [] };
        session = capture;
        render();
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { channelCount: { ideal: 1 }, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
            });
            if (session !== capture) {
                stopTracks(stream);
                return;
            }
            capture.stream = stream;
            for (const track of stream.getAudioTracks()) {
                track.addEventListener('ended', () => {
                    if (session === capture) failCapture('humming.deviceMissing');
                }, { once: true });
            }
            const context = new AudioContext();
            capture.context = context;
            await context.audioWorklet.addModule(WORKLET_URL);
            if (session !== capture) return;

            const worklet = new AudioWorkletNode(context, 'yu-e2-humming-capture', {
                channelCount: 1, channelCountMode: 'explicit', outputChannelCount: [1],
            });
            capture.worklet = worklet;
            worklet.onprocessorerror = () => {
                if (session === capture) failCapture('humming.captureFailed');
            };
            worklet.port.onmessage = ({ data }) => {
                if (session !== capture) return;
                if (data instanceof ArrayBuffer) capture.blocks.push(data);
                else if (data === 'finished') finishCapture(capture);
            };
            context.createMediaStreamSource(stream).connect(worklet);
            worklet.connect(context.destination);
            await context.resume();
            if (session !== capture) return;

            capture.phase = 'recording';
            render();
        } catch (error) {
            if (session === capture) failCapture(recordingError(error));
        }
    }

    function stopCapture() {
        if (session?.phase !== 'recording') return;
        session.phase = 'finishing';
        session.stopTimer = setTimeout(() => failCapture('humming.captureFailed'), 3000);
        stopTracks(session.stream);
        session.worklet.port.postMessage('finish');
        render();
    }

    function finishCapture(capture) {
        const wav = makeWav(capture.blocks, capture.context.sampleRate);
        releaseCapture();
        if (!wav) {
            failCapture('humming.noSamples');
            return;
        }
        player.pause();
        if (take) URL.revokeObjectURL(take.url);
        take = { wav, url: URL.createObjectURL(wav), name: `hum-${crypto.randomUUID()}.wav` };
        player.src = take.url;
        render();
    }

    const valueChanged = source.callback;
    source.callback = function () {
        const result = valueChanged?.apply(this, arguments);
        if (source.value !== 'microphone') {
            releaseCapture();
            player.pause();
        } else {
            filePlayer.pause();
        }
        render();
        node.expandToFitContent?.();
        node.setDirtyCanvas(true, true);
        return result;
    };

    recording.serializeValue = async () => {
        if (source.value !== 'microphone' || !node.outputs[0]?.links?.length) return '';
        const enabledIndex = node.findInputSlot('enabled');
        const toggle = enabledIndex >= 0 ? node.getInputNode(enabledIndex) : null;
        if (toggle?.type === 'PrimitiveBoolean' &&
            toggle.widgets?.find(widget => widget.name === 'value')?.value === false) return '';
        if (session || !take) {
            errorKey = session ? 'humming.stopBeforeRunning' : 'humming.recordBeforeRunning';
            render();
            throw new Error(t(errorKey));
        }
        try {
            const path = await uploadTake(take);
            errorKey = undefined;
            render();
            return path;
        } catch (error) {
            errorKey = 'humming.uploadFailed';
            render();
            throw new Error(t(errorKey), { cause: error });
        }
    };

    const recorderWidget = node.addDOMWidget('humming', 'humming', host, {
        serialize: false, hideInPanel: true, getMinHeight: () => 92,
    });
    const onConfigure = node.onConfigure;
    node.onConfigure = function () {
        const result = onConfigure?.apply(this, arguments);
        render();
        return result;
    };
    const unsubscribe = onLocaleChange(render);
    const onRemoved = node.onRemoved;
    node.onRemoved = function () {
        releaseCapture();
        player.pause();
        filePlayer.pause();
        if (take) URL.revokeObjectURL(take.url);
        unsubscribe();
        return onRemoved?.apply(this, arguments);
    };
    render();
}

app.registerExtension({
    name: 'YuE2.HumComposer.AudioInput',
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        // The native uploader expects its audio preview widget to be created first.
        nodeData.input.optional.audioUI = ['AUDIO_UI', {}];
        nodeData.input.optional.upload = ['AUDIOUPLOAD', {}];
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onCreated?.apply(this, arguments);
            attachRecorder(this);
            return result;
        };
    },
});
