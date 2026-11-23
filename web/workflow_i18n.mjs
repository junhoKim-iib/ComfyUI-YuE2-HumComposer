import { matchesTranslation, t } from './i18n.mjs?v=20261119-i18n2';
import { nodeTitles, groupTitles, previousWorkflowTitles } from './locales/workflow_titles.mjs?v=20261119-i18n2';

function matchesWorkflowTitle(key, title) {
    return matchesTranslation(key, title) || previousWorkflowTitles[key]?.includes(title);
}

export function localizeWorkflow(graph) {
    if (!graph) return;
    const nodes = graph.nodes ?? graph._nodes ?? [];
    if (!nodes.some(node => node.type?.startsWith('YuE2') &&
        nodeTitles.some(item => item.type === node.type))) return;
    let changed = false;
    for (const node of nodes) {
        const entry = nodeTitles.find(item => item.type === node.type && matchesWorkflowTitle(item.key, node.title));
        if (entry && node.title !== t(entry.key)) {
            node.title = t(entry.key);
            changed = true;
        }
    }
    for (const group of graph.groups ?? graph._groups ?? []) {
        const key = groupTitles.find(key => matchesWorkflowTitle(key, group.title));
        if (key && group.title !== t(key)) {
            group.title = t(key);
            changed = true;
        }
    }
    if (changed) graph.setDirtyCanvas?.(true, true);
}
