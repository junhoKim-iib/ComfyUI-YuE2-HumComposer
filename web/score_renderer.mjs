// Hand-drawn SVG notation for the existing HumComposer parser's dialect.
const NS = "http://www.w3.org/2000/svg";
const LEFT = 112;
const PAGE_BARS = 16;
const value = (ratio) => ratio[0] / ratio[1];
const equal = (a, b) => a[0] === b[0] && a[1] === b[1];

function svg(parent, tag, attrs = {}, text) {
    const element = document.createElementNS(NS, tag);
    for (const [key, val] of Object.entries(attrs)) element.setAttribute(key, val);
    if (text !== undefined) element.textContent = text;
    parent?.append(element);
    return element;
}

function line(parent, x1, y1, x2, y2, width = 1) {
    return svg(parent, "line", { x1, y1, x2, y2, stroke: "#18212b", "stroke-width": width });
}

function text(parent, x, y, content, size = 13, attrs = {}) {
    return svg(parent, "text", { x, y, "font-size": size, fill: "#18212b",
        "font-family": "Segoe UI, Arial, sans-serif", ...attrs }, content);
}

function accidental(parent, x, y, amount) {
    const group = svg(parent, "g", { transform: `translate(${x},${y})`, "data-accidental": amount });
    if (amount === 0) {
        line(group, -3, -9, -3, 5, 1.5);
        line(group, 3, -5, 3, 9, 1.5);
        line(group, -3, -3, 3, -5, 2.4);
        line(group, -3, 5, 3, 3, 2.4);
    } else {
        for (let index = 0; index < Math.abs(amount); index++) {
            const symbol = svg(group, "g", { transform: `translate(${-index * 8},0)` });
            if (amount > 0) {
                line(symbol, -2, -9, -2, 9, 1.3);
                line(symbol, 3, -10, 3, 8, 1.3);
                line(symbol, -5, -2, 6, -4, 2.4);
                line(symbol, -5, 4, 6, 2, 2.4);
            } else {
                svg(symbol, "path", { d: "M-2 -13 V7 C10 1 7 -7 -2 0", fill: "none",
                    stroke: "#18212b", "stroke-width": 1.7 });
            }
        }
    }
}

export function noteY(step, clef, top = 0) {
    return top + 40 - (step - (clef === "bass" ? -10 : 2)) * 5;
}

function clef(parent, x, top, kind) {
    const group = svg(parent, "g", { transform: `translate(${x},${top})`, "data-clef": kind });
    if (kind === "bass") {
        svg(group, "path", { d: "M5 17 C0 12 4 5 11 6 C26 6 26 23 13 34 L1 41 C12 32 23 16 15 11 C9 7 6 12 8 15 Z", fill: "#18212b" });
        svg(group, "circle", { cx: 29, cy: 5, r: 2.2, fill: "#18212b" });
        svg(group, "circle", { cx: 29, cy: 15, r: 2.2, fill: "#18212b" });
    } else {
        svg(group, "path", { d: "M17 53 C5 53 8 43 15 45 C24 46 24 57 17 59 C10 61 10 55 12 46 L22 -9 C25 -22 14 -17 15 -7 C16 4 28 9 25 23 C22 36 5 37 3 25 C1 15 16 8 23 15 C31 24 18 36 12 26 C9 19 16 16 20 20", fill: "none", stroke: "#18212b", "stroke-width": 2.7,
            "stroke-linecap": "round", "stroke-linejoin": "round" });
    }
}

function keyWidth(current, previous = 0) {
    return (Math.abs(current) + (current !== previous ? Math.abs(previous) : 0)) * 10;
}

function keySignature(parent, x, top, current, previous, kind) {
    const sharp = [10, 7, 11, 8, 5, 9, 6];
    const flat = [6, 9, 5, 8, 4, 7, 3];
    const shift = kind === "bass" ? -14 : 0;
    if (previous && previous !== current) {
        for (const step of (previous > 0 ? sharp : flat).slice(0, Math.abs(previous))) {
            accidental(parent, x, noteY(step + shift, kind, top), 0);
            x += 10;
        }
    }
    for (const step of (current >= 0 ? sharp : flat).slice(0, Math.abs(current))) {
        accidental(parent, x, noteY(step + shift, kind, top), Math.sign(current));
        x += 10;
    }
    return x;
}

