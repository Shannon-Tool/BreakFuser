export function element<K extends keyof HTMLElementTagNameMap>(
    tag: K,
    className?: string,
    text?: string,
): HTMLElementTagNameMap[K] {
    const node = document.createElement(tag);
    if (className !== undefined) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

export function button(
    className: string,
    label: string,
    onClick: () => void,
): HTMLButtonElement {
    const node = element("button", className, label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
}

export function svgElement<K extends keyof SVGElementTagNameMap>(
    tag: K,
    attributes: Record<string, string | number> = {},
    text?: string,
): SVGElementTagNameMap[K] {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attributes)) {
        node.setAttribute(name, String(value));
    }
    if (text !== undefined) node.textContent = text;
    return node;
}

export function json(value: unknown): string {
    return JSON.stringify(value, null, 2);
}
