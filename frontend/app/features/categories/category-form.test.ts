import { describe, expect, it } from "vitest";

import {
  categoryFieldErrors,
  firstInvalidCategoryField,
  validateCategoryDraft,
} from "./category-form";

describe("category form", () => {
  it("requires a name and enforces explicit client bounds", () => {
    expect(
      validateCategoryDraft({ name: "  ", kind: "mixed", notes: "" }),
    ).toEqual({ name: "Введите название категории." });

    const errors = validateCategoryDraft({
      name: "Н".repeat(256),
      kind: "expense",
      notes: "З".repeat(1001),
    });
    expect(errors).toEqual({
      name: "Название не должно быть длиннее 255 символов.",
      notes: "Заметка не должна быть длиннее 1000 символов.",
    });
    expect(firstInvalidCategoryField(errors)).toBe("name");
  });

  it("keeps only known server fields", () => {
    expect(
      categoryFieldErrors({
        name: ["Название уже занято."],
        request: ["Неизвестное поле."],
      }),
    ).toEqual({ name: "Название уже занято." });
  });
});
