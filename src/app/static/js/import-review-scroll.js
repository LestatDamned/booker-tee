(() => {
  const reviewItemSelector = ".review-item";
  const storageKey = `booker-tee.review-scroll:${window.location.pathname}`;
  let pendingReviewPosition = null;
  let restoreTimerIds = [];

  if ("scrollRestoration" in history) {
    history.scrollRestoration = "manual";
  }

  const readStoredPosition = () => {
    try {
      return JSON.parse(sessionStorage.getItem(storageKey) || "null");
    } catch {
      return null;
    }
  };

  const forgetStoredPosition = () => {
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      // Ignore storage failures: scroll restoration is a UI enhancement.
    }
  };

  const captureReviewPosition = (row) => {
    const rect = row.getBoundingClientRect();
    return {
      rowId: row.id,
      scrollY: window.scrollY,
      top: rect.top,
    };
  };

  const rememberReviewPosition = (row) => {
    const currentPosition = captureReviewPosition(row);
    pendingReviewPosition = currentPosition;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(currentPosition));
    } catch {
      // Keep the in-memory position for the current HTMX cycle.
    }
  };

  const restoreReviewPosition = (state) => {
    if (!state) {
      return;
    }

    const target = state.rowId ? document.getElementById(state.rowId) : null;
    if (target && Number.isFinite(state.top)) {
      const currentTop = target.getBoundingClientRect().top;
      window.scrollTo(0, Math.max(0, window.scrollY + currentTop - state.top));
      return;
    }

    if (Number.isFinite(state.scrollY)) {
      window.scrollTo(0, state.scrollY);
    }
  };

  const scheduleReviewPositionRestore = (state) => {
    if (!state) {
      return;
    }
    restoreTimerIds.forEach((timerId) => window.clearTimeout(timerId));
    restoreTimerIds = [0, 80, 180, 360].map((delay, index, delays) => {
      return window.setTimeout(() => {
        requestAnimationFrame(() => {
          restoreReviewPosition(state);
          if (index === delays.length - 1) {
            pendingReviewPosition = null;
            forgetStoredPosition();
            restoreTimerIds = [];
          }
        });
      }, delay);
    });
  };

  window.addEventListener(
    "pageshow",
    () => {
      scheduleReviewPositionRestore(readStoredPosition());
    },
    { once: true },
  );

  document.addEventListener("htmx:afterSettle", () => {
    scheduleReviewPositionRestore(pendingReviewPosition || readStoredPosition());
  });

  document.addEventListener("htmx:beforeRequest", (event) => {
    const source = event.detail ? event.detail.elt : null;
    if (!(source instanceof Element)) {
      return;
    }

    const row = source.closest(reviewItemSelector);
    if (!row || !row.id) {
      return;
    }

    rememberReviewPosition(row);
  });

  document.addEventListener("htmx:afterRequest", () => {
    scheduleReviewPositionRestore(pendingReviewPosition || readStoredPosition());
  });

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) {
        return;
      }

      const row = form.closest(reviewItemSelector);
      if (!row || !row.id) {
        return;
      }

      rememberReviewPosition(row);
    },
    true,
  );
})();
