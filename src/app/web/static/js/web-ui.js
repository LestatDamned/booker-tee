(function () {
  "use strict";

  const ROW_SELECTOR = ".workbench-row";
  const WORKING_CLASS = "workbench-row--working";
  const RECENT_CLASS = "workbench-row--recent";
  const PRIMARY_FOCUS_SELECTOR = [
    ".action-stack__primary a:not([aria-disabled='true'])",
    ".action-stack__primary button:not(:disabled)",
    "a:not([aria-disabled='true'])",
    "button:not(:disabled)",
  ].join(",");
  let pendingReplacement = null;

  function disclosure(initialOpen) {
    return {
      open: Boolean(initialOpen),
      close() {
        this.open = false;
      },
      cancel() {
        this.$root.dispatchEvent(new CustomEvent("bt:disclosure-cancel", { bubbles: true }));
        this.open = false;
      },
    };
  }

  function requestScope(element) {
    return element instanceof Element ? element.closest("[data-request-scope]") : null;
  }

  function setRequestBusy(scope, busy) {
    if (!(scope instanceof Element)) {
      return;
    }
    scope.setAttribute("aria-busy", busy ? "true" : "false");
    scope.querySelectorAll("button[type='submit']").forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      if (busy) {
        button.dataset.wasDisabled = button.disabled ? "true" : "false";
        button.disabled = true;
        return;
      }
      button.disabled = button.dataset.wasDisabled === "true";
      delete button.dataset.wasDisabled;
    });
  }

  function clearTransientUrl() {
    const url = new URL(window.location.href);
    if (!url.hash) {
      return;
    }
    url.hash = "";
    window.history.replaceState(window.history.state, "", url);
  }

  function markWorking(row) {
    if (!(row instanceof Element)) {
      return;
    }
    document.querySelectorAll(`${ROW_SELECTOR}.${WORKING_CLASS}`).forEach((current) => {
      if (current !== row) {
        current.classList.remove(WORKING_CLASS);
      }
    });
    row.classList.remove(RECENT_CLASS);
    row.classList.add(WORKING_CLASS);
  }

  function replacementContext(source) {
    const row = source instanceof Element ? source.closest(ROW_SELECTOR) : null;
    if (!(row instanceof HTMLElement) || !row.id) {
      return null;
    }
    const siblings = Array.from(document.querySelectorAll(ROW_SELECTOR));
    const index = siblings.indexOf(row);
    return {
      row,
      rowId: row.id,
      nextId: siblings[index + 1] instanceof HTMLElement ? siblings[index + 1].id : null,
      previousId: siblings[index - 1] instanceof HTMLElement ? siblings[index - 1].id : null,
    };
  }

  function focusRow(row) {
    if (!(row instanceof HTMLElement)) {
      return false;
    }
    const explicitTarget = row.querySelector("[data-focus-on-swap]");
    if (explicitTarget instanceof HTMLElement) {
      explicitTarget.focus({ preventScroll: true });
      return true;
    }
    const invalidField = row.querySelector("[aria-invalid='true']");
    if (invalidField instanceof HTMLElement) {
      invalidField.focus({ preventScroll: true });
      return true;
    }
    const focusTarget = row.querySelector(PRIMARY_FOCUS_SELECTOR);
    if (focusTarget instanceof HTMLElement) {
      focusTarget.focus({ preventScroll: true });
      return true;
    }
    row.tabIndex = -1;
    row.focus({ preventScroll: true });
    return true;
  }

  function restoreReplacementFocus(context) {
    if (!context) {
      return;
    }
    const currentRow = document.getElementById(context.rowId);
    if (currentRow === context.row) {
      return;
    }
    if (focusRow(currentRow)) {
      markWorking(currentRow);
      return;
    }
    if (focusRow(context.nextId ? document.getElementById(context.nextId) : null)) {
      return;
    }
    if (focusRow(context.previousId ? document.getElementById(context.previousId) : null)) {
      return;
    }
    const fallback = document.querySelector("[data-focus-fallback]");
    if (fallback instanceof HTMLElement) {
      fallback.tabIndex = -1;
      fallback.focus({ preventScroll: true });
    }
  }

  function resetDisclosureStates() {
    document.querySelectorAll("[data-disclosure-reset]").forEach((scope) => {
      scope.removeAttribute("data-disclosure-reset");
      if (
        window.Alpine
        && typeof window.Alpine.destroyTree === "function"
        && typeof window.Alpine.initTree === "function"
      ) {
        window.Alpine.destroyTree(scope);
        Reflect.deleteProperty(scope, "_x_dataStack");
        window.Alpine.initTree(scope);
      }
    });
  }

  document.addEventListener("alpine:init", () => {
    window.Alpine.data("disclosure", disclosure);
  });

  document.addEventListener("click", (event) => {
    const row = event.target instanceof Element ? event.target.closest(ROW_SELECTOR) : null;
    if (!(row instanceof Element)) {
      return;
    }
    clearTransientUrl();
    markWorking(row);
  });

  document.addEventListener("htmx:beforeRequest", (event) => {
    const source = event.detail ? event.detail.elt : null;
    const scope = requestScope(source);
    setRequestBusy(scope, true);
    pendingReplacement = replacementContext(source);
    if (pendingReplacement) {
      markWorking(pendingReplacement.row);
    }
  });

  document.addEventListener("htmx:beforeSwap", (event) => {
    const status = event.detail && event.detail.xhr ? event.detail.xhr.status : null;
    if (status === 409 || status === 422) {
      event.detail.shouldSwap = true;
      event.detail.isError = false;
    }
  });

  document.addEventListener("htmx:afterSettle", (event) => {
    const source = event.detail ? event.detail.elt : null;
    setRequestBusy(requestScope(source), false);
    resetDisclosureStates();
    restoreReplacementFocus(pendingReplacement);
    pendingReplacement = null;
  });

  document.addEventListener("htmx:responseError", (event) => {
    const source = event.detail ? event.detail.elt : null;
    const scope = requestScope(source);
    setRequestBusy(scope, false);
    if (scope instanceof Element) {
      scope.dispatchEvent(new CustomEvent("bt:request-error", { bubbles: true }));
    }
    pendingReplacement = null;
  });

  window.BookerTeeUI = Object.freeze({ disclosure });
})();
