const HASH_TARGET_DURATION_MS = 4_000;
let arrivalSequence = 0;

export function navigateToHashTarget(hash: string): boolean {
  if (!hash) return false;
  try {
    const target = document.getElementById(decodeURIComponent(hash.slice(1)));
    return target instanceof HTMLElement ? revealHashTarget(target) : false;
  } catch {
    return false;
  }
}

export function revealHashTarget(target: HTMLElement): true {
  document
    .querySelectorAll<HTMLElement>("[data-hash-target-focus]")
    .forEach((element) => {
      delete element.dataset.hashTargetArrival;
      delete element.dataset.hashTargetFocus;
    });

  const arrival = String(++arrivalSequence);
  target.dataset.hashTargetArrival = arrival;
  target.dataset.hashTargetFocus = "";
  target.scrollIntoView?.({ block: "center" });
  target.focus({ preventScroll: true });

  window.setTimeout(() => {
    if (target.dataset.hashTargetArrival === arrival) {
      delete target.dataset.hashTargetArrival;
    }
  }, HASH_TARGET_DURATION_MS);

  return true;
}