function meter(parent, x, top, signature) {
    text(parent, x, top + 18, signature[0], 20, { "text-anchor": "middle", "font-weight": 600 });
    text(parent, x, top + 37, signature[1], 20, { "text-anchor": "middle", "font-weight": 600 });
}

function flags(denominator) {
    return denominator >= 8 ? Math.log2(denominator) - 2 : 0;
}

function rest(parent, x, top, event) {
    const y = top + 20;
    if (!event.denominator) {
        svg(parent, "rect", { x: x - 5, y: y - 5, width: 10, height: 10, fill: "none", stroke: "#18212b" });
    } else if (event.fullRest || event.denominator <= 2) {
        svg(parent, "rect", { x: x - 6, y: top + (event.fullRest || event.denominator === 1 ? 10 : 15),
            width: 12, height: 5, fill: "#18212b" });
    } else if (event.denominator === 4) {
        svg(parent, "path", { d: `M${x - 3} ${y - 14} l7 10 -7 7 5 7 q-9 -4 -4 5 q-11 -6 -2 -12 l-5 -6 7 -6 Z`, fill: "#18212b" });
    } else {
        const count = flags(event.denominator);
        line(parent, x + 5, y - 10, x - 1, y + 12 + (count - 1) * 5, 1.8);
        for (let i = 0; i < count; i++) {
            svg(parent, "circle", { cx: x - 3, cy: y - 9 + i * 5, r: 3, fill: "#18212b" });
            svg(parent, "path", { d: `M${x - 3} ${y - 7 + i * 5} Q${x + 2} ${y - 4 + i * 5} ${x + 5 - i} ${y - 10 + i * 5}`,
                fill: "none", stroke: "#18212b", "stroke-width": 1.5 });
        }
    }
}

function head(parent, x, y, event, top) {
    const group = svg(parent, "g", { "data-kind": "note", "data-midi": event.midi,
        "data-step": event.step, "data-duration": event.duration.join("/"), "data-onset-x": x });
    svg(group, "title", {}, `MIDI ${event.midi} · ${event.duration.join("/")}`);
    for (let ledger = top - 10; ledger >= y - 1; ledger -= 10) line(group, x - 10, ledger, x + 10, ledger);
    for (let ledger = top + 50; ledger <= y + 1; ledger += 10) line(group, x - 10, ledger, x + 10, ledger);
    if (!event.denominator) {
        svg(group, "path", { d: `M${x - 6} ${y} l6 -5 6 5 -6 5 Z`, fill: "white", stroke: "#18212b", "stroke-width": 1.5 });
    } else {
        svg(group, "ellipse", { cx: x, cy: y, rx: event.denominator === 1 ? 7 : 6, ry: 4,
            transform: `rotate(-20 ${x} ${y})`, fill: event.denominator <= 2 ? "white" : "#18212b",
            stroke: "#18212b", "stroke-width": 1.5 });
    }
    if (event.accidental !== null) accidental(group, x - 16, y, event.accidental);
}

function dots(parent, x, y, event, top) {
    const dotY = Math.abs((y - top) % 10) < 1 ? y - 5 : y;
    for (let index = 0; index < event.dots; index++) {
        svg(parent, "circle", { cx: x + 12 + index * 5, cy: dotY, r: 1.8, fill: "#18212b" });
    }
    if (!event.denominator) text(parent, x, top + 60, event.duration.join("/"), 10, { "text-anchor": "middle" });
}

