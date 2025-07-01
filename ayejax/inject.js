/**
 * @typedef {Object} ScrollOpts
 * @property {('vertical'|'horizontal'|'both')} [direction='both'] - Which direction to scroll.
 */

/**
 * Determines if an element uses native scroll.
 */
function isStandardScrollable(element) {
  const style = window.getComputedStyle(element);
  const overflowY = style.overflowY;
  const overflowX = style.overflowX;
  const canScrollY =
    /auto|scroll/.test(overflowY) &&
    element.scrollHeight > element.clientHeight;
  const canScrollX =
    /auto|scroll/.test(overflowX) && element.scrollWidth > element.clientWidth;
  return canScrollY || canScrollX;
}

/**
 * Determines if an element uses transform-based scroll.
 */
function isTransformScrollable(element) {
  const style = window.getComputedStyle(element);
  const transform = style.transform || "";
  return (
    (transform.includes("translate") || transform.includes("matrix")) &&
    style.overflow === "hidden" &&
    element.scrollHeight === 0 &&
    element.clientHeight === 0
  );
}

/**
 * Returns elements that are scrollable either traditionally or via transform,
 * filtered to avoid unnecessary or duplicate entries.
 */
function getScrollableElements() {
  const allElements = Array.from(document.querySelectorAll("*"));
  const scrollableSet = new Set();
  const added = new Set();

  for (const el of allElements) {
    const rect = el.getBoundingClientRect();
    if (
      rect.height === 0 ||
      rect.width === 0 ||
      !isElementInViewport(el) ||
      added.has(el)
    ) {
      continue;
    }
    if (el.tagName === "HTML" || el.tagName === "BODY") {
      continue;
    }

    if (isStandardScrollable(el)) {
      if (
        el.scrollTop === el.scrollHeight - el.clientHeight &&
        el.scrollLeft === el.scrollWidth - el.clientWidth
      ) {
        continue;
      }
      scrollableSet.add(el);
      added.add(el);
    } else if (isTransformScrollable(el)) {
      scrollableSet.add(el);
      added.add(el);
    }
  }

  return Array.from(scrollableSet);
}

/**
 * Scroll transform-based element.
 */
function scrollTransformElement(el, { direction = "vertical" }) {
  const style = window.getComputedStyle(el);
  const current = style.transform.match(
    /translate3d\(([^,]+),\s*([^,]+),\s*([^,]+)\)/,
  );
  let x = 0,
    y = 0,
    z = 0;
  if (current) {
    x = parseFloat(current[1]);
    y = parseFloat(current[2]);
    z = parseFloat(current[3]);
  }
  if (direction === "vertical" || direction === "both") y -= 100;
  if (direction === "horizontal" || direction === "both") x -= 100;
  el.style.transform = `translate3d(${x}px, ${y}px, ${z}px)`;
  return true;
}

/**
 * Core scroll animator: smoothly scrolls from an initial position toward computed targets in steps.
 * Resolves to true if scrolling occurred, false if no scroll was needed.
 *
 * @param {Object} params
 * @param {number} params.initialTop - Starting vertical offset.
 * @param {number} params.initialLeft - Starting horizontal offset.
 * @param {number} params.maxTop - Maximum vertical scroll offset.
 * @param {number} params.maxLeft - Maximum horizontal scroll offset.
 * @param {ScrollOpts} params.options - Scrolling options.
 * @param {Function} params.callback - Callback to perform the actual scroll: ({top, left, behavior}) => void.
 * @returns {Promise<boolean>}
 */
function _animateScroll({
  initialTop,
  initialLeft,
  maxTop,
  maxLeft,
  options,
  callback,
}) {
  const { direction = "vertical" } = options;

  return new Promise((resolve) => {
    const targetTop = direction === "horizontal" ? initialTop : maxTop;
    const targetLeft = direction === "vertical" ? initialLeft : maxLeft;

    if (initialTop === targetTop && initialLeft === targetLeft) {
      callback({ top: targetTop, left: targetLeft, behavior: "auto" });
      return resolve(false);
    }
    callback({ top: targetTop, left: targetLeft, behavior: "auto" });
    return resolve(true);
  });
}

/**
 * Smart scroll for any type of element.
 */
function scrollElement(el, options = {}) {
  if (isStandardScrollable(el)) {
    const maxTop = el.scrollHeight - el.clientHeight;
    const maxLeft = el.scrollWidth - el.clientWidth;

    if (maxTop === 0 && maxLeft === 0) return Promise.resolve(false);

    return _animateScroll({
      initialTop: el.scrollTop,
      initialLeft: el.scrollLeft,
      maxTop,
      maxLeft,
      options,
      callback: ({ top, left, behavior }) =>
        el.scrollTo({ top, left, behavior }),
    });
  } else if (isTransformScrollable(el)) {
    return Promise.resolve(scrollTransformElement(el, options));
  }
  return Promise.resolve(false);
}

/**
 * Parallel scroll for multiple elements.
 */
function scrollElements(elements, options = {}) {
  return Promise.all(elements.map((el) => scrollElement(el, options))).then(
    (results) => results.some((r) => r),
  );
}

/**
 * Viewport scroll.
 */
function scrollViewport(options = {}) {
  const { direction = "down" } = options;

  const maxY =
    Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.offsetHeight,
    ) - window.innerHeight;

  const currentY = window.scrollY;

  let targetY;
  if (direction === "up") {
    targetY = Math.max(currentY - window.innerHeight, 0);
  } else {
    // default is "down"
    targetY = Math.min(currentY + window.innerHeight, maxY);
  }

  if (targetY === currentY) return Promise.resolve(false);

  return _animateScroll({
    initialTop: currentY,
    initialLeft: window.scrollX,
    maxTop: targetY,
    maxLeft: window.scrollX,
    options: { direction },
    callback: ({ top, left, behavior }) =>
      window.scrollTo({ top, left, behavior }),
  });
}

/**
 * Basic viewport visibility check.
 */
function isElementInViewport(el) {
  const rect = el.getBoundingClientRect();
  return (
    rect.top < window.innerHeight &&
    rect.bottom > 0 &&
    rect.left < window.innerWidth &&
    rect.right > 0
  );
}

// Expose to window
window.getScrollableElements = getScrollableElements;
window.scrollElement = scrollElement;
window.scrollElements = scrollElements;
window.scrollViewport = scrollViewport;
window.ayejaxScriptAttached = true;
