import { useState } from "react";

import type { PropertySummaryDto } from "./api/properties-api";

export function usePropertyCollection(initial: PropertySummaryDto[]) {
  const [properties, setProperties] = useState(initial);

  function commitCreated(property: PropertySummaryDto) {
    setProperties((current) => insertCommittedProperty(current, property));
  }

  function replaceCommitted(property: PropertySummaryDto) {
    setProperties((current) =>
      current.map((item) => (item.id === property.id ? property : item)),
    );
  }

  return {
    commitCreated,
    properties,
    replaceAll: setProperties,
    replaceCommitted,
  };
}

function insertCommittedProperty(
  properties: PropertySummaryDto[],
  property: PropertySummaryDto,
): PropertySummaryDto[] {
  const withoutCommitted = properties.filter((item) => item.id !== property.id);
  const firstArchived = withoutCommitted.findIndex(
    (item) => item.status === "archived",
  );
  if (firstArchived === -1) return [...withoutCommitted, property];
  return [
    ...withoutCommitted.slice(0, firstArchived),
    property,
    ...withoutCommitted.slice(firstArchived),
  ];
}
