const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export function formatIsoDate(isoDate: string): string {
  const match = ISO_DATE_PATTERN.exec(isoDate);
  if (!match) {
    throw new RangeError(`Expected ISO date YYYY-MM-DD, received: ${isoDate}`);
  }

  const year = isoDate.slice(0, 4);
  const month = isoDate.slice(5, 7);
  const day = isoDate.slice(8, 10);
  return `${day}.${month}.${year}`;
}

export function todayIsoDate(now: Date = new Date()): string {
  return [
    String(now.getFullYear()).padStart(4, "0"),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}