function stems(parent, notes, top) {
    if (!notes.length) return;
    const up = notes.reduce((sum, note) => sum + note.y, 0) / notes.length >= top + 20;
    const direction = up ? 1 : -1;
    const end = up ? Math.min(...notes.map((n) => n.y)) - 31 : Math.max(...notes.map((n) => n.y)) + 31;
    for (const note of notes) {
        note.stemUp = up;
        note.stemX = note.x + direction * 5;
        line(parent, note.stemX, note.y, note.stemX, end, 1.5);
    }
    const maxFlags = Math.max(...notes.map((n) => flags(n.event.denominator)));
    if (notes.length === 1) {
        for (let level = 0; level < maxFlags; level++) {
            const start = end + direction * level * 6;
            svg(parent, "path", { d: `M${notes[0].stemX} ${start} q${direction * 14} ${direction * 6} ${direction * 6} ${direction * 18} q${direction * 2} ${-direction * 10} ${-direction * 6} ${-direction * 12}`,
                fill: "#18212b" });
        }
        return;
    }
    for (let level = 1; level <= maxFlags; level++) {
        let start = 0;
        while (start < notes.length) {
            if (flags(notes[start].event.denominator) < level) { start++; continue; }
            let last = start;
            while (last + 1 < notes.length && flags(notes[last + 1].event.denominator) >= level) last++;
            const x1 = notes[start].stemX;
            const x2 = last > start ? notes[last].stemX : x1 + (start === notes.length - 1 ? -10 : 10);
            const beamY = end + direction * (level - 1) * 6;
            svg(parent, "path", { d: `M${x1} ${beamY} H${x2} v${direction * 4} H${x1} Z`, fill: "#18212b", "data-kind": "beam" });
            start = last + 1;
        }
    }
}

function tie(parent, x1, y1, x2, y2, below) {
    const shift = below ? 9 : -9;
    const bend = below ? 14 : -14;
    svg(parent, "path", { d: `M${x1} ${y1 + shift} Q${(x1 + x2) / 2} ${(below ? Math.max(y1, y2) : Math.min(y1, y2)) + shift + bend} ${x2} ${y2 + shift}`,
        fill: "none", stroke: "#18212b", "stroke-width": 1.5, "data-kind": "tie" });
}

export function layoutMeasure(voices, index, first) {
    let prefix = first ? 75 : 8;
    const slots = new Map();
    for (const voice of voices) {
        const bar = voice.measures[index];
        const previous = voice.measures[index - 1];
        if (first) prefix = Math.max(prefix, 78 + keyWidth(bar.fifths,
            previous && previous.fifths !== bar.fifths ? previous.fifths : 0));
        else {
            const key = previous.fifths !== bar.fifths ? keyWidth(bar.fifths, previous.fifths) + 12 : 0;
            prefix = Math.max(prefix, 10 + key + (!equal(previous.meter, bar.meter) ? 34 : 0));
        }
        for (const event of bar.events) {
            const time = value(event.offset);
            const slot = slots.get(time) ?? { time, before: 12, after: 26, context: 0 };
            if (event.kind === "note" && event.accidental !== null) slot.before = Math.max(slot.before, 25 + Math.abs(event.accidental) * 6);
            if (event.kind === "key") slot.context = Math.max(slot.context, keyWidth(event.fifths, event.previousFifths) + 12);
            if (event.kind === "chord") slot.after = Math.max(slot.after, event.text.length * 7 + 8);
            if (event.dots) slot.after = Math.max(slot.after, 26 + event.dots * 5);
            slots.set(time, slot);
        }
    }
    let width = prefix;
    const ticks = [...slots.values()].sort((a, b) => a.time - b.time);
    for (const slot of ticks) {
        slot.x = width + slot.before + slot.context;
        width = slot.x + slot.after;
    }
    return { prefix, ticks, width: Math.max(180, width + 16) };
}

