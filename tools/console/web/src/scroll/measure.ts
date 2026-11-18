// Scroll measurements shared by the follow hook and its decision helper.

// How close to the end still counts as "at the bottom" (sub-pixel scroll slop).
const BOTTOM_SLACK_PX = 8;

/** Whether el is scrolled to its end, within BOTTOM_SLACK_PX of sub-pixel slop. */
export function isAtBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_SLACK_PX;
}

/**
 * Where the scroller's content ends, in its scroll coordinates. scrollHeight
 * can't say: it never drops below the view's height, so a short log that
 * doesn't fill the view would read as ending at the view's bottom. Assumes the
 * scroller's last child spans the content (Shell's view wrapper does).
 */
export function contentEnd(el: HTMLElement): number {
  const last = el.lastElementChild;
  if (!last) return el.scrollHeight;
  return last.getBoundingClientRect().bottom - el.getBoundingClientRect().top + el.scrollTop;
}
