import type { KeyboardEvent, PointerEvent } from "react";
import { useState } from "react";

import { Button } from "../../ui/button/button";
import { ExpansionPanel } from "../../ui/expansion-panel/expansion-panel";
import type { CoordinateControlRegion, CoordinateSpec } from "./api";
import styles from "./visual-coordinate-mapping.module.css";

type LayoutName = "first" | "middle" | "last";
type Rect = { x0: number; y0: number; x1: number; y1: number };

export function CoordinateEditor({
  disabled,
  controlRegions,
  imageUrl,
  layoutName,
  pageNumber,
  spec,
  onChange,
  onControlRegionsChange,
  onPageChange,
}: {
  disabled: boolean;
  controlRegions: CoordinateControlRegion[];
  imageUrl: string;
  layoutName: LayoutName;
  pageNumber: number;
  spec: CoordinateSpec;
  onChange: (spec: CoordinateSpec) => void;
  onControlRegionsChange: (regions: CoordinateControlRegion[]) => void;
  onPageChange: (page: number) => void;
}) {
  const [showCoordinates, setShowCoordinates] = useState(false);
  const layout = spec.layouts[layoutName];
  if (!layout) return null;
  const updateRect = (name: string, rect: Rect) => {
    const nextLayout =
      name === "sampleRow"
        ? { ...layout, sampleRow: rect }
        : { ...layout, fields: { ...layout.fields, [name]: rect } };
    onChange({
      ...spec,
      layouts: { ...spec.layouts, [layoutName]: nextLayout },
    });
  };
  const move = (name: string, rect: Rect, dx: number, dy: number) => {
    const width = rect.x1 - rect.x0;
    const height = rect.y1 - rect.y0;
    const x0 = clamp(rect.x0 + dx, 0, 1 - width);
    const y0 = clamp(
      rect.y0 + dy,
      layout.transactionTop,
      layout.transactionBottom - height,
    );
    updateRect(name, { x0, y0, x1: x0 + width, y1: y0 + height });
  };
  const updateControl = (kind: CoordinateControlRegion["kind"], rect: Rect) =>
    onControlRegionsChange(
      controlRegions.map((region) =>
        region.kind === kind ? { ...region, rect } : region,
      ),
    );
  const moveControl = (
    kind: CoordinateControlRegion["kind"],
    rect: Rect,
    dx: number,
    dy: number,
  ) => {
    const width = rect.x1 - rect.x0;
    const height = rect.y1 - rect.y0;
    const x0 = clamp(rect.x0 + dx, 0, 1 - width);
    const y0 = clamp(rect.y0 + dy, 0, 1 - height);
    updateControl(kind, { x0, y0, x1: x0 + width, y1: y0 + height });
  };
  const keyboard = (
    name: string,
    rect: Rect,
    event: KeyboardEvent<HTMLButtonElement>,
  ) => {
    const step = event.shiftKey ? 0.01 : 0.002;
    const direction: [number, number] | undefined = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    }[event.key] as [number, number] | undefined;
    if (!direction) return;
    event.preventDefault();
    if (event.altKey) {
      updateRect(name, {
        ...rect,
        x1: clamp(rect.x1 + direction[0], rect.x0 + 0.01, 1),
        y1: clamp(
          rect.y1 + direction[1],
          rect.y0 + 0.01,
          layout.transactionBottom,
        ),
      });
    } else {
      move(name, rect, direction[0], direction[1]);
    }
  };
  const pointer = (
    name: string,
    rect: Rect,
    event: PointerEvent<HTMLButtonElement>,
  ) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startY = event.clientY;
    const box = event.currentTarget.parentElement!.getBoundingClientRect();
    const target = event.currentTarget;
    target.onpointermove = (moveEvent) => {
      const dx = (moveEvent.clientX - startX) / box.width;
      const dy = (moveEvent.clientY - startY) / box.height;
      if (event.shiftKey) {
        updateRect(name, {
          ...rect,
          x1: clamp(rect.x1 + dx, rect.x0 + 0.01, 1),
          y1: clamp(rect.y1 + dy, rect.y0 + 0.01, layout.transactionBottom),
        });
      } else {
        move(name, rect, dx, dy);
      }
    };
    target.onpointerup = () => {
      target.onpointermove = null;
      target.onpointerup = null;
    };
  };
  const controlKeyboard = (
    kind: CoordinateControlRegion["kind"],
    rect: Rect,
    event: KeyboardEvent<HTMLButtonElement>,
  ) => {
    const step = event.shiftKey ? 0.01 : 0.002;
    const direction: [number, number] | undefined = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    }[event.key] as [number, number] | undefined;
    if (!direction) return;
    event.preventDefault();
    if (event.altKey) {
      updateControl(kind, {
        ...rect,
        x1: clamp(rect.x1 + direction[0], rect.x0 + 0.01, 1),
        y1: clamp(rect.y1 + direction[1], rect.y0 + 0.01, 1),
      });
    } else {
      moveControl(kind, rect, direction[0], direction[1]);
    }
  };
  const controlPointer = (
    kind: CoordinateControlRegion["kind"],
    rect: Rect,
    event: PointerEvent<HTMLButtonElement>,
  ) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startY = event.clientY;
    const box = event.currentTarget.parentElement!.getBoundingClientRect();
    const target = event.currentTarget;
    target.onpointermove = (moveEvent) => {
      const dx = (moveEvent.clientX - startX) / box.width;
      const dy = (moveEvent.clientY - startY) / box.height;
      if (event.shiftKey) {
        updateControl(kind, {
          ...rect,
          x1: clamp(rect.x1 + dx, rect.x0 + 0.01, 1),
          y1: clamp(rect.y1 + dy, rect.y0 + 0.01, 1),
        });
      } else {
        moveControl(kind, rect, dx, dy);
      }
    };
    target.onpointerup = () => {
      target.onpointermove = null;
      target.onpointerup = null;
    };
  };

  const overlays: Array<[string, Rect]> = [
    ["sampleRow", layout.sampleRow],
    ...Object.entries(layout.fields),
  ];
  const pageControls = controlRegions.filter(
    (region) => region.pageNumber === pageNumber,
  );
  return (
    <div className={styles.editorGrid}>
      <div
        className={styles.viewer}
        style={{ aspectRatio: layout.pageAspectRatio }}
      >
        <img alt={`Страница ${pageNumber} выписки`} src={imageUrl} />
        <div
          className={styles.bounds}
          style={{
            top: `${layout.transactionTop * 100}%`,
            height: `${(layout.transactionBottom - layout.transactionTop) * 100}%`,
          }}
        />
        {overlays.map(([name, rect]) => (
          <button
            aria-label={`Переместить область ${roleLabel(name)}`}
            className={styles.overlay}
            data-role={name}
            disabled={disabled}
            key={name}
            onKeyDown={(event) => keyboard(name, rect, event)}
            onPointerDown={(event) => pointer(name, rect, event)}
            style={{
              left: `${rect.x0 * 100}%`,
              top: `${rect.y0 * 100}%`,
              width: `${(rect.x1 - rect.x0) * 100}%`,
              height: `${(rect.y1 - rect.y0) * 100}%`,
            }}
            type="button"
          >
            {roleLabel(name)}
          </button>
        ))}
        {pageControls.map((region) => (
          <button
            aria-label={`Переместить контрольную область ${controlLabel(region.kind)}`}
            className={`${styles.overlay} ${styles.controlOverlay}`}
            disabled={disabled}
            key={region.kind}
            onKeyDown={(event) =>
              controlKeyboard(region.kind, region.rect, event)
            }
            onPointerDown={(event) =>
              controlPointer(region.kind, region.rect, event)
            }
            style={{
              left: `${region.rect.x0 * 100}%`,
              top: `${region.rect.y0 * 100}%`,
              width: `${(region.rect.x1 - region.rect.x0) * 100}%`,
              height: `${(region.rect.y1 - region.rect.y0) * 100}%`,
            }}
            type="button"
          >
            {controlLabel(region.kind)}
          </button>
        ))}
      </div>
      <div className={styles.controls}>
        <label>
          Верх списка{" "}
          <input
            disabled={disabled}
            max={layout.transactionBottom - 0.01}
            min={0}
            onChange={(event) =>
              onChange({
                ...spec,
                layouts: {
                  ...spec.layouts,
                  [layoutName]: {
                    ...layout,
                    transactionTop: Number(event.target.value),
                  },
                },
              })
            }
            step="0.01"
            type="range"
            value={layout.transactionTop}
          />
        </label>
        <label>
          Низ списка{" "}
          <input
            disabled={disabled}
            max={1}
            min={layout.transactionTop + 0.01}
            onChange={(event) =>
              onChange({
                ...spec,
                layouts: {
                  ...spec.layouts,
                  [layoutName]: {
                    ...layout,
                    transactionBottom: Number(event.target.value),
                  },
                },
              })
            }
            step="0.01"
            type="range"
            value={layout.transactionBottom}
          />
        </label>
        <p>
          Перетаскивайте области или используйте стрелки. Shift + drag меняет
          размер, Alt + стрелка меняет размер, Shift + стрелка — крупный шаг.
        </p>
        <p className={styles.sampleRowHint}>
          <strong>Высота строки</strong> задает верхнюю и нижнюю границы одной
          типичной операции. Рамки «Дата», «Описание» и «Сумма» указывают, где
          внутри нее искать значения.
        </p>
        <section className={styles.controlRegions}>
          <h2>Контрольные значения</h2>
          <p>
            Добавьте рамку и поместите её только на число, без подписи. Эти
            области относятся к документу и не сохраняются в шаблоне.
          </p>
          {CONTROL_KINDS.map((kind) => {
            const region = controlRegions.find((item) => item.kind === kind);
            return (
              <div className={styles.controlRegionRow} key={kind}>
                <strong>{controlLabel(kind)}</strong>
                {region ? (
                  <>
                    <span>Страница {region.pageNumber}</span>
                    {region.pageNumber !== pageNumber ? (
                      <button
                        disabled={disabled}
                        onClick={() => onPageChange(region.pageNumber)}
                        type="button"
                      >
                        Показать
                      </button>
                    ) : null}
                    <button
                      disabled={disabled}
                      onClick={() =>
                        onControlRegionsChange(
                          controlRegions.filter((item) => item.kind !== kind),
                        )
                      }
                      type="button"
                    >
                      Удалить
                    </button>
                  </>
                ) : (
                  <button
                    disabled={disabled}
                    onClick={() => {
                      const y0 = Math.min(
                        0.88,
                        0.04 + pageControls.length * 0.07,
                      );
                      onControlRegionsChange([
                        ...controlRegions,
                        {
                          kind,
                          pageNumber,
                          rect: { x0: 0.65, y0, x1: 0.95, y1: y0 + 0.05 },
                        },
                      ]);
                    }}
                    type="button"
                  >
                    Добавить на этой странице
                  </button>
                )}
              </div>
            );
          })}
        </section>
        {!showCoordinates ? (
          <Button
            disabled={disabled}
            onClick={() => setShowCoordinates(true)}
            tone="secondary"
            type="button"
          >
            Показать точные координаты
          </Button>
        ) : null}
        <ExpansionPanel
          id="visual-coordinate-values"
          isOpen={showCoordinates}
          onClose={() => setShowCoordinates(false)}
          title="Точные координаты областей"
        >
          <p className={styles.coordinateHint}>
            Используйте числовые значения только для точной корректировки рамок.
          </p>
          {overlays.map(([name, rect]) => (
            <fieldset key={name}>
              <legend>{roleLabel(name)}</legend>
              {(["x0", "y0", "x1", "y1"] as const).map((key) => (
                <label key={key}>
                  {key}
                  <input
                    disabled={disabled}
                    max={1}
                    min={0}
                    onChange={(event) =>
                      updateRect(name, {
                        ...rect,
                        [key]: Number(event.target.value),
                      })
                    }
                    step="0.01"
                    type="number"
                    value={rect[key]}
                  />
                </label>
              ))}
            </fieldset>
          ))}
          {pageControls.map((region) => (
            <fieldset key={region.kind}>
              <legend>{controlLabel(region.kind)}</legend>
              {(["x0", "y0", "x1", "y1"] as const).map((key) => (
                <label key={key}>
                  {key}
                  <input
                    disabled={disabled}
                    max={1}
                    min={0}
                    onChange={(event) =>
                      updateControl(region.kind, {
                        ...region.rect,
                        [key]: Number(event.target.value),
                      })
                    }
                    step="0.01"
                    type="number"
                    value={region.rect[key]}
                  />
                </label>
              ))}
            </fieldset>
          ))}
        </ExpansionPanel>
      </div>
    </div>
  );
}

const CONTROL_KINDS: CoordinateControlRegion["kind"][] = [
  "opening_balance",
  "closing_balance",
  "total_inflow",
  "total_outflow",
];

function controlLabel(kind: CoordinateControlRegion["kind"]) {
  return {
    opening_balance: "Входящий остаток",
    closing_balance: "Исходящий остаток",
    total_inflow: "Итого поступлений",
    total_outflow: "Итого списаний",
  }[kind];
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}
function roleLabel(role: string) {
  return (
    (
      {
        sampleRow: "Высота строки",
        operation_date: "Дата",
        description: "Описание",
        amount: "Сумма",
        debit: "Списание",
        credit: "Поступление",
        posting_date: "Дата проводки",
        currency: "Валюта",
        balance: "Остаток",
      } as Record<string, string>
    )[role] ?? role
  );
}
