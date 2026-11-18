// Version local imports together so older immutable browser caches cannot retain Korean-only modules.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { createScoreView } from "./score_renderer.mjs?v=20261119-i18n2";
import { createScoreEditor } from "./score_editor.mjs?v=20261119-i18n2";
import { getLocale, setLocale, onLocaleChange, t } from "./i18n.mjs?v=20261119-i18n2";
import { localizeWorkflow } from "./workflow_i18n.mjs?v=20261119-i18n2";

const views = new WeakMap();
const retainedViews = new Map();
const viewTokens = new WeakMap();
let localeTransitionUntil = 0;

function releaseRetainedView(token) {
    const entry = retainedViews.get(token);
    if (!entry) return;
    clearTimeout(entry.timer);
    retainedViews.delete(token);
    viewTokens.delete(entry.view);
    if (entry.detached) entry.view.destroy();
}

app.registerExtension({
    name: "YuE2.HumComposer.ScoreViewer",
    init() {
        setLocale(app.ui.settings.getSettingValue('Comfy.Locale'));
        onLocaleChange(() => localizeWorkflow(app.rootGraph ?? app.graph));
        app.ui.settings.addEventListener('Comfy.Locale.change', (event) => {
            // ComfyUI refreshes node definitions and reloads the graph after this event.
            localeTransitionUntil = Date.now() + 30_000;
            setLocale(event.detail.value);
        });
    },
    afterConfigureGraph() {
        localizeWorkflow(app.rootGraph ?? app.graph);
    },
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!['YuE2HumMelodyAnalyze', 'YuE2KeyModeCandidates', 'YuE2ChordProgressionRecommend',
              'YuE2MelodyAnchor', 'YuE2AppendMelodyAnchor', 'YuE2HumSongComposer', 'YuE2ABCValidate',
              'YuE2ABCScoreViewer', 'YuE2ABCScoreEditor', 'YuE2HumTranscribe', 'YuE2HumGenerateABC'].includes(nodeData.name)) return;
        const onSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function (data) {
            const result = onSerialize?.apply(this, arguments);
            // Attach the submitting client's language without changing live workflow properties.
            data.properties = { ...data.properties, humcomposer_locale: getLocale() };
            const view = views.get(this);
            if (view && Date.now() < localeTransitionUntil) {
                let token = viewTokens.get(view);
                if (!token) {
                    token = crypto.randomUUID();
                    viewTokens.set(view, token);
                    retainedViews.set(token, { view, id: data.id, type: data.type,
                        timer: setTimeout(() => releaseRetainedView(token), 30_000) });
                }
                data.properties.humcomposer_view_session = token;
            }
            return result;
        };
        if (!['YuE2ABCScoreViewer', 'YuE2ABCScoreEditor'].includes(nodeData.name)) return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onCreated?.apply(this, arguments);
            const editor = nodeData.name === 'YuE2ABCScoreEditor';
            const abc = editor && this.widgets.find((widget) => widget.name === 'abc');
            const follow = editor && this.widgets.find((widget) => widget.name === 'follow_input');
            const changed = () => { this.graph?.change(); this.setDirtyCanvas(true); };
            const updateLabels = () => {
                if (follow) {
                    follow.options.on = t('editor.followInput');
                    follow.options.off = t('editor.useDraft');
                    this.setDirtyCanvas(true);
                }
            };
            updateLabels();
            const unsubscribeLocale = onLocaleChange(updateLabels);
            if (editor) {
                abc.type = 'hidden'; abc.computeSize = () => [0, -4];
                if (abc.element) abc.element.style.display = 'none';
            }
            const callbacks = {
                followInput: () => follow.value,
                setFollowInput: (value) => { follow.value = value; changed(); },
                onChange: (text) => { abc.value = text; changed(); },
            };
            let view = editor ? createScoreEditor({
                initialAbc: abc.value,
                ...callbacks,
                request: async (data, signal) => {
                    const response = await api.fetchApi('/humcomposer/score', { method: 'POST', signal,
                        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...data, locale: getLocale() }) });
                    if (response.status === 404) throw new Error(t('editor.apiMissing'));
                    const payload = await response.json();
                    if (!response.ok || payload.error) throw new Error(payload.error ?? `HTTP ${response.status}`);
                    return payload;
                },
            }) : createScoreView();
            views.set(this, view);
            const host = document.createElement('div');
            host.style.cssText = 'width:100%;height:100%';
            const mountView = () => {
                if (view.attach) view.attach(host);
                else host.append(view.element);
            };
            mountView();
            this.addDOMWidget("score", "score", host, {
                serialize: false,
                hideOnZoom: false,
                // This widget owns one DOM element; do not mount it again in the inspector.
                hideInPanel: true,
                getMinHeight: () => editor ? 700 : 440,
            });
            this.setSize([Math.max(this.size[0], editor ? 1040 : 820), Math.max(this.size[1], editor ? 850 : 560)]);
            const onConfigure = this.onConfigure;
            this.onConfigure = function (data) {
                onConfigure?.apply(this, arguments);
                const token = data?.properties?.humcomposer_view_session;
                const entry = retainedViews.get(token);
                if (this.properties) delete this.properties.humcomposer_view_session;
                const sameDraft = !editor || entry?.view.getDraft?.() === abc.value;
                if (entry && sameDraft && entry.id === data.id && entry.type === data.type && (entry.detached || entry.view === view)) {
                    localeTransitionUntil = 0;
                    clearTimeout(entry.timer);
                    retainedViews.delete(token);
                    viewTokens.delete(entry.view);
                    if (view !== entry.view) view.destroy();
                    view = entry.view;
                    if (editor) view.rebind(callbacks);
                    mountView();
                    views.set(this, view);
                } else {
                    if (entry?.detached) releaseRetainedView(token);
                    if (editor) view.loadDraft(abc.value);
                }
            };
            if (editor) view.loadDraft(abc.value);

            const onExecuted = this.onExecuted;
            this.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                view.update((editor ? message.editor : message.score) ?? []);
            };
            const onRemoved = this.onRemoved;
            this.onRemoved = function () {
                unsubscribeLocale();
                const token = viewTokens.get(view);
                const entry = retainedViews.get(token);
                if (entry) {
                    entry.detached = true;
                    clearTimeout(entry.timer);
                    entry.timer = setTimeout(() => releaseRetainedView(token), 5_000);
                } else view.destroy();
                views.delete(this);
                return onRemoved?.apply(this, arguments);
            };
            return result;
        };
    },
    onNodeOutputsUpdated(outputs) {
        for (const [id, output] of Object.entries(outputs)) {
            const node = app.graph?.getNodeById(id);
            if (node && (output.editor || output.score)) views.get(node)?.update(output.editor ?? output.score, { preserveState: true });
        }
    },
});
