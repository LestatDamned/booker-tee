import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CoordinateSpec } from "./api";
import { CoordinateEditor } from "./editor";
import { completeLayouts, withAmountMode, withOptionalRole } from "./page";

describe("CoordinateEditor", () => {
  it("moves a normalized field with the keyboard without depending on image size", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const spec = coordinateSpec();
    render(
      <CoordinateEditor
        disabled={false}
        imageUrl="blob:coordinate-page"
        layoutName="first"
        onChange={onChange}
        pageNumber={1}
        spec={spec}
      />,
    );

    const date = screen.getByRole("button", {
      name: "Переместить область Дата",
    });
    date.focus();
    await user.keyboard("{ArrowRight}");

    const changed = onChange.mock.calls[0]?.[0] as CoordinateSpec;
    expect(changed.layouts.first?.fields.operation_date?.x0).toBeCloseTo(0.102);
    expect(changed.layouts.first?.fields.operation_date).toMatchObject({
      y0: 0.2,
      x1: 0.202,
      y1: 0.3,
    });
    expect(screen.getByAltText("Страница 1 выписки")).toHaveAttribute(
      "src",
      "blob:coordinate-page",
    );
    expect(
      screen.getByRole("button", {
        name: "Переместить область Высота строки",
      }),
    ).toHaveAttribute("data-role", "sampleRow");
    expect(
      screen.getByText(/рамки «Дата», «Описание» и «Сумма»/i),
    ).toBeVisible();
  });

  it("moves a normalized field with pointer coordinates", () => {
    const onChange = vi.fn();
    render(
      <CoordinateEditor
        disabled={false}
        imageUrl="blob:coordinate-page"
        layoutName="first"
        onChange={onChange}
        pageNumber={1}
        spec={coordinateSpec()}
      />,
    );
    const date = screen.getByRole("button", {
      name: "Переместить область Дата",
    });
    Object.defineProperty(date, "setPointerCapture", { value: vi.fn() });
    vi.spyOn(date.parentElement!, "getBoundingClientRect").mockReturnValue({
      width: 1000,
      height: 1000,
    } as DOMRect);

    fireEvent.pointerDown(date, { pointerId: 1, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(date, { pointerId: 1, clientX: 150, clientY: 120 });

    const changed = onChange.mock.calls[0]?.[0] as CoordinateSpec;
    expect(changed.layouts.first?.fields.operation_date?.x0).toBeCloseTo(0.15);
    expect(changed.layouts.first?.fields.operation_date?.y0).toBeCloseTo(0.22);
  });
});

describe("coordinate field roles", () => {
  it("switches amount to debit and credit and adds optional roles", () => {
    const split = withAmountMode(coordinateSpec(), true);
    expect(split.layouts.first?.fields).not.toHaveProperty("amount");
    expect(split.layouts.first?.fields).toHaveProperty("debit");
    expect(split.layouts.first?.fields).toHaveProperty("credit");

    const withPostingDate = withOptionalRole(split, "posting_date", true);
    expect(withPostingDate.layouts.first?.fields).toHaveProperty(
      "posting_date",
    );
  });

  it("expands a single-page template into required multi-page layouts", () => {
    const completed = completeLayouts(coordinateSpec(), {
      documentId: "doc",
      filename: "statement.pdf",
      pageCount: 3,
      pages: [
        {
          pageNumber: 1,
          width: 600,
          height: 800,
          aspectRatio: 0.75,
          hasTextLayer: true,
        },
        {
          pageNumber: 2,
          width: 700,
          height: 800,
          aspectRatio: 0.875,
          hasTextLayer: true,
        },
        {
          pageNumber: 3,
          width: 800,
          height: 800,
          aspectRatio: 1,
          hasTextLayer: true,
        },
      ],
      defaultCurrency: "RUB",
      capability: { allowed: true, blockingReasonCodes: [] },
      templates: [],
    });

    expect(Object.keys(completed.layouts)).toEqual(["first", "middle", "last"]);
    expect(completed.layouts.middle?.pageAspectRatio).toBe(0.875);
    expect(completed.layouts.last?.pageAspectRatio).toBe(1);
  });

  it("preserves aspect ratios recorded by existing template layouts", () => {
    const spec = coordinateSpec();
    spec.layouts.last = {
      ...spec.layouts.first!,
      pageAspectRatio: 0.6,
    };
    const completed = completeLayouts(spec, {
      documentId: "doc",
      filename: "statement.pdf",
      pageCount: 3,
      pages: [
        {
          pageNumber: 1,
          width: 800,
          height: 800,
          aspectRatio: 1,
          hasTextLayer: true,
        },
        {
          pageNumber: 2,
          width: 700,
          height: 800,
          aspectRatio: 0.875,
          hasTextLayer: true,
        },
        {
          pageNumber: 3,
          width: 800,
          height: 800,
          aspectRatio: 1,
          hasTextLayer: true,
        },
      ],
      defaultCurrency: "RUB",
      capability: { allowed: true, blockingReasonCodes: [] },
      templates: [],
    });

    expect(completed.layouts.first?.pageAspectRatio).toBe(0.75);
    expect(completed.layouts.middle?.pageAspectRatio).toBe(0.875);
    expect(completed.layouts.last?.pageAspectRatio).toBe(0.6);
  });
});

function coordinateSpec(): CoordinateSpec {
  return {
    version: 1,
    defaultCurrency: "RUB",
    unsignedAmountDirection: "require_sign",
    layouts: {
      first: {
        pageAspectRatio: 0.75,
        transactionTop: 0.1,
        transactionBottom: 0.9,
        sampleRow: { x0: 0.05, y0: 0.2, x1: 0.95, y1: 0.3 },
        fields: {
          operation_date: { x0: 0.1, y0: 0.2, x1: 0.2, y1: 0.3 },
          description: { x0: 0.25, y0: 0.2, x1: 0.65, y1: 0.3 },
          amount: { x0: 0.75, y0: 0.2, x1: 0.9, y1: 0.3 },
        },
      },
    },
  };
}
