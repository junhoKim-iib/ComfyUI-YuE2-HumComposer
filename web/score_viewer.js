import { app } from "../../scripts/app.js";
import { createScoreView } from "./score_renderer.mjs";

const views = new WeakMap();

app.registerExtension({
    name: "YuE2.HumComposer.ScoreViewer",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "YuE2ABCScoreViewer") return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onCreated?.apply(this, arguments);
            const view = createScoreView();
            views.set(this, view);
            this.addDOMWidget("score", "score", view.element, {
                serialize: false,
                hideOnZoom: false,
                getMinHeight: () => 440,
            });
            this.setSize([Math.max(this.size[0], 820), Math.max(this.size[1], 560)]);

            const onExecuted = this.onExecuted;
            this.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                view.update(message.score ?? []);
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
            if (node && output.score) views.get(node)?.update(output.score);
        }
    },
});
