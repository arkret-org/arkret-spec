/**
 * Convert ```mermaid fenced code blocks into a raw <pre class="mermaid">
 * HTML node. The actual rendering is done client-side by mermaid.js, which is
 * loaded via Starlight's head injection (see astro.config.mjs).
 *
 * We escape `&`, `<`, `>` so mermaid source survives HTML serialization. Other
 * characters mermaid uses (`#`, `[`, `(`, etc.) are not HTML-special.
 */
export default function remarkMermaid() {
  return (tree) => walk(tree);
}

function walk(node) {
  if (!node || !Array.isArray(node.children)) return;
  for (let i = 0; i < node.children.length; i++) {
    const child = node.children[i];
    if (child && child.type === "code" && child.lang === "mermaid") {
      node.children[i] = {
        type: "html",
        value: `<pre class="mermaid">${escapeHtml(child.value || "")}</pre>`,
      };
    } else {
      walk(child);
    }
  }
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
