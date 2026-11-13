// Small DOM helpers shared by the board page modules (stage, renderers, diagrams).

// Absolutely position an element at x, y with size w x h, in its parent's pixels.
export function place(element, x, y, w, h) {
  Object.assign(element.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
}

// Make an SVG scale into its box, keeping its aspect ratio.
export function fitSvgToBox(svg) {
  const width = parseFloat(svg.getAttribute("width"));
  const height = parseFloat(svg.getAttribute("height"));
  if (!svg.hasAttribute("viewBox") && width > 0 && height > 0) {
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  }
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  svg.style.maxWidth = "none";
}
