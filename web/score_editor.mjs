import { createScoreView } from './score_renderer.mjs';

const NS = 'http://www.w3.org/2000/svg';
const value = (n) => n[0] / n[1];
const gcd = (a, b) => b ? gcd(b, a % b) : Math.abs(a);
const ratio = (n, d = 1) => { const g = gcd(n, d); return [n / g, d / g]; };
const add = (a, b) => ratio(a[0] * b[1] + b[0] * a[1], a[1] * b[1]);
const names = ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B'];
const pitchName = (midi) => names[midi % 12] + (Math.floor(midi / 12) - 1);

export function createScoreEditor({ initialAbc, request, onChange, followInput, setFollowInput }) {
    const element = document.createElement('div');
    element.style.cssText = 'width:100%;height:100%;min-height:660px';
    const shadow = element.attachShadow({ mode: 'open' });
    function html(tag, parent, content, cls) {
        const el = document.createElement(tag);
        if (content !== undefined) el.textContent = content;
        if (cls) el.className = cls;
        parent.append(el);
        return el;
    }
    for (const filename of ['score.css', 'score_editor.css']) {
        const link = html('link', shadow);
        link.rel = 'stylesheet'; link.href = new URL(filename, import.meta.url).href;
    }
    const root = html('div', shadow, undefined, 'editor');
    root.tabIndex = 0;
    root.setAttribute('aria-label', '실시간 악보 편집기');
    const toolbar = html('div', root, undefined, 'toolbar');
    html('strong', toolbar, '실시간 악보 · 피아노');
    const maximize = html('button', toolbar, '크게 편집');
    html('span', toolbar, '메뉴 크기');
    const menuSize = html('select', toolbar); menuSize.setAttribute('aria-label', '메뉴 크기');
    for (const size of ['auto', 100, 125, 150, 175, 200]) {
        html('option', menuSize, size === 'auto' ? '자동' : `${size}%`).value = size;
    }
    menuSize.addEventListener('change', () => {
        if (menuSize.value === 'auto') element.style.removeProperty('--score-ui-font-size');
        else element.style.setProperty('--score-ui-font-size', `${16 * Number(menuSize.value) / 100}px`);
    });
    const mode = html('span', toolbar, '', 'mode');
    const load = html('button', toolbar, '입력 ABC 불러오기');
    const undo = html('button', toolbar, '실행 취소');
    const redo = html('button', toolbar, '다시 실행');
    const play = html('button', toolbar, '현재 마디 재생');
    const stop = html('button', toolbar, '정지');
    const controls = html('div', root, undefined, 'toolbar');
    const voices = html('select', controls); voices.setAttribute('aria-label', '편집 성부');
    html('span', controls, '마디');
    const measure = html('input', controls); measure.type = 'number'; measure.min = '1'; measure.value = '1';
    measure.setAttribute('aria-label', '편집 마디');
    const append = html('button', controls, '마디 추가');
    const grid = html('select', controls); grid.setAttribute('aria-label', '입력 격자');
    for (const denominator of [4, 8, 16, 32]) html('option', grid, `1/${denominator} 격자`).value = denominator;
    grid.value = '16';
    const duration = html('select', controls); duration.setAttribute('aria-label', '음 길이');
    for (const [r, label] of [['1/1', '온음표'], ['1/2', '2분'], ['3/8', '점4분'], ['1/4', '4분'],
        ['3/16', '점8분'], ['1/8', '8분'], ['1/16', '16분'], ['1/32', '32분']]) html('option', duration, label).value = r;
    duration.value = '1/8';
    const noteDown = html('button', controls, '반음 −');
    const noteUp = html('button', controls, '반음 +');
    const resize = html('button', controls, '길이 적용');
    const erase = html('button', controls, '쉼표 / 삭제');
    const chordTools = html('div', root, undefined, 'toolbar');
    const selectionText = html('span', chordTools, '음표 또는 피아노 롤의 위치를 선택하세요.', 'selection');
    const chord = html('input', chordTools); chord.placeholder = 'C, Am7…'; chord.maxLength = 128;
    chord.setAttribute('aria-label', '코드 기호');
    const applyChord = html('button', chordTools, '코드 적용');
    const tabs = html('div', root, undefined, 'tabs');
    const staffTab = html('button', tabs, '오선 악보');
    const rollTab = html('button', tabs, '피아노 롤');
    const notation = html('div', root, undefined, 'notation');
    const roll = html('div', root, undefined, 'roll'); roll.hidden = true;
    const keyboardBar = html('div', root, undefined, 'toolbar');
    const octaveDown = html('button', keyboardBar, '옥타브 −');
    const octaveUp = html('button', keyboardBar, '옥타브 +');
    const inputLabel = html('label', keyboardBar, undefined, 'check');
    const inputEnabled = html('input', inputLabel); inputEnabled.type = 'checkbox'; inputEnabled.checked = true;
    inputLabel.append(document.createTextNode('건반으로 입력'));
    const advanceLabel = html('label', keyboardBar, undefined, 'check');
    const advance = html('input', advanceLabel); advance.type = 'checkbox'; advance.checked = true;
    advanceLabel.append(document.createTextNode('입력 후 이동'));
    html('span', keyboardBar, 'A W S E D F T G Y H U J K · 단선율 구간 덮어쓰기', 'hint');
    const keyboard = html('div', root, undefined, 'keyboard');
    const details = html('details', root, undefined, 'abc-panel');
    html('summary', details, 'ABC 직접 편집 · 변경 즉시 반영 / 워크플로에 저장');
    const source = html('textarea', details); source.spellcheck = false;
    source.setAttribute('aria-label', '편집 ABC');
    const status = html('div', root, '악보를 읽는 중…', 'status'); status.setAttribute('role', 'status');
    let draft = initialAbc;
    source.value = draft;
    let payload;
    let inputSource = '';
    let selected;
    let cursor = [0, 1];
    let basePitch = 48;
    let epoch = 0;
    let revision = 0;
    let timer;
    let controller;
    let chain = Promise.resolve();
    let destroyed = false;
    const past = [];
    const future = [];
    let audio;
    let audioVersion = 0;
    const oscillators = new Set();
    let lastAudition;
    let dialog;
    let placeholder;

    function closeDialog() {
        if (!dialog) return;
        placeholder.replaceWith(element);
        dialog.close(); dialog.remove(); dialog = undefined; placeholder = undefined;
        element.style.minHeight = '660px'; maximize.textContent = '크게 편집';
    }
    maximize.addEventListener('click', () => {
        if (dialog) { closeDialog(); return; }
        placeholder = document.createComment('score-editor'); element.before(placeholder);
        dialog = document.createElement('dialog');
        dialog.setAttribute('aria-label', '악보 편집 확대 창');
        dialog.style.cssText = 'width:94vw;height:92vh;max-width:1400px;max-height:none;padding:0;border:1px solid #8da4bc;border-radius:9px;overflow:hidden;background:#edf1f5';
        document.body.append(dialog); dialog.append(element); element.style.minHeight = '0';
        maximize.textContent = '편집창 닫기'; dialog.showModal();
        dialog.addEventListener('cancel', (event) => { event.preventDefault(); closeDialog(); });
    });

    function currentVoice() { return payload?.voices.find((v) => v.id === voices.value); }
    function currentBar() { return currentVoice()?.measures[Number(measure.value) - 1]; }
    function durationRatio() { return duration.value.split('/').map(Number); }
    function message(text, error = false) {
        status.textContent = text; status.classList.toggle('error', error);
    }
    function updateMode() {
        mode.textContent = followInput() && inputSource ? '입력 ABC 사용' : '편집본 → edited_abc';
        load.disabled = !inputSource;
        undo.disabled = !past.length; redo.disabled = !future.length;
    }
    function remember() {
        if (past.at(-1) !== draft) past.push(draft);
        while (past.length > 50 || past.reduce((sum, text) => sum + text.length, 0) > 8_000_000) past.shift();
        future.length = 0;
    }
    function commit(text, history = true) {
        if (text !== draft && history) remember();
        draft = text; source.value = text; onChange(text); updateMode();
    }
    function focusSelection(next) {
        if (next && payload) {
            const bar = payload.voices.find((v) => v.id === next.voice)?.measures[next.measure];
            const tone = bar?.tones.find((t) => value(t.offset) <= value(next.offset) &&
                value(next.offset) < value(add(t.offset, t.duration)));
            if (tone) next = { ...next, ...tone };
        }
        selected = next;
        if (next) {
            voices.value = next.voice; measure.value = next.measure + 1; cursor = next.offset;
            if (next.midi !== null && (next.midi < basePitch || next.midi >= basePitch + 36)) {
                basePitch = Math.max(0, Math.min(92, Math.floor(next.midi / 12) * 12 - 12));
                drawKeyboard();
            }
        }
        const name = next?.midi !== null && next?.midi !== undefined ? pitchName(next.midi) : '쉼표 / 입력 위치';
        selectionText.textContent = `${measure.value}마디 · ${name} · 위치 ${cursor.join('/')} (온음표 기준)`;
        const bar = currentBar();
        chord.value = bar?.events.find((e) => e.kind === 'chord' && value(e.offset) === value(cursor))?.text ?? '';
        view.focus(next ?? (payload && { voice: voices.value, measure: Number(measure.value) - 1, offset: cursor })); drawRoll();
    }
    const view = createScoreView({ onSelect: (next) => { focusSelection(next); if (next.midi !== null) sound(next.midi); } });
    notation.append(view.element);

    function accept(next) {
        payload = next;
        const oldVoice = voices.value;
        voices.replaceChildren();
        for (const voice of next.voices) html('option', voices, voice.name).value = voice.id;
        if (next.voices.some((v) => v.id === oldVoice)) voices.value = oldVoice;
        measure.max = currentVoice().measures.length;
        measure.value = Math.max(1, Math.min(Number(measure.value) || 1, Number(measure.max)));
        const bar = currentBar();
        if (value(cursor) > value(bar.duration)) cursor = bar.duration;
        view.update([next]);
        if (selected && selected.voice === voices.value && selected.measure === Number(measure.value) - 1) {
            const tone = bar.tones.find((e) => value(e.offset) === value(selected.offset));
            selected = tone ? { ...selected, ...tone } : undefined;
        } else selected = undefined;
        focusSelection(selected);
        const errors = next.messages.filter((m) => m.startsWith('ERROR'));
        for (const button of [append, noteDown, noteUp, resize, erase, applyChord]) button.disabled = Boolean(errors.length);
        message(errors.length ? errors.join(' · ') : '편집본 반영됨 · 워크플로 저장 시 함께 보관 · 건반 / 롤 클릭 입력 · 드래그 이동 · 오른쪽 클릭 삭제', Boolean(errors.length));
        updateMode();
    }

    async function refresh() {
        const ticket = ++revision;
        payload = undefined; selected = undefined;
        controller?.abort(); controller = new AbortController();
        message('악보 갱신 중…');
        try {
            const next = await request({ action: 'preview', abc: draft }, controller.signal);
            if (!destroyed && ticket === revision) accept(next);
        } catch (error) {
            if (error.name === 'AbortError' || ticket !== revision || destroyed) return;
            payload = undefined; selected = undefined; view.update([{ error: error.message, source: draft }]);
            roll.replaceChildren(); message(error.message, true);
        }
    }
    function cancelPending() {
        epoch++; revision++; clearTimeout(timer); controller?.abort();
    }
    function enqueue(operation, after) {
        setFollowInput(false); updateMode();
        const currentEpoch = epoch;
        chain = chain.then(async () => {
            if (destroyed || currentEpoch !== epoch) return;
            const action = operation();
            if (!action || !payload) return;
            const ticket = ++revision;
            controller?.abort(); controller = new AbortController();
            message('편집 반영 중…');
            try {
                const next = await request({ ...action, abc: draft }, controller.signal);
                if (destroyed || currentEpoch !== epoch || ticket !== revision) return;
                commit(next.source); accept(next); after?.(next);
            } catch (error) {
                if (error.name !== 'AbortError' && ticket === revision && !destroyed) message(error.message, true);
            }
        }).catch((error) => { if (!destroyed) message(`편집 오류: ${error.message}`, true); });
    }
    function paintAction(midi, at = cursor, length = durationRatio(), target = { voice: voices.value, measure: Number(measure.value) - 1 }) {
        const bar = payload?.voices.find((v) => v.id === target.voice)?.measures[target.measure];
        if (!bar || value(at) >= value(bar.duration)) { message('마디 끝입니다. 다음 마디를 선택하거나 마디를 추가하세요.'); return null; }
        const remaining = add(bar.duration, [-at[0], at[1]]);
        return { action: 'paint', voice: target.voice, measure: target.measure,
            offset: at, duration: value(length) <= value(remaining) ? length : remaining, midi };
    }
    function enterPitch(midi) {
        sound(midi);
        if (!inputEnabled.checked) return;
        let action;
        enqueue(() => { action = paintAction(midi); return action; }, () => {
            selected = undefined;
            if (advance.checked) {
                cursor = add(action.offset, action.duration);
                if (value(cursor) >= value(currentBar().duration) && Number(measure.value) < Number(measure.max)) {
                    measure.value = Number(measure.value) + 1; cursor = [0, 1];
                }
            }
            focusSelection(undefined);
        });
    }
    function changePitch(delta) {
        if (selected?.midi === null || !selected) return;
        const target = { ...selected };
        sound(Math.max(0, Math.min(127, target.midi + delta)));
        enqueue(() => {
            const tone = payload?.voices.find((v) => v.id === target.voice)?.measures[target.measure].tones
                .find((t) => value(t.offset) === value(target.offset));
            const midi = (tone?.midi ?? target.midi) + delta;
            return midi >= 0 && midi <= 127 ? paintAction(midi, target.offset, target.duration, target) : null;
        });
    }

    function makeSvg(parent, tag, attrs, content) {
        const el = document.createElementNS(NS, tag);
        for (const [key, val] of Object.entries(attrs)) el.setAttribute(key, val);
        if (content !== undefined) el.textContent = content;
        parent.append(el); return el;
    }
    function drawRoll() {
        roll.replaceChildren();
        const bar = currentBar();
        if (!bar) return;
        const unit = Number(grid.value);
        const columns = Math.ceil(value(bar.duration) * unit);
        if (columns > 256) { html('p', roll, '이 마디는 격자가 너무 큽니다. 더 큰 입력 격자를 선택하세요.'); return; }
        const width = 64 + columns * 32;
        const rootSvg = makeSvg(roll, 'svg', { width, height: 528, viewBox: `0 0 ${width} 528`, role: 'group', 'aria-label': '피아노 롤 입력 격자' });
        for (let row = 0; row < 36; row++) {
            const midi = basePitch + 35 - row;
            const black = [1, 3, 6, 8, 10].includes(midi % 12);
            makeSvg(rootSvg, 'rect', { x: 0, y: 24 + row * 14, width, height: 14, fill: black ? '#e7edf4' : '#fff', stroke: '#dce4ee', 'stroke-width': .5 });
            makeSvg(rootSvg, 'text', { x: 5, y: 35 + row * 14, fill: '#41556c', 'font-size': 9 }, pitchName(midi));
        }
        for (let col = 0; col <= columns; col++) {
            const x = 64 + col * 32;
            makeSvg(rootSvg, 'line', { x1: x, x2: x, y1: 24, y2: 528, stroke: col % (unit / bar.meter[1]) === 0 ? '#a6b6c9' : '#d7e0eb' });
            if (col < columns) makeSvg(rootSvg, 'text', { x: x + 3, y: 16, fill: '#536a83', 'font-size': 10 }, `${col + 1}`);
        }
        for (const tone of bar.tones.filter((e) => e.midi !== null && e.midi >= basePitch && e.midi < basePitch + 36)) {
            const x = 64 + value(tone.offset) * unit * 32;
            const active = selected && value(selected.offset) === value(tone.offset);
            const rect = makeSvg(rootSvg, 'rect', { x, y: 25 + (basePitch + 35 - tone.midi) * 14,
                width: Math.max(3, value(tone.duration) * unit * 32 - 2), height: 12, rx: 2,
                fill: active ? '#184e9c' : '#3b82c4', 'data-roll-note': '',
                'data-offset': tone.offset.join('/'), 'data-duration': tone.duration.join('/'), 'data-midi': tone.midi,
                role: 'button', tabindex: 0, 'aria-label': `${pitchName(tone.midi)} · ${tone.offset.join('/')} · ${tone.duration.join('/')}` });
            makeSvg(rect, 'title', {}, `${pitchName(tone.midi)} · 드래그 이동 / 오른쪽 가장자리로 길이 조절`);
        }
        const cursorX = 64 + value(cursor) * unit * 32;
        makeSvg(rootSvg, 'line', { x1: cursorX, x2: cursorX, y1: 24, y2: 528, stroke: '#e06e25', 'stroke-width': 2, 'pointer-events': 'none' });
        let dragging;
        const position = (event) => {
            const point = rootSvg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
            const local = point.matrixTransform(rootSvg.getScreenCTM().inverse());
            return { col: Math.max(0, Math.min(columns - 1, Math.floor((local.x - 64) / 32))),
                midi: basePitch + 35 - Math.max(0, Math.min(35, Math.floor((local.y - 24) / 14))), x: local.x };
        };
        rootSvg.addEventListener('contextmenu', (event) => event.preventDefault());
        rootSvg.addEventListener('pointerdown', (event) => {
            if (!payload) return;
            const note = event.target.closest('[data-roll-note]');
            const pos = position(event);
            const original = note ? { offset: note.getAttribute('data-offset').split('/').map(Number),
                duration: note.getAttribute('data-duration').split('/').map(Number), midi: Number(note.getAttribute('data-midi')) } : null;
            dragging = { start: pos, original, x: event.clientX, y: event.clientY, erase: event.button === 2 || event.shiftKey,
                resize: note && pos.x > Number(note.getAttribute('x')) + Number(note.getAttribute('width')) - 7 };
            rootSvg.setPointerCapture(event.pointerId); event.preventDefault();
        });
        rootSvg.addEventListener('pointerup', (event) => {
            if (!dragging) return;
            const drag = dragging; dragging = null;
            const pos = position(event);
            const moved = Math.abs(event.clientX - drag.x) + Math.abs(event.clientY - drag.y) > 4;
            if (drag.original) {
                const sel = { ...drag.original, voice: voices.value, measure: Number(measure.value) - 1 };
                focusSelection(sel); sound(sel.midi);
                if (drag.erase) enqueue(() => paintAction(null, sel.offset, sel.duration));
                else if (moved) {
                    const offset = drag.resize ? sel.offset : ratio(pos.col, unit);
                    const difference = add(ratio(pos.col + 1, unit), [-sel.offset[0], sel.offset[1]]);
                    const length = drag.resize ? (value(difference) > 0 ? difference : [1, unit]) : sel.duration;
                    const action = paintAction(drag.resize ? sel.midi : pos.midi, offset, length);
                    if (action) enqueue(() => ({ ...action, action: 'move', oldOffset: sel.offset, oldDuration: sel.duration }),
                        () => focusSelection({ ...action }));
                }
            } else {
                cursor = ratio(pos.col, unit); focusSelection(undefined);
                if (drag.erase) enqueue(() => paintAction(null));
                else enterPitch(pos.midi);
            }
        });
        rootSvg.addEventListener('pointercancel', () => { dragging = null; });
    }

    function drawKeyboard() {
        keyboard.replaceChildren();
        const keys = html('div', keyboard, undefined, 'keys');
        let whites = 0;
        for (let midi = basePitch; midi < Math.min(128, basePitch + 36); midi++) {
            const black = [1, 3, 6, 8, 10].includes(midi % 12);
            const key = html('button', keys, black ? '' : pitchName(midi), black ? 'black-key' : 'white-key');
            key.style.left = `${black ? whites * 32 - 10 : whites * 32}px`;
            key.setAttribute('aria-label', `피아노 ${pitchName(midi)}`);
            key.addEventListener('click', () => enterPitch(midi));
            if (!black) whites++;
        }
        keys.style.width = `${whites * 32}px`;
    }
    function stopAudio() {
        audioVersion++;
        for (const oscillator of oscillators) { try { oscillator.stop(); } catch (error) { if (error.name !== 'InvalidStateError') throw error; } }
        oscillators.clear(); clearTimeout(lastAudition);
    }
    async function sound(midi, length = .3, delay = 0) {
        const version = audioVersion;
        try {
            audio ??= new AudioContext();
            if (audio.state === 'suspended') await audio.resume();
            if (destroyed || version !== audioVersion || audio.state !== 'running') return;
            const at = audio.currentTime + delay;
            for (const [multiple, gain] of [[1, .12], [2, .025], [3, .012]]) {
                const oscillator = audio.createOscillator(); const envelope = audio.createGain();
                oscillator.type = 'sine'; oscillator.frequency.value = 440 * 2 ** ((midi - 69) / 12) * multiple;
                envelope.gain.setValueAtTime(.0001, at);
                envelope.gain.exponentialRampToValueAtTime(gain, at + .008);
                envelope.gain.exponentialRampToValueAtTime(.0001, at + Math.max(.06, length));
                oscillator.connect(envelope).connect(audio.destination); oscillator.start(at); oscillator.stop(at + Math.max(.08, length) + .02);
                oscillators.add(oscillator); oscillator.onended = () => { oscillators.delete(oscillator); oscillator.disconnect(); envelope.disconnect(); };
            }
        } catch (error) { message(`소리 미리듣기 오류: ${error.message}`, true); }
    }
    function playMeasure() {
        const bar = currentBar(); if (!bar) return;
        stopAudio();
        const match = payload.tempo?.match(/^([\d/]+) = ([\d/]+)$/);
        const parse = (s) => { const [n, d = 1] = s.split('/').map(Number); return n / d; };
        const seconds = match ? 60 / (parse(match[1]) * parse(match[2])) : 60 / (104 / 4);
        for (const tone of bar.tones) if (tone.midi !== null) sound(tone.midi, value(tone.duration) * seconds, value(tone.offset) * seconds);
        message('현재 성부·마디를 기본 Q: 템포로 재생합니다.');
    }

    source.addEventListener('input', () => {
        cancelPending(); setFollowInput(false); commit(source.value);
        timer = setTimeout(refresh, 180);
    });
    load.addEventListener('click', () => {
        if (!inputSource) return;
        cancelPending(); selected = undefined; cursor = [0, 1]; commit(inputSource); setFollowInput(true); updateMode(); refresh();
    });
    undo.addEventListener('click', () => {
        if (!past.length) return;
        cancelPending(); future.push(draft); commit(past.pop(), false); setFollowInput(false); refresh();
    });
    redo.addEventListener('click', () => {
        if (!future.length) return;
        cancelPending(); past.push(draft); commit(future.pop(), false); setFollowInput(false); refresh();
    });
    const changeBar = () => { selected = undefined; cursor = [0, 1]; measure.max = currentVoice()?.measures.length ?? 1;
        measure.value = Math.max(1, Math.min(Number(measure.value) || 1, Number(measure.max))); focusSelection(undefined); };
    voices.addEventListener('change', changeBar); measure.addEventListener('change', changeBar); grid.addEventListener('change', drawRoll);
    append.addEventListener('click', () => enqueue(() => ({ action: 'append' }), () => { measure.value = Number(measure.max); changeBar(); }));
    noteDown.addEventListener('click', () => changePitch(-1)); noteUp.addEventListener('click', () => changePitch(1));
    resize.addEventListener('click', () => { if (selected) {
        const target = { ...selected }; const length = durationRatio();
        enqueue(() => paintAction(target.midi, target.offset, length, target));
    } });
    erase.addEventListener('click', () => {
        const target = selected ? { ...selected } : { voice: voices.value, measure: Number(measure.value) - 1, offset: cursor, duration: durationRatio() };
        enqueue(() => paintAction(null, target.offset, target.duration, target));
    });
    applyChord.addEventListener('click', () => enqueue(() => ({ action: 'chord', voice: voices.value,
        measure: Number(measure.value) - 1, offset: cursor, chord: chord.value.trim() })));
    staffTab.addEventListener('click', () => { notation.hidden = false; roll.hidden = true; staffTab.setAttribute('aria-pressed', 'true'); rollTab.setAttribute('aria-pressed', 'false'); });
    rollTab.addEventListener('click', () => { notation.hidden = true; roll.hidden = false; staffTab.setAttribute('aria-pressed', 'false'); rollTab.setAttribute('aria-pressed', 'true'); drawRoll(); });
    staffTab.setAttribute('aria-pressed', 'true'); rollTab.setAttribute('aria-pressed', 'false');
    for (const [button, delta] of [[octaveDown, -12], [octaveUp, 12]]) button.addEventListener('click', () => {
        basePitch = Math.max(0, Math.min(92, basePitch + delta)); drawKeyboard(); drawRoll();
    });
    play.addEventListener('click', playMeasure); stop.addEventListener('click', stopAudio);
    root.addEventListener('keydown', (event) => {
        if (['TEXTAREA', 'INPUT', 'SELECT'].includes(event.target.tagName)) return;
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); (event.shiftKey ? redo : undo).click(); return; }
        if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); erase.click(); return; }
        if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); changePitch(event.key === 'ArrowUp' ? 1 : -1); return; }
        const key = 'awsedftgyhujk'.indexOf(event.key.toLowerCase());
        if (key >= 0 && !event.repeat && !event.ctrlKey && !event.metaKey && !event.altKey) { event.preventDefault(); enterPitch(Math.min(127, basePitch + 12 + key)); }
    });
    for (const type of ['pointerdown', 'keydown', 'wheel']) element.addEventListener(type, (event) => event.stopPropagation());
    drawKeyboard(); updateMode();
    return {
        element,
        loadDraft(text) { cancelPending(); commit(text, false); past.length = future.length = 0; updateMode(); refresh(); },
        update(results) {
            const result = results[0]; if (!result) return;
            const changedInput = inputSource && result.inputSource && inputSource !== result.inputSource;
            inputSource = result.inputSource ?? '';
            if (followInput() && result.followInput && inputSource && draft !== inputSource) {
                cancelPending(); commit(inputSource); accept(result);
            }
            if (changedInput && !followInput()) message('새 입력 ABC가 도착했습니다. 편집본은 유지했으며, 입력 ABC 불러오기로 전환할 수 있습니다.');
            updateMode();
        },
        destroy() { destroyed = true; closeDialog(); cancelPending(); stopAudio(); audio?.close(); view.destroy(); element.remove(); },
    };
}