export function renderScore(payload, { voiceId = "all", page = 0, barsPerLine = 4 } = {}) {
    const voices = payload.voices.filter((v) => voiceId === "all" || v.id === voiceId);
    const total = Math.max(...voices.map((v) => v.measures.length), 0);
    const start = page * PAGE_BARS;
    const end = Math.min(total, start + PAGE_BARS);
    const rows = [];
    for (let index = start; index < end;) {
        const bars = [];
        let width = LEFT + 30;
        while (index < end && bars.length < barsPerLine) {
            const layout = layoutMeasure(voices, index, !bars.length);
            if (bars.length && width + layout.width > 1100) break;
            bars.push({ index, ...layout });
            width += layout.width;
            index++;
        }
        rows.push({ bars, width });
    }
    const width = Math.max(960, ...rows.map((row) => row.width));
    const root = svg(null, "svg", { xmlns: NS, role: "img", "aria-label": payload.title });
    svg(root, "title", {}, payload.title);
    const background = svg(root, "rect", { width: "100%", height: "100%", fill: "white" });
    text(root, 24, 34, payload.title, 21, { "font-weight": 600 });
    text(root, 24, 56, `${start + 1}–${end} / ${total} 마디`, 12, { fill: "#546579" });
    if (payload.tempo) text(root, width - 24, 56, payload.tempo, 12, { "text-anchor": "end" });
    let rowY = 80;
    for (const row of rows) {
        const extra = (width - row.width) / row.bars.length;
        let left = LEFT;
        for (const bar of row.bars) {
            bar.left = left;
            bar.scale = (bar.width - bar.prefix + extra) / (bar.width - bar.prefix);
            bar.right = left + bar.width + extra;
            const ticks = new Map(bar.ticks.map((slot) => [slot.time, slot]));
            bar.xAt = (offset) => bar.left + bar.prefix + (ticks.get(value(offset)).x - bar.prefix) * bar.scale;
            left = bar.right;
        }
        let voiceY = rowY;
        const tops = [];
        for (const voice of voices) {
            const group = svg(root, "g", { "data-voice": voice.id });
            const notes = row.bars.flatMap((bar) => voice.measures[bar.index].events.filter((e) => e.kind === "note"));
            const minY = notes.reduce((y, e) => Math.min(y, noteY(e.step, voice.clef)), 0);
            const maxY = notes.reduce((y, e) => Math.max(y, noteY(e.step, voice.clef)), 40);
            const top = voiceY + Math.max(84, 77 - minY);
            const chordY = top + Math.min(-24, minY - 43);
            tops.push(top);
            for (let staff = 0; staff < 5; staff++) line(group, LEFT, top + staff * 10, width - 30, top + staff * 10, .8);
            const label = text(group, 14, top + 23, voice.name.length > 14 ? voice.name.slice(0, 13) + "…" : voice.name, 11);
            svg(label, "title", {}, voice.name);
            const positions = [];
            for (let barIndex = 0; barIndex < row.bars.length; barIndex++) {
                const layout = row.bars[barIndex];
                const bar = voice.measures[layout.index];
                const previous = voice.measures[layout.index - 1];
                if (voice === voices[0]) {
                    text(group, layout.left + 2, chordY - 22, bar.index + 1, 10, { fill: "#6a7889" });
                    if (bar.section && bar.section !== previous?.section) text(group, layout.left + 28, chordY - 22, bar.section, 11, { fill: "#405f86" });
                }
                let contextX = layout.left + 9;
                if (!barIndex) {
                    clef(group, contextX, top, voice.clef);
                    contextX += 38;
                    contextX = keySignature(group, contextX, top, bar.fifths,
                        previous && previous.fifths !== bar.fifths ? previous.fifths : 0, voice.clef) + 12;
                    meter(group, contextX, top, bar.meter);
                } else {
                    if (previous.fifths !== bar.fifths) contextX = keySignature(group, contextX, top, bar.fifths, previous.fifths, voice.clef) + 12;
                    if (!equal(previous.meter, bar.meter)) meter(group, contextX + 10, top, bar.meter);
                }
                let beam = [];
                let beat = -1;
                const flush = () => { stems(group, beam, top); beam = []; };
                const beatLength = (bar.meter[0] > 3 && bar.meter[0] % 3 === 0 ? 3 : 1) / bar.meter[1];
                for (const event of bar.events) {
                    const x = layout.xAt(event.offset);
                    if (event.kind === "chord") { text(group, x - 5, chordY, event.text, 13, { "font-weight": 600 }); continue; }
                    if (event.kind === "tempo") { text(group, x, top + maxY + 35, event.text, 10); continue; }
                    if (event.kind === "key") {
                        flush();
                        keySignature(group, x - (keyWidth(event.fifths, event.previousFifths) + 12) * layout.scale, top, event.fifths, event.previousFifths, voice.clef);
                        continue;
                    }
                    const nextBeat = Math.floor((value(event.offset) + 1e-9) / beatLength);
                    if (nextBeat !== beat || event.kind !== "note" || !flags(event.denominator)) flush();
                    beat = nextBeat;
                    if (event.kind === "rest") rest(group, event.fullRest ? (layout.left + layout.prefix + layout.right) / 2 : x, top, event);
                    else {
                        const y = noteY(event.step, voice.clef, top);
                        head(group, x, y, event, top);
                        const position = { x, y, event };
                        positions.push(position);
                        if (event.denominator > 1) {
                            if (flags(event.denominator)) beam.push(position);
                            else stems(group, [position], top);
                        }
                    }
                    dots(group, x, event.kind === "note" ? noteY(event.step, voice.clef, top) : top + 20, event, top);
                }
                flush();
                line(group, layout.right, top, layout.right, top + 40);
                if (layout.index === total - 1) line(group, layout.right - 5, top, layout.right - 5, top + 40, 2.5);
            }
            for (let index = 0; index < positions.length; index++) {
                const current = positions[index];
                const previous = positions[index - 1];
                if (current.event.tieIn) {
                    if (previous?.event.tieOut) tie(group, previous.x + 6, previous.y, current.x - 6, current.y, previous.stemUp !== false);
                    else tie(group, current.x - 28, current.y, current.x - 6, current.y, current.stemUp !== false);
                }
                if (current.event.tieOut && index === positions.length - 1) tie(group, current.x + 6, current.y, width - 32, current.y, current.stemUp !== false);
            }
            voiceY = top + maxY + 45;
        }
        line(root, LEFT, tops[0], LEFT, tops.at(-1) + 40, 1.4);
        if (tops.length > 1) {
            line(root, LEFT - 7, tops[0], LEFT - 7, tops.at(-1) + 40, 2);
            line(root, LEFT - 7, tops[0], LEFT - 2, tops[0], 2);
            line(root, LEFT - 7, tops.at(-1) + 40, LEFT - 2, tops.at(-1) + 40, 2);
        }
        rowY = voiceY + 12;
    }
    root.setAttribute("viewBox", `0 0 ${width} ${rowY + 16}`);
    root.setAttribute("width", width);
    root.setAttribute("height", rowY + 16);
    background.setAttribute("height", rowY + 16);
    return root;
}

