import en from './locales/en.mjs?v=20261119-i18n2';
import ko from './locales/ko.mjs?v=20261119-i18n2';

const catalogs = { en, ko };
const listeners = new Set();
const bindings = new WeakMap();
let locale = 'en';

export function normalizeLocale(value) {
    const language = typeof value === 'string' ? value.toLowerCase().split(/[-_]/)[0] : 'en';
    return Object.hasOwn(catalogs, language) ? language : 'en';
}

export const getLocale = () => locale;

export function matchesTranslation(key, value) {
    return Object.values(catalogs).some(catalog => Object.hasOwn(catalog, key) && catalog[key] === value);
}

export function setLocale(value) {
    const next = normalizeLocale(value);
    if (next === locale) return;
    locale = next;
    for (const listener of listeners) listener();
}

export function onLocaleChange(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
}

export function t(key, params = {}) {
    const template = catalogs[locale][key] ?? en[key] ?? key;
    return template.replace(/\{(\w+)\}/g, (match, name) => {
        if (!Object.hasOwn(params, name)) return match;
        const value = params[name];
        return value && typeof value === 'object' && value.key ? t(value.key, value.params) : String(value);
    });
}

export const msg = (key, params = {}) => ({ key, params });

function bind(element, descriptor, attribute) {
    let entries = bindings.get(element);
    if (!entries) {
        entries = new Map();
        bindings.set(element, entries);
        element.setAttribute('data-hum-i18n', '');
    }
    entries.set(attribute, descriptor);
    const translated = t(descriptor.key, descriptor.params);
    if (attribute === 'textContent') element.textContent = translated;
    else element.setAttribute(attribute, translated);
}

export function setContent(element, content) {
    if (content && typeof content === 'object' && typeof content.key === 'string') bind(element, content, 'textContent');
    else {
        bindings.get(element)?.delete('textContent');
        element.textContent = content;
    }
}

export function setTranslatedAttribute(element, attribute, descriptor) {
    bind(element, descriptor, attribute);
}

export function translateTree(root) {
    for (const element of [root, ...root.querySelectorAll('[data-hum-i18n]')]) {
        for (const [attribute, descriptor] of bindings.get(element) ?? []) bind(element, descriptor, attribute);
    }
}

export function scoreMessages(payload) {
    return (payload?.messages ?? []).map((message, index) => {
        const descriptor = payload.messageDetails?.[index];
        return descriptor ? t(descriptor.key, descriptor.params) : message;
    });
}
