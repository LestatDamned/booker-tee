(function () {
  const TARGET_CLEARED_CLASS_NAME = "entity-target-cleared";
  const TARGET_CLASS_NAMES = ["manual-operation-row--target"];
  const TARGET_QUERY_KEYS = ["operation_id"];
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

  function clearTargetClasses() {
    for (const className of TARGET_CLASS_NAMES) {
      document.querySelectorAll(`.${className}`).forEach((element) => {
        element.classList.remove(className);
      });
    }
  }

  function clearTargetUrl() {
    const url = new URL(window.location.href);
    let changed = false;

    if (url.hash) {
      url.hash = "";
      changed = true;
    }

    for (const key of TARGET_QUERY_KEYS) {
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
    clearTargetClasses();
    clearTargetUrl();
  }

  document.addEventListener(
    "pointerdown",
    (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (!target.closest(INTERACTIVE_SELECTOR)) {
        return;
      }
      clearTargetState();
    },
    { capture: true },
  );

  document.addEventListener("htmx:beforeRequest", clearTargetState);
  window.addEventListener("hashchange", () => {
    if (window.location.hash) {
      document.documentElement.classList.remove(TARGET_CLEARED_CLASS_NAME);
    }
  });
})();
