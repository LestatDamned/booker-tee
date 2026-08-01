import { describe, expect, it } from "vitest";

import type { PropertySummaryDto } from "./api/properties-api";
import {
  propertyListQuery,
  propertyListUrl,
  propertyMatchesSearch,
} from "./property-list-query";

describe("property list query", () => {
  it("normalizes URL state and falls back to active", () => {
    expect(
      propertyListQuery(
        "?view=unexpected&search=%20%D0%94%D0%BE%D0%BC%20%20%D0%9C%D0%B8%D1%80%D0%B0%20",
      ),
    ).toEqual({
      view: "active",
      search: "Дом Мира",
    });
    expect(propertyListUrl("archived", " Старый   проект ")).toBe(
      "?view=archived&search=%D0%A1%D1%82%D0%B0%D1%80%D1%8B%D0%B9+%D0%BF%D1%80%D0%BE%D0%B5%D0%BA%D1%82",
    );
  });

  it("searches name, short name and address case-insensitively", () => {
    expect(propertyMatchesSearch(property, "кВаРт")).toBe(true);
    expect(propertyMatchesSearch(property, "ДОМ")).toBe(true);
    expect(propertyMatchesSearch(property, "МИРА")).toBe(true);
    expect(propertyMatchesSearch(property, "офис")).toBe(false);
  });
});

const property: PropertySummaryDto = {
  id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
  name: "Квартира",
  shortName: "Дом",
  address: "Красноярск, ул. Мира, 1",
  status: "active",
  archivedAt: null,
  updatedAt: "2026-08-01T08:30:00Z",
  capabilities: { canUpdate: true, canArchive: true, canRestore: false },
};
