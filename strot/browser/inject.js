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
  const allElements = getElementsInView(getElementsInDOM());
  const scrollableSet = new Set();
  const added = new Set();

  for (const el of allElements) {
    if (el.tagName === "HTML" || el.tagName === "BODY") {
      continue;
    }

    if (isStandardScrollable(el) || isTransformScrollable(el)) {
      scrollableSet.add(el);
      added.add(el);
    }
  }

  return Array.from(scrollableSet);
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

  const isWindowScrollable =
    document.documentElement.scrollHeight > window.innerHeight;
  let scrollableElement = null;
  if (!isWindowScrollable) {
    for (const element of getScrollableElements()) {
      if (element.getBoundingClientRect().height === window.innerHeight) {
        scrollableElement = element;
        break;
      }
    }
    if (!scrollableElement) return Promise.resolve(false);
  }

  let height = isWindowScrollable
    ? window.innerHeight
    : scrollableElement.getBoundingClientRect().height;

  // Fix: Use scrollableElement's scrollHeight when window is not scrollable
  const maxY = isWindowScrollable
    ? Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight,
        document.body.offsetHeight,
        document.documentElement.offsetHeight,
      ) - height
    : scrollableElement.scrollHeight - height; // Use scrollableElement's scrollHeight

  const currentY = isWindowScrollable
    ? window.scrollY
    : scrollableElement.scrollTop;

  let targetY;
  if (direction === "up") {
    targetY = Math.max(currentY - height, 0);
  } else {
    targetY = Math.min(currentY + height, maxY);
  }

  let callback;
  if (!isWindowScrollable) {
    callback = ({ top, left, behavior }) => {
      scrollableElement.scrollTo({ top, left, behavior });
    };
  } else {
    callback = ({ top, left, behavior }) => {
      window.scrollTo({ top, left, behavior });
    };
  }

  return _animateScroll({
    initialTop: currentY,
    initialLeft: isWindowScrollable
      ? window.scrollX
      : scrollableElement.scrollLeft,
    maxTop: targetY,
    maxLeft: isWindowScrollable ? window.scrollX : scrollableElement.scrollLeft,
    options: { direction: "vertical" },
    callback,
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
  return identifier
    .replace(/^([-0-9])/, "\\$1") // escape leading digit or hyphen
    .replace(/\s+/g, "\\ ") // escape whitespace
    .replace(/[!"#$%&'()*+,.\/:;<=>?@\[\\\]^`{|}~]/g, "\\$&");
}

/**
 * Helper function to generate a unique CSS selector for an element
 *
 * @param {HTMLElement} element - The element to generate a selector for
 * @returns {string} The CSS selector for the element
 */
function generateCSSSelector(element) {
  if (element === document.body) {
    return "body";
  }

  if (element.id) {
    return `#${escapeCSSIdentifier(element.id)}`;
  }

  const path = [];
  let current = element;

  while (current && current !== document.body) {
    let selector = buildOptimalSelector(current);
    path.unshift(selector);

    // Stop if parent has ID
    if (current.parentElement && current.parentElement.id) {
      path.unshift(`#${escapeCSSIdentifier(current.parentElement.id)}`);
      break;
    }

    current = current.parentElement;
  }

  return path.join(" > ");
}

/**
 * Build the most minimal selector for an element
 */
function buildOptimalSelector(element) {
  const tagName = element.tagName.toLowerCase();

  // Try just the tag name first
  let selector = tagName;
  if (isUniqueAmongSiblings(element, selector)) {
    return selector;
  }

  // Try with classes
  if (element.className) {
    const classes = Array.from(element.classList);
    const classSelector =
      tagName + `.${classes.map((cls) => escapeCSSIdentifier(cls)).join(".")}`;

    if (isUniqueAmongSiblings(element, classSelector)) {
      return classSelector;
    }
  }

  // Need nth-child
  const siblings = Array.from(element.parentElement.children);
  const index = siblings.indexOf(element) + 1;

  // Try tag + nth-child first (cleaner)
  const tagWithNth = tagName + `:nth-child(${index})`;
  if (isUniqueAmongSiblings(element, tagWithNth)) {
    return tagWithNth;
  }

  // Fall back to tag + classes + nth-child
  if (element.className) {
    const classes = Array.from(element.classList);
    return (
      tagName +
      `.${classes.map((cls) => escapeCSSIdentifier(cls)).join(".")}` +
      `:nth-child(${index})`
    );
  }

  return tagWithNth;
}

/**
 * Check if a selector uniquely identifies the element among its siblings
 */
function isUniqueAmongSiblings(element, selector) {
  if (!element.parentElement) return true;

  try {
    const matches = element.parentElement.querySelectorAll(
      `:scope > ${selector}`,
    );
    return matches.length === 1 && matches[0] === element;
  } catch (error) {
    return false;
  }
}

/**
 * Normalize text by removing extra whitespace and converting to lowercase
 *
 * @param {string} text - Text to normalize
 * @returns {string} Normalized text
 */
function normalizeText(text) {
  return text
    .replace(/\s+/g, "")
    .replace(/[\p{P}\p{S}]/gu, "")
    .trim()
    .toLowerCase();
}

/**
 * Simple approach: Find elements containing each section, then find their common parent
 *
 * @param {string[]} sections - Array of text sections to find
 * @param {number} threshold - Minimum percentage of sections that must be found
 * @returns {HTMLElement|null} Common parent element
 */
function findCommonParent(sections, threshold = 0.8) {
  if (!sections || sections.length === 0) return null;

  const sectionElements = [];
  const elementsInView = getElementsInView(getElementsInDOM());

  for (let i = 0; i < sections.length; i++) {
    const section = normalizeText(sections[i]);
    if (!section) continue;

    let bestElement = null;
    let smallestTextLength = Infinity;

    for (const element of elementsInView) {
      if (["HTML", "HEAD", "BODY", "SCRIPT", "STYLE"].includes(element.tagName))
        continue;
      if (!element.textContent || element.textContent.trim() === "") continue;

      // Ensure DOM ordering: current element should come after at least one captured element or be the same element
      if (sectionElements.length > 0) {
        const sameOrAfter = sectionElements.some(
          (capturedElement) =>
            capturedElement === element ||
            capturedElement.compareDocumentPosition(element) &
              Node.DOCUMENT_POSITION_FOLLOWING,
        );
        if (!sameOrAfter) {
          continue;
        }
      }

      const elementText = normalizeText(element.textContent || "");

      // First try exact match
      if (!elementText.includes(section)) {
        // If no exact match, try with 80% of the section text
        const partialSection = section.slice(
          0,
          Math.floor(section.length * 0.8),
        );
        if (!elementText.includes(partialSection)) continue;
      }

      // Keep the one with least text (most specific)
      const textLength = element.textContent.length;
      if (textLength < smallestTextLength) {
        smallestTextLength = textLength;
        bestElement = element;
      }
    }

    if (!bestElement) continue;
    sectionElements.push(bestElement);
  }

  const matchThreshold = Math.ceil(sections.length * threshold);
  if (sectionElements.length < matchThreshold) {
    return null;
  }

  if (sectionElements.length === 0) return null;
  if (sectionElements.length === 1) return sectionElements[0];

  // Start with first element and go up the DOM tree
  let currentParent = sectionElements[0];

  while (currentParent) {
    const containsAll = sectionElements.every((element) =>
      currentParent.contains(element),
    );

    if (containsAll) return currentParent;

    currentParent = currentParent.parentElement;
  }

  return null;
}

/**
 * Check if element is completely below the current viewport
 *
 * @param {HTMLElement} element - Element to check
 * @returns {boolean} True if element is completely below viewport
 */
function isElementCompletelyOutsideViewport(element) {
  return element.getBoundingClientRect().top > window.innerHeight;
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
 * Compares two DOM elements for structural similarity using a threshold-based approach.
 * Recursively checks tag names and child counts to calculate a similarity score.
 *
 * @param {HTMLElement} element1 - The first element to compare
 * @param {HTMLElement} element2 - The second element to compare
 * @param {number} threshold - Similarity threshold (0-1). Default is 0.95 (95%)
 * @returns {boolean} True if elements are structurally similar above the threshold
 *
 * @example
 * // Check if two elements are 95% similar (default)
 * const isSimilar = areStructurallyEqual(div1, div2);
 *
 * // Check with custom 90% threshold
 * const isSimilar = areStructurallyEqual(div1, div2, 0.90);
 */
function areStructurallyEqual(element1, element2, threshold = 0.95) {
  let totalChecks = 0;
  let passedChecks = 0;

  function compareRecursive(el1, el2) {
    totalChecks++;
    if (el1.tagName === el2.tagName) {
      passedChecks++;
    }

    totalChecks++;
    if (el1.children.length === el2.children.length) {
      passedChecks++;
    }

    // Compare children up to the minimum count
    const minChildren = Math.min(el1.children.length, el2.children.length);
    for (let i = 0; i < minChildren; i++) {
      compareRecursive(el1.children[i], el2.children[i]);
    }
  }

  compareRecursive(element1, element2);
  const similarity = passedChecks / totalChecks;

  return similarity >= threshold;
}

/**
 * Gets the last similar children or sibling based on structural comparison.
 * Returns the last similar element if:
 * 1. At least 80% of the element's children are similar to each other, OR
 * 2. At least 80% of siblings are similar to the given element
 *
 * @param {HTMLElement} element - The element to analyze
 * @param {Object} options - Configuration options
 * @param {number} options.threshold - Similarity threshold (0-1). Default is 0.95 (95%)
 * @param {boolean} options.isOutsideViewport - Whether to check if element is outside viewport. Default is false
 * @param {boolean} options.isVisible - Whether to check if element can scroll into view. Default is false
 * @returns {HTMLElement|null} The last similar child or sibling, or null if none found
 *
 * @example
 * // Get the last similar child or sibling (95% threshold)
 * const lastSimilar = getLastSimilarChildrenOrSibling(element);
 *
 * // Check with viewport conditions only
 * const lastSimilar = getLastSimilarChildrenOrSibling(element, { isOutsideViewport: true });
 *
 * // Check with visibility conditions only
 * const lastSimilar = getLastSimilarChildrenOrSibling(element, { isVisible: true });
 *
 * // Check with both viewport and visibility conditions
 * const lastSimilar = getLastSimilarChildrenOrSibling(element, { isOutsideViewport: true, isVisible: true });
 */
function getLastSimilarChildrenOrSibling(
  element,
  { threshold = 0.95, isOutsideViewport = false, isVisible = false } = {},
) {
  // Local function to process elements based on options
  function processElements(elements) {
    if (isOutsideViewport || isVisible) {
      // Find the last element that meets the specified conditions
      for (let i = elements.length - 1; i >= 0; i--) {
        const el = elements[i];
        const outsideViewport = isOutsideViewport
          ? isElementCompletelyOutsideViewport(el)
          : true;
        const canScroll = isVisible ? canScrollIntoView(el) : true;

        if (outsideViewport && canScroll) {
          return el;
        }
      }
      return null;
    } else {
      return elements[elements.length - 1];
    }
  }

  // Check if at least 80% of children are similar to each other
  const children = Array.from(element.children);
  if (children.length > 1) {
    const totalPairs = (children.length * (children.length - 1)) / 2;
    let similarPairs = 0;

    for (let i = 0; i < children.length; i++) {
      for (let j = i + 1; j < children.length; j++) {
        if (areStructurallyEqual(children[i], children[j], threshold)) {
          similarPairs++;
        }
      }
    }

    const similarityPercentage = similarPairs / totalPairs;
    if (similarityPercentage >= 0.8) {
      return processElements(children);
    }
  }

  // Check if at least 80% of siblings are similar to the given element
  if (element.parentElement) {
    const siblings = Array.from(element.parentElement.children).filter(
      (sibling) => sibling !== element,
    );
    if (siblings.length > 0) {
      let similarSiblings = 0;

      for (let sibling of siblings) {
        if (areStructurallyEqual(element, sibling, threshold)) {
          similarSiblings++;
        }
      }

      const siblingsSimilarityPercentage = similarSiblings / siblings.length;
      if (siblingsSimilarityPercentage >= 0.8) {
        const allSiblings = Array.from(element.parentElement.children);
        return processElements(allSiblings);
      }
    }
  }

  return null;
}

// Expose to window
window.scrollToNextView = scrollToNextView;
window.getElementsInDOM = getElementsInDOM;
window.getElementsInView = getElementsInView;
window.generateCSSSelector = generateCSSSelector;
window.isElementCompletelyOutsideViewport = isElementCompletelyOutsideViewport;
window.canScrollIntoView = canScrollIntoView;
window.findCommonParent = findCommonParent;
window.areStructurallyEqual = areStructurallyEqual;
window.getLastSimilarChildrenOrSibling = getLastSimilarChildrenOrSibling;
window.strotPluginInjected = true;
