(function () {
  const TARGET_CLEARED_CLASS_NAME = "entity-target-cleared";
  const WORKING_CLASS_NAME = "entity-card--working";
  const WORKING_SELECTOR = '[data-entity-working="true"]';
  let pendingWorkingElementId = null;
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

  function clearFeedbackUrl() {
    const url = new URL(window.location.href);
    let changed = false;

    if (url.hash) {
      url.hash = "";
      changed = true;
    }

    if (changed) {
      window.history.replaceState(window.history.state, "", url);
    }
  }

  function clearTargetState() {
    document.documentElement.classList.add(TARGET_CLEARED_CLASS_NAME);
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
