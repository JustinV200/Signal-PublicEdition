// Renders scene items into #items: one absolutely positioned box per item, drawn by kind.
// Only items whose data changed are re-rendered, so a slow mermaid diagram doesn't
// flicker every time something else moves. Untrusted HTML/SVG goes through DOMPurify.

import { renderMermaid, renderRough } from "./diagrams.js";
import { fitSvgToBox, place } from "./dom.js";

const MIN_FONT_PX = 8;
const itemsEl = document.getElementById("items");
// item id -> {key: JSON of the item, element}
const rendered = new Map();

const RENDERERS = {
  text: renderText,
  markdown: renderMarkdown,
  math: renderMath,
  svg: renderSvg,
  image: renderImage,
  mermaid: renderMermaid,
  rough: renderRough,
  loading: renderLoading,
};

// Bring #items in line with `items` (drawing order = array order).
export function renderScene(items, onError) {
  const liveIds = new Set();
  for (const item of items) {
    const key = JSON.stringify(item);
    let entry = rendered.get(item.id);
    if (!entry || entry.key !== key) {
      entry?.element.remove();
      entry = { key, element: createItemElement(item, onError) };
      rendered.set(item.id, entry);
    }
    // appendChild moves an existing node, so this also fixes the stacking order.
    itemsEl.appendChild(entry.element);
    liveIds.add(item.id);
  }
  for (const [id, entry] of rendered) {
    if (!liveIds.has(id)) {
      entry.element.remove();
      rendered.delete(id);
    }
  }
}

function createItemElement(item, onError) {
  const box = document.createElement("div");
  box.className = `item item-${item.kind}`;
  place(box, item.x, item.y, item.w, item.h);
  box.style.color = item.style.color;
  box.style.opacity = item.style.opacity;
  // Run after renderScene has put the box in the DOM, so text can be measured.
  queueMicrotask(() => {
    Promise.resolve()
      .then(() => RENDERERS[item.kind](box, item))
      .catch((error) => onError(item.id, error));
  });
  return box;
}

function renderText(box, item) {
  const content = contentElement(box);
  content.textContent = item.content;
  return fitFont(box, content, item.style.font_size);
}

function renderMarkdown(box, item) {
  const content = contentElement(box);
  // No <style>: a markdown item mustn't restyle the rest of the board.
  content.innerHTML = DOMPurify.sanitize(marked.parse(item.content), { FORBID_TAGS: ["style"] });
  return fitFont(box, content, item.style.font_size);
}

function renderMath(box, item) {
  const content = contentElement(box);
  katex.render(item.content, content, { displayMode: true, throwOnError: false, trust: false });
  return fitFont(box, content, item.style.font_size);
}

function renderSvg(box, item) {
  // Already sanitized by the daemon; DOMPurify here is the second layer. No <style>, as
  // for markdown: it would restyle the page, hidden layers included (scenes saved before
  // the daemon stripped it still carry it).
  box.innerHTML = DOMPurify.sanitize(item.content, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ["style"],
  });
  const svg = box.querySelector("svg");
  if (svg) fitSvgToBox(svg);
}

// The "Claude is thinking" placeholder: the styling and pulse live in board.css.
function renderLoading(box, item) {
  contentElement(box).textContent = item.content;
}

function renderImage(box, item) {
  const image = document.createElement("img");
  image.src = `/files?path=${encodeURIComponent(item.content)}`;
  box.append(image);
}

function contentElement(box) {
  const content = document.createElement("div");
  content.className = "content";
  box.append(content);
  return content;
}

// Use the item's font size, or (font_size 0) the largest size whose text fits the box.
async function fitFont(box, content, fontSize) {
  if (fontSize > 0) {
    content.style.fontSize = `${fontSize}px`;
    return;
  }
  // Measuring before web fonts (KaTeX) load would size against the fallback font.
  await document.fonts.ready;
  let low = MIN_FONT_PX;
  let high = Math.max(MIN_FONT_PX, box.clientHeight);
  while (high - low > 0.5) {
    const middle = (low + high) / 2;
    content.style.fontSize = `${middle}px`;
    const fits = content.scrollWidth <= box.clientWidth && content.offsetHeight <= box.clientHeight;
    if (fits) low = middle;
    else high = middle;
  }
  content.style.fontSize = `${low}px`;
}
