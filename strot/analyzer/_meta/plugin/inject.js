/**
 * @typedef {Object} ScrollOpts
 * @property {('vertical'|'horizontal'|'both')} [direction='both'] - Which direction to scroll.
 */

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
 * Scroll to next view.
 *
 * @param {Object} options
 * @param {('up'|'down')} [options.direction='down'] - Which direction to scroll.
 * @returns {Promise<boolean>}
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
    targetY = Math.min(currentY + window.innerHeight, maxY);
  }

  if (targetY === currentY) return Promise.resolve(false);

  return _animateScroll({
    initialTop: currentY,
    initialLeft: window.scrollX,
    maxTop: targetY,
    maxLeft: window.scrollX,
    options: { direction: "vertical" },
    callback: ({ top, left, behavior }) =>
      window.scrollTo({ top, left, behavior }),
  });
}

/**
 * Helper function to escape CSS identifiers for use in selectors
 *
 * @param {string} identifier - The identifier to escape
 * @returns {string} The escaped identifier
 */
function escapeCSSIdentifier(identifier) {
  // Use CSS.escape if available (modern browsers)
  if (typeof CSS !== "undefined" && CSS.escape) {
    return CSS.escape(identifier);
  }

  // Fallback: manually escape special characters
  return identifier.replace(/[!"#$%&'()*+,.\/:;<=>?@\[\\\]^`{|}~]/g, "\\$&");
}

/**
 * Helper function to generate a CSS selector for an element
 *
 * @param {HTMLElement} element - The element to generate a selector for
 * @returns {string} The CSS selector for the element
 */
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

/**
 * Check if two elements are similar
 *
 * @param {HTMLElement} element1
 * @param {HTMLElement} element2
 * @returns {boolean}
 */
function areElementsSimilar(element1, element2) {
  // They should not be identical
  if (element1 === element2) return false;

  // Same tag name
  if (element1.tagName !== element2.tagName) return false;

  // Get all attributes for both elements
  const attrs1 = Array.from(element1.attributes);
  const attrs2 = Array.from(element2.attributes);

  // Must have same number of attributes
  if (attrs1.length !== attrs2.length) return false;

  // Check each attribute exists in both elements with same value
  for (const attr of attrs1) {
    const attrName = attr.name;
    const attrValue1 = attr.value;

    if (!element2.hasAttribute(attrName)) return false;

    const attrValue2 = element2.getAttribute(attrName);

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

/**
 * Get all elements in the DOM.
 *
 * @returns {HTMLElement[]} Array of all elements in the DOM.
 */
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
 *
 * @param {HTMLElement} elementA - First element
 * @param {HTMLElement} elementB - Second element
 * @returns {boolean} True if elementB comes after elementA in document order
 */
function isElementAfter(elementA, elementB) {
  const position = elementA.compareDocumentPosition(elementB);
  return !!(position & Node.DOCUMENT_POSITION_FOLLOWING);
}

/**
 * Check if element is completely outside the current viewport
 *
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
 *
 * @param {HTMLElement} element - Element to check
 * @returns {boolean} True if element can be scrolled into view
 */
function canScrollIntoView(element) {
  const computedStyle = window.getComputedStyle(element);
  if (
    computedStyle.display === "none" ||
    computedStyle.visibility === "hidden" ||
    computedStyle.opacity === "0"
  ) {
    return false;
  }

  return true;
}

/**
 * Map elements in viewport to their last visible sibling in the DOM
 *
 * @param {number} surfaceRatio - Surface ratio to expand viewport bounds
 * @returns {Map<HTMLElement, HTMLElement>} Map of elements to last visible siblings in the DOM
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

    // if element has no attributes, use its parent element if it is in view
    if (elementInView.attributes.length === 0) {
      const parentElement = elementInView.parentElement;
      if (getElementsInView([parentElement], surfaceRatio).length > 0) {
        elementInView = parentElement;
      }
    }

    // Only consider elements that have one or more similar siblings
    const allSimilarElements = elementsInDOM.filter((element) =>
      areElementsSimilar(elementInView, element),
    );
    if (allSimilarElements.length === 0) {
      return;
    }

    // Only consider siblings that comes after the current viewport element
    const siblingsAfterViewport = allSimilarElements.filter((sibling) =>
      isElementAfter(elementInView, sibling),
    );
    if (siblingsAfterViewport.length === 0) {
      return;
    }

    // Only consider siblings that are completely outside the viewport
    const siblingsAfterAndOutside = siblingsAfterViewport.filter((sibling) =>
      isElementCompletelyOutsideViewport(sibling),
    );
    if (siblingsAfterAndOutside.length === 0) {
      return;
    }

    // Only consider siblings that are visible
    const visibleSiblings = siblingsAfterAndOutside.filter(canScrollIntoView);
    if (visibleSiblings.length === 0) {
      return;
    }

    // Select the last visible sibling
    const lastSibling = visibleSiblings[visibleSiblings.length - 1];
    mapping.set(elementInView, lastSibling);
  });

  return mapping;
}

// Expose to window
window.scrollToNextView = scrollToNextView;
window.getElementsInDOM = getElementsInDOM;
window.getElementsInView = getElementsInView;
window.mapLastVisibleSiblings = mapLastVisibleSiblings;
window.generateCSSSelector = generateCSSSelector;
window.strotPluginInjected = true;
