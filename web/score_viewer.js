import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { createScoreView } from "./score_renderer.mjs";
import { createScoreEditor } from "./score_editor.mjs";

const views = new WeakMap();

app.registerExtension({
    name: "YuE2.HumComposer.ScoreViewer",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!['YuE2ABCScoreViewer', 'YuE2ABCScoreEditor'].includes(nodeData.name)) return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onCreated?.apply(this, arguments);
            const editor = nodeData.name === 'YuE2ABCScoreEditor';
            const abc = editor && this.widgets.find((widget) => widget.name === 'abc');
            const follow = editor && this.widgets.find((widget) => widget.name === 'follow_input');
            const changed = () => { this.graph?.change(); this.setDirtyCanvas(true); };
            if (editor) {
                abc.type = 'hidden'; abc.computeSize = () => [0, -4];
                if (abc.element) abc.element.style.display = 'none';
            }
            const view = editor ? createScoreEditor({
                initialAbc: abc.value,
                followInput: () => follow.value,
                setFollowInput: (value) => { follow.value = value; changed(); },
                onChange: (text) => { abc.value = text; changed(); },
                request: async (data, signal) => {
                    const response = await api.fetchApi('/humcomposer/score', { method: 'POST', signal,
                        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
                    if (response.status === 404) throw new Error('편집 API가 없습니다. ComfyUI 재시작 후 새로고침하세요.');
                    const payload = await response.json();
                    if (!response.ok || payload.error) throw new Error(payload.error ?? `HTTP ${response.status}`);
                    return payload;
                },
            }) : createScoreView();
            views.set(this, view);
            this.addDOMWidget("score", "score", view.element, {
                serialize: false,
                hideOnZoom: false,
                getMinHeight: () => editor ? 700 : 440,
            });
            this.setSize([Math.max(this.size[0], editor ? 1040 : 820), Math.max(this.size[1], editor ? 850 : 560)]);
            if (editor) {
                const onConfigure = this.onConfigure;
                this.onConfigure = function () { onConfigure?.apply(this, arguments); view.loadDraft(abc.value); };
                view.loadDraft(abc.value);
            }

            const onExecuted = this.onExecuted;
            this.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                view.update((editor ? message.editor : message.score) ?? []);
            };
            const onRemoved = this.onRemoved;
            this.onRemoved = function () {
                view.destroy();
                views.delete(this);
                return onRemoved?.apply(this, arguments);
            };
            return result;
        };
    },
    onNodeOutputsUpdated(outputs) {
        for (const [id, output] of Object.entries(outputs)) {
            const node = app.graph?.getNodeById(id);
            if (node && (output.editor || output.score)) views.get(node)?.update(output.editor ?? output.score);
        }
    },
});
