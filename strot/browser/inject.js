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
      // First check if selector without nth-child is unique
      const pathWithoutNth = [...path];
      pathWithoutNth.unshift(selector);

      if (current.parentElement.id) {
        pathWithoutNth.unshift(
          `#${escapeCSSIdentifier(current.parentElement.id)}`,
        );
      }

      const testSelectorWithoutNth = pathWithoutNth.join(" > ");

      // Check if selector without nth-child matches multiple elements
      let needsNthChild = false;
      try {
        const foundElements = document.querySelectorAll(testSelectorWithoutNth);

        if (foundElements.length > 1) {
          needsNthChild = true;
        }
      } catch (error) {
        // If selector is invalid, we'll try with nth-child
        needsNthChild = true;
      }

      // Only add nth-child if the selector matches multiple elements
      if (needsNthChild) {
        // CSS nth-child counts ALL children, not just visible ones
        const siblings = Array.from(current.parentElement.children);
        const index = siblings.indexOf(current) + 1;

        // Try with nth-child
        const selectorWithNth = selector + `:nth-child(${index})`;
        const pathWithNth = [...path];
        pathWithNth.unshift(selectorWithNth);

        if (current.parentElement.id) {
          pathWithNth.unshift(
            `#${escapeCSSIdentifier(current.parentElement.id)}`,
          );
        }

        const testSelector = pathWithNth.join(" > ");

        // Check if selector with nth-child works and is unique
        try {
          const found = document.querySelector(testSelector);
          if (found === element) {
            selector = selectorWithNth;
          }
          // If it doesn't work, keep selector without nth-child
        } catch (error) {
          // If selector is invalid, keep selector without nth-child
        }
      }
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
 * Find all containers that contain all given text sections
 *
 * @param {string[]} sections - Array of text sections to find
 * @returns {Object[]} Array of container objects with selector and text
 */
function getContainersWithTextSections(sections) {
  const allElements = getElementsInDOM();

  // Normalize search sections once
  const normalizedSections = sections.map((s) => s.replace(/\s+/g, "").trim());

  // Find all potential container elements that contain all text sections
  const potentialContainers = allElements.filter((container) => {
    if (
      container.tagName.toLowerCase() === "html" ||
      container.tagName.toLowerCase() === "body"
    ) {
      return false;
    }

    // Normalize whitespace for comparison
    const containerText = container.textContent.replace(/\s+/g, "").trim();

    const containerTextLower = containerText.toLowerCase();
    const containsAllSections = normalizedSections.every(
      (normalizedSection) => {
        const normalizedSectionLower = normalizedSection.toLowerCase();
        return containerTextLower.includes(normalizedSectionLower);
      },
    );

    return containsAllSections;
  });

  if (potentialContainers.length === 0) {
    // If no single container has all sections, try to find the parent of containers with individual sections
    // This handles cases where sections are from multiple items
    const containersBySection = sections.map((section) => {
      const sectionLower = section.replace(/\s+/g, "").trim().toLowerCase();
      return allElements.filter((el) => {
        if (el.tagName.toLowerCase() === "html") return false;
        const text = el.textContent.replace(/\s+/g, "").trim().toLowerCase();
        return text.includes(sectionLower) && text.length < 2000; // Focus on smaller containers
      });
    });

    // Find common parents
    const firstSectionContainers = containersBySection[0] || [];

    if (firstSectionContainers.length > 0) {
      // Get all potential parent containers
      const parentCandidates = new Set();
      firstSectionContainers.forEach((container) => {
        let parent = container.parentElement;
        while (parent && parent !== document.body) {
          // Check if this parent contains most/all sections
          const parentText = parent.textContent
            .replace(/\s+/g, "")
            .trim()
            .toLowerCase();
          const sectionsInParent = normalizedSections.filter((section) =>
            parentText.includes(section.toLowerCase()),
          );

          if (
            sectionsInParent.length >=
            Math.ceil(normalizedSections.length * 0.6)
          ) {
            // At least 60% of sections
            parentCandidates.add(parent);
            break; // Don't go higher once we find a good parent
          }
          parent = parent.parentElement;
        }
      });

      if (parentCandidates.size > 0) {
        const parents = Array.from(parentCandidates);
        const result = parents.map((container) => ({
          selector: generateCSSSelector(container),
          text: container.textContent.trim(),
        }));
        return result;
      }
    }

    return [];
  }

  const result = potentialContainers.map((container) => {
    return {
      selector: generateCSSSelector(container),
      text: container.textContent.trim(),
    };
  });

  return result;
}

/**
 * Find the last visible child
 *
 * @param {HTMLElement} parentContainer - Parent container element
 * @returns {String|null} CSS selector of the last visible child
 */
function getLastVisibleChild(parentContainer) {
  // Get all direct children of the parent container
  const children = Array.from(parentContainer.children);
  if (children.length < 2) {
    return null;
  }

  // Find the last child that can be scrolled into view
  for (let i = children.length - 1; i >= 0; i--) {
    const child = children[i];

    // Check if child is completely outside viewport
    const isOutsideViewport = isElementCompletelyOutsideViewport(child);
    if (!isOutsideViewport) {
      continue;
    }

    // Check if child can be scrolled into view
    if (canScrollIntoView(child)) {
      return generateCSSSelector(child);
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
window.getContainersWithTextSections = getContainersWithTextSections;
window.getLastVisibleChild = getLastVisibleChild;
window.strotPluginInjected = true;
