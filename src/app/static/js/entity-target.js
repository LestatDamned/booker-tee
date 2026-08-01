(function () {
  const TARGET_CLEARED_CLASS_NAME = "entity-target-cleared";
  const WORKING_CLASS_NAME = "entity-card--working";
  const WORKING_SELECTOR = '[data-entity-working="true"]';
  let pendingWorkingElementId = null;
  const RECENT_CLASS_NAMES = [
    "rule-card--recent",
    "category-card--recent",
  ];
  const RECENT_FEEDBACK_SELECTORS = [
    ".rule-list-feedback",
    ".category-list-feedback",
  ];
  const RECENT_QUERY_KEYS = [
    "recent_rule_id",
    "recent_category_id",
  ];
  const INTERACTIVE_SELECTOR = [
    "a",
    "button",
    "summary",
    "input",
    "select",
    "textarea",
    "label",
    "[role='button']",
  ].join(",");

  function markWorking(element) {
    document
      .querySelectorAll(`.${WORKING_CLASS_NAME}`)
      .forEach((currentElement) => {
        if (currentElement !== element) {
          currentElement.classList.remove(WORKING_CLASS_NAME);
        }
      });
    element.classList.add(WORKING_CLASS_NAME);
  }

  function clearRecentState() {
    for (const className of RECENT_CLASS_NAMES) {
      document.querySelectorAll(`.${className}`).forEach((element) => {
        element.classList.remove(className);
      });
    }

    for (const selector of RECENT_FEEDBACK_SELECTORS) {
      document.querySelectorAll(selector).forEach((element) => {
        element.remove();
      });
    }
  }

  function clearFeedbackUrl() {
    const url = new URL(window.location.href);
    let changed = false;

    if (url.hash) {
      url.hash = "";
      changed = true;
    }

    for (const key of RECENT_QUERY_KEYS) {
      if (url.searchParams.has(key)) {
        url.searchParams.delete(key);
        changed = true;
      }
    }

    if (changed) {
      window.history.replaceState(window.history.state, "", url);
    }
  }

  function clearTargetState() {
    document.documentElement.classList.add(TARGET_CLEARED_CLASS_NAME);
    clearRecentState();
    clearFeedbackUrl();
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    if (!target.closest(INTERACTIVE_SELECTOR)) {
      return;
    }
    const workingElement = target.closest(WORKING_SELECTOR);
    window.setTimeout(clearTargetState, 0);
    if (workingElement instanceof Element) {
      window.setTimeout(() => markWorking(workingElement), 0);
    }
  });

  document.addEventListener("htmx:beforeRequest", (event) => {
    clearTargetState();
    const source = event.detail ? event.detail.elt : null;
    const workingElement =
      source instanceof Element ? source.closest(WORKING_SELECTOR) : null;
    pendingWorkingElementId =
      workingElement instanceof Element ? workingElement.id : null;
  });

  document.addEventListener("htmx:afterSettle", () => {
    if (!pendingWorkingElementId) {
      return;
    }
    const workingElement = document.getElementById(pendingWorkingElementId);
    pendingWorkingElementId = null;
    if (
      !(workingElement instanceof Element) ||
      !workingElement.matches(WORKING_SELECTOR)
    ) {
      return;
    }
    markWorking(workingElement);
  });

  window.addEventListener("hashchange", () => {
    if (window.location.hash) {
      document.documentElement.classList.remove(TARGET_CLEARED_CLASS_NAME);
    }
  });
})();