export function createScoreView() {
    const element = document.createElement("div");
    element.style.cssText = "width:100%;height:100%;min-height:320px";
    const shadow = element.attachShadow({ mode: "open" });
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = new URL("./score.css", import.meta.url).href;
    shadow.append(stylesheet);
    function html(tag, parent, content, className) {
        const item = document.createElement(tag);
        if (content !== undefined) item.textContent = content;
        if (className) item.className = className;
        parent.append(item);
        return item;
    }
    const viewer = html("div", shadow, undefined, "viewer");
    const toolbar = html("div", viewer, undefined, "toolbar");
    html("strong", toolbar, "오선 악보");
    const batches = html("select", toolbar);
    batches.setAttribute("aria-label", "실행 결과");
    batches.hidden = true;
    const voices = html("select", toolbar);
    voices.setAttribute("aria-label", "성부 선택");
    const measures = html("select", toolbar);
    measures.setAttribute("aria-label", "한 줄 마디 수");
    for (const count of [2, 4, 8]) {
        const option = html("option", measures, `${count}마디 / 줄`);
        option.value = count;
    }
    measures.value = "4";
    const minus = html("button", toolbar, "−");
    minus.setAttribute("aria-label", "축소");
    const zoomText = html("span", toolbar, "100%");
    const plus = html("button", toolbar, "+");
    plus.setAttribute("aria-label", "확대");
    const saveSvg = html("button", toolbar, "SVG 저장");
    saveSvg.title = "현재 페이지를 SVG로 저장";
    const saveAbc = html("button", toolbar, "ABC 저장");
    const status = html("div", viewer, "ABC를 연결하고 실행하면 악보가 표시됩니다.", "status");
    status.setAttribute("role", "status");
    const details = html("details", viewer);
    html("summary", details, "표시 안내 / 검증 메시지");
    const messages = html("pre", details);
    details.hidden = true;
    const viewport = html("div", viewer, undefined, "viewport");
    const paper = html("div", viewport, undefined, "paper");
    const pager = html("div", viewer, undefined, "pager");
    const previous = html("button", pager, "이전");
    const pageText = html("span", pager, "0 / 0");
    const next = html("button", pager, "다음");
    let payloads = [];
    let payload;
    let page = 0;
    let zoom = 1;
    let currentSvg;
    const urls = new Set();

    function draw() {
        paper.replaceChildren();
        currentSvg = null;
        const valid = payload && !payload.error;
        voices.disabled = measures.disabled = minus.disabled = plus.disabled = !valid;
        saveAbc.disabled = !payload?.source;
        previous.disabled = next.disabled = saveSvg.disabled = true;
        pageText.textContent = "0 / 0";
        messages.textContent = payload?.messages?.join("\n") ?? "";
        details.hidden = !messages.textContent;
        status.classList.toggle("error", Boolean(payload?.error));
        status.textContent = payload?.error ? `악보를 표시할 수 없습니다: ${payload.error}` :
            valid ? "구간·코드·성부를 표시합니다. SVG 저장은 현재 페이지에 적용됩니다." : "ABC를 연결하고 실행하면 악보가 표시됩니다.";
        if (!valid) return;
        const selected = payload.voices.filter((v) => voices.value === "all" || v.id === voices.value);
        const total = Math.max(...selected.map((v) => v.measures.length));
        const pages = Math.ceil(total / PAGE_BARS);
        page = Math.max(0, Math.min(page, pages - 1));
        try {
            currentSvg = renderScore(payload, { voiceId: voices.value, page, barsPerLine: Number(measures.value) });
            paper.append(currentSvg);
            paper.style.width = `${zoom * 100}%`;
            zoomText.textContent = `${Math.round(zoom * 100)}%`;
            pageText.textContent = `${page + 1} / ${pages} · ${page * PAGE_BARS + 1}–${Math.min(total, (page + 1) * PAGE_BARS)} / ${total} 마디`;
            previous.disabled = page === 0;
            next.disabled = page + 1 >= pages;
            saveSvg.disabled = false;
        } catch (error) {
            status.classList.add("error");
            status.textContent = `악보 표시 오류: ${error.message}`;
        }
    }

    function selectResult() {
        payload = payloads[Number(batches.value) || 0];
        page = 0;
        voices.replaceChildren();
        if (payload?.voices) {
            if (payload.aligned) html("option", voices, "모든 성부").value = "all";
            for (const voice of payload.voices) html("option", voices, voice.name).value = voice.id;
        }
        draw();
    }

    function download(content, type, filename) {
        const url = URL.createObjectURL(new Blob([content], { type }));
        urls.add(url);
        const anchor = html("a", shadow);
        anchor.href = url;
        anchor.download = filename;
        anchor.click();
        anchor.remove();
        setTimeout(() => { URL.revokeObjectURL(url); urls.delete(url); }, 1000);
    }
    batches.addEventListener("change", selectResult);
    voices.addEventListener("change", () => { page = 0; viewport.scrollTop = 0; draw(); });
    measures.addEventListener("change", draw);
    previous.addEventListener("click", () => { page--; viewport.scrollTop = 0; draw(); });
    next.addEventListener("click", () => { page++; viewport.scrollTop = 0; draw(); });
    minus.addEventListener("click", () => { zoom = Math.max(.5, zoom - .25); draw(); });
    plus.addEventListener("click", () => { zoom = Math.min(3, zoom + .25); draw(); });
    saveSvg.addEventListener("click", () => download(new XMLSerializer().serializeToString(currentSvg), "image/svg+xml;charset=utf-8", `yue2-score-page-${page + 1}.svg`));
    saveAbc.addEventListener("click", () => download(payload.source, "text/plain;charset=utf-8", "yue2-score.abc"));
    // Consume score interactions so canvas dragging/shortcuts do not steal them.
    for (const type of ["pointerdown", "keydown", "wheel"]) element.addEventListener(type, (event) => event.stopPropagation());
    draw();
    return {
        element,
        update(results) {
            payloads = results;
            batches.replaceChildren();
            results.forEach((result, index) => { html("option", batches, `결과 ${index + 1}`).value = index; });
            batches.hidden = results.length < 2;
            selectResult();
        },
        destroy() {
            for (const url of urls) URL.revokeObjectURL(url);
            urls.clear();
            element.remove();
        },
    };
}
