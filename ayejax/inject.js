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
function scrollToNextView(options = {}) {
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

// Helper function to escape CSS identifiers for use in selectors
function escapeCSSIdentifier(identifier) {
  // Use CSS.escape if available (modern browsers)
  if (typeof CSS !== "undefined" && CSS.escape) {
    return CSS.escape(identifier);
  }

  // Fallback: manually escape special characters
  return identifier.replace(/[!"#$%&'()*+,.\/:;<=>?@\[\\\]^`{|}~]/g, "\\$&");
}

// Helper function to generate a CSS selector for an element
function generateCSSSelector(element) {
  if (element.id) {
    return `#${escapeCSSIdentifier(element.id)}`;
  }

  const path = [];
  let current = element;

  while (current && current !== document.body) {
    let selector = current.tagName.toLowerCase();

    if (current.className) {
      const classes = Array.from(current.classList);
      selector += `.${classes
        .map((cls) => escapeCSSIdentifier(cls))
        .join(".")}`;
    }

    if (current.parentElement) {
      const siblings = Array.from(current.parentElement.children);
      const index = siblings.indexOf(current) + 1;
      selector += `:nth-child(${index})`;
    }

    path.unshift(selector);

    if (current.parentElement && current.parentElement.id) {
      path.unshift(`#${escapeCSSIdentifier(current.parentElement.id)}`);
      break;
    }

    current = current.parentElement;
  }

  return path.join(" > ");
}
// Helper function to check if two elements are similar
function areElementsSimilar(elem1, elem2) {
  // Don't compare element with itself
  if (elem1 === elem2) return false;

  // Same tag name
  if (elem1.tagName !== elem2.tagName) return false;

  // Get all attributes for both elements
  const attrs1 = Array.from(elem1.attributes);
  const attrs2 = Array.from(elem2.attributes);

  // Must have same number of attributes
  if (attrs1.length !== attrs2.length) return false;

  // Check each attribute exists in both elements with same value
  for (const attr of attrs1) {
    const attrName = attr.name;
    const attrValue1 = attr.value;

    if (!elem2.hasAttribute(attrName)) return false;

    const attrValue2 = elem2.getAttribute(attrName);

    // Special handling for class attribute - compare sorted class lists
    if (attrName === "class") {
      const classList1 = attrValue1
        .trim()
        .split(/\s+/)
        .filter((c) => c)
        .sort();
      const classList2 = attrValue2
        .trim()
        .split(/\s+/)
        .filter((c) => c)
        .sort();

      if (classList1.length !== classList2.length) return false;
      for (let i = 0; i < classList1.length; i++) {
        if (classList1[i] !== classList2[i]) return false;
      }
    } else {
      // For all other attributes, values must be identical
      if (attrValue1 !== attrValue2) return false;
    }
  }

  return true;
}

function getElementsInDOM() {
  return Array.from(document.querySelectorAll("*"));
}

/**
 * Get elements that are in viewport.
 *
 * @param {HTMLElement[]} elements - Array of elements to check.
 * @param {number} surfaceRatio - Surface ratio to expand viewport bounds (1.0 = normal viewport, 1.25 = 25% larger, etc.).
 * @returns {HTMLElement[]} Array of elements that are in viewport.
 */
function getElementsInView(elements, surfaceRatio = 1.0) {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  const extraWidth = (viewportWidth * (surfaceRatio - 1)) / 2;
  const extraHeight = (viewportHeight * (surfaceRatio - 1)) / 2;

  return elements.filter((el) => {
    const rect = el.getBoundingClientRect();
    return (
      rect.top >= -extraHeight &&
      rect.left >= -extraWidth &&
      rect.bottom <= viewportHeight + extraHeight &&
      rect.right <= viewportWidth + extraWidth &&
      rect.width > 0 &&
      rect.height > 0
    );
  });
}

/**
 * Check if element comes after another element in document order
 * @param {HTMLElement} elementA - First element
 * @param {HTMLElement} elementB - Second element
 * @returns {boolean} True if elementB comes after elementA in document order
 */
function isElementAfter(elementA, elementB) {
  const position = elementA.compareDocumentPosition(elementB);
  return !!(position & Node.DOCUMENT_POSITION_FOLLOWING);
}

/**
 * Check if element is completely outside the original viewport
 * @param {HTMLElement} element - Element to check
 * @returns {boolean} True if element is completely outside viewport
 */
function isElementCompletelyOutsideViewport(element) {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  const rect = element.getBoundingClientRect();

  return (
    rect.bottom < 0 ||
    rect.top > viewportHeight ||
    rect.right < 0 ||
    rect.left > viewportWidth
  );
}

/**
 * Check if an element can be scrolled into view
 * @param {HTMLElement} element - Element to check
 * @returns {boolean} True if element can be scrolled into view
 */
function canScrollIntoView(element) {
  // Check CSS visibility
  const computedStyle = window.getComputedStyle(element);
  if (
    computedStyle.display === "none" ||
    computedStyle.visibility === "hidden" ||
    computedStyle.opacity === "0"
  ) {
    return false;
  }

  // Check if element is behind other elements (optional)
  const rect = element.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;

  // If center point is within viewport, check if element is the topmost
  if (
    centerX >= 0 &&
    centerX <= window.innerWidth &&
    centerY >= 0 &&
    centerY <= window.innerHeight
  ) {
    const topElement = document.elementFromPoint(centerX, centerY);
    if (
      topElement &&
      !element.contains(topElement) &&
      !topElement.contains(element)
    ) {
      // Element might be behind another element
      console.warn("Element might be obscured by another element");
    }
  }

  return true;
}

/**
 * Map elements in viewport to their last visible sibling that comes AFTER them
 * @param {number} surfaceRatio - Surface ratio to expand viewport bounds
 * @returns {Map<HTMLElement, HTMLElement>} Map of elements to last visible siblings after them
 */
function mapLastVisibleSiblings(surfaceRatio = 1.0) {
  const elementsInDOM = getElementsInDOM();
  const elementsInView = getElementsInView(elementsInDOM, surfaceRatio);
  const leafElementsInView = elementsInView.filter(
    (el) =>
      !elementsInView.some((otherEl) => otherEl !== el && el.contains(otherEl)),
  );

  const mapping = new Map();

  leafElementsInView.forEach((elementInView) => {
    const elementText = elementInView.textContent?.trim() || "";
    if (!elementText) return;

    if (elementInView.attributes.length === 0) {
      const parentElement = elementInView.parentElement;
      if (getElementsInView([parentElement], surfaceRatio).length > 0) {
        console.log(`Element has no attributes, using parent element instead`);
        elementInView = parentElement;
      }
    }

    console.log(
      `\n--- Processing element: "${elementText.substring(0, 50)}..." ---`,
    );

    const allSimilarElements = elementsInDOM.filter((element) =>
      areElementsSimilar(elementInView, element),
    );

    console.log(`Found ${allSimilarElements.length} similar elements total`);

    if (allSimilarElements.length === 0) {
      console.log(`No similar siblings found`);
      return;
    }

    const siblingsAfterViewport = allSimilarElements.filter((sibling) =>
      isElementAfter(elementInView, sibling),
    );

    console.log(
      `${siblingsAfterViewport.length} siblings come after the viewport element`,
    );

    if (siblingsAfterViewport.length === 0) {
      console.log(`No siblings after viewport element`);
      return;
    }

    const siblingsAfterAndOutside = siblingsAfterViewport.filter((sibling) =>
      isElementCompletelyOutsideViewport(sibling),
    );

    console.log(
      `${siblingsAfterAndOutside.length} siblings are after viewport AND outside view`,
    );

    if (siblingsAfterAndOutside.length === 0) {
      console.log(`No siblings both after viewport and outside view`);
      return;
    }

    const visibleSiblingsAfter =
      siblingsAfterAndOutside.filter(canScrollIntoView);

    console.log(
      `${visibleSiblingsAfter.length} siblings are after viewport, outside view, and visible`,
    );

    if (visibleSiblingsAfter.length === 0) {
      console.log(`No visible siblings after viewport`);
      return;
    }

    const lastSiblingAfter =
      visibleSiblingsAfter[visibleSiblingsAfter.length - 1];

    const lastRect = lastSiblingAfter.getBoundingClientRect();
    console.log(
      `Selected last sibling AFTER viewport: "${lastSiblingAfter.textContent
        .trim()
        .substring(0, 50)}..."`,
    );
    console.log(
      `Position: top=${Math.round(
        lastRect.top + window.pageYOffset,
      )}, viewport_top=${Math.round(lastRect.top)}`,
    );

    mapping.set(elementInView, lastSiblingAfter);
  });

  console.log(`\nFinal mapping has ${mapping.size} entries`);
  return mapping;
}

// Expose to window
window.scrollToNextView = scrollToNextView;
window.getElementsInDOM = getElementsInDOM;
window.getElementsInView = getElementsInView;
window.mapLastVisibleSiblings = mapLastVisibleSiblings;
window.generateCSSSelector = generateCSSSelector;
window.scriptInjected = true;
