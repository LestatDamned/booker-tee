import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { BackLink } from "../../ui/back-link/back-link";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { Fieldset } from "../../ui/field/fieldset";
import type {
  CoordinateOverview,
  CoordinatePreview,
  CoordinateSpec,
} from "./api";
import {
  importCoordinates,
  loadCoordinatePageImage,
  previewCoordinates,
} from "./api";
import { CoordinateEditor } from "./editor";
import styles from "./visual-coordinate-mapping.module.css";

type LayoutName = "first" | "middle" | "last";

export function VisualCoordinateMappingPage({
  overview,
  session,
}: {
  overview: CoordinateOverview;
  session: SessionDto;
}) {
  const navigate = useNavigate();
  const [spec, setSpec] = useState(() => initialSpec(overview));
  const [layout, setLayout] = useState<LayoutName>("first");
  const [preview, setPreview] = useState<{
    fingerprint: string;
    value: CoordinatePreview;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [image, setImage] = useState<{ page: number; url: string } | null>(
    null,
  );
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageRetry, setImageRetry] = useState(0);
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null);
  const fingerprint = spec ? JSON.stringify(spec) : "";
  const stale = preview !== null && preview.fingerprint !== fingerprint;
  const activePage =
    layout === "first" ? 1 : layout === "last" ? overview.pageCount : 2;
  const canLoadImage =
    overview.capability.allowed && spec !== null && overview.pages.length > 0;

  useEffect(() => {
    if (!canLoadImage) return;
    const controller = new AbortController();
    let objectUrl: string | null = null;
    void loadCoordinatePageImage(
      overview.documentId,
      activePage,
      controller.signal,
    )
      .then((result) => {
        if (redirectIfUnauthenticated(result)) return;
        if (result.status !== "success") {
          setImageError(result.message);
          return;
        }
        objectUrl = URL.createObjectURL(result.value);
        setImage({ page: activePage, url: objectUrl });
      })
      .catch((loadError: unknown) => {
        if (!(
          loadError instanceof DOMException && loadError.name === "AbortError"
        )) {
          setImageError("Не удалось загрузить изображение страницы.");
        }
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [activePage, canLoadImage, imageRetry, overview.documentId]);

  const change = (next: CoordinateSpec) => {
    setSpec(next);
    attempt.current = null;
  };
  const runPreview = async () => {
    if (!spec) return;
    setPending(true);
    setError(null);
    const result = await previewCoordinates(
      overview.documentId,
      spec,
      session.csrfToken,
    );
    setPending(false);
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "success")
      setPreview({ fingerprint, value: result.value });
    else
      setError(
        "message" in result
          ? result.message
          : "Не удалось обновить предпросмотр.",
      );
  };
  const runImport = async () => {
    if (!spec || !session.capabilities.canManageImports) return;
    const intent = JSON.stringify([fingerprint, templateName.trim()]);
    const current =
      attempt.current?.fingerprint === intent
        ? attempt.current
        : { fingerprint: intent, key: crypto.randomUUID() };
    attempt.current = current;
    setPending(true);
    setError(null);
    const result = await importCoordinates(
      overview.documentId,
      spec,
      templateName.trim() || null,
      session.csrfToken,
      current.key,
    );
    setPending(false);
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "success")
      void navigate(
        `/imports/documents/${result.value.reviewTarget.documentId}/review`,
      );
    else
      setError(
        "message" in result
          ? result.message
          : "Не удалось импортировать строки.",
      );
  };

  return (
    <AppShell session={session}>
      <main className={styles.page}>
        <nav
          aria-label="Режим настройки импорта"
          className={styles.pageNavigation}
        >
          <BackLink to={`/imports/documents/${overview.documentId}`}>
            К документу
          </BackLink>
          <RouterButtonLink
            to={`/imports/documents/${overview.documentId}/mapping`}
          >
            Настройка колонок
          </RouterButtonLink>
        </nav>
        <header>
          <p className={styles.eyebrow}>Визуальная настройка PDF</p>
          <h1>{overview.filename}</h1>
          <p>
            Выберите одну типичную операцию и отметьте в ней нужные поля. По
            этому примеру система распознает остальные строки выписки.
          </p>
        </header>
        {!overview.capability.allowed || !spec ? (
          <section role="status" className={styles.notice}>
            <h2>Визуальная настройка недоступна</h2>
            <p>{overview.capability.blockingReasonCodes.join(", ")}</p>
          </section>
        ) : (
          <>
            <nav aria-label="Layouts страниц" className={styles.tabs}>
              {availableLayouts(overview.pageCount).map((name) => (
                <button
                  aria-pressed={layout === name}
                  key={name}
                  onClick={() => {
                    if (name !== layout) {
                      setImage(null);
                      setImageError(null);
                    }
                    setLayout(name);
                  }}
                  type="button"
                >
                  {layoutLabel(name)}
                </button>
              ))}
            </nav>
            <section
              className={styles.settings}
              aria-labelledby="coordinate-settings-title"
            >
              <div className={styles.settingsHeader}>
                <h2 id="coordinate-settings-title">Настройки распознавания</h2>
                <p>
                  Сначала укажите структуру выписки, затем разметьте строку
                  ниже.
                </p>
              </div>
              <div className={styles.settingsGrid}>
                <div className={styles.settingsGroup}>
                  <h3>Сумма</h3>
                  <Field htmlFor="amount-mode" label="Формат суммы">
                    <select
                      disabled={pending}
                      id="amount-mode"
                      onChange={(event) =>
                        change(
                          withAmountMode(spec, event.target.value === "split"),
                        )
                      }
                      value={
                        spec.layouts.first?.fields.amount ? "amount" : "split"
                      }
                    >
                      <option value="amount">Одна сумма</option>
                      <option value="split">Списание и поступление</option>
                    </select>
                  </Field>
                  <Field
                    htmlFor="unsigned-amount-direction"
                    label="Если сумма без знака"
                  >
                    <select
                      disabled={pending}
                      id="unsigned-amount-direction"
                      onChange={(event) =>
                        change({
                          ...spec,
                          unsignedAmountDirection: event.target
                            .value as CoordinateSpec["unsignedAmountDirection"],
                        })
                      }
                      value={spec.unsignedAmountDirection}
                    >
                      <option value="require_sign">Требовать знак</option>
                      <option value="expense">Списание</option>
                      <option value="income">Поступление</option>
                    </select>
                  </Field>
                </div>
                <div className={styles.settingsGroup}>
                  <Fieldset
                    hint="Включите только те колонки, которые есть в выписке."
                    legend="Дополнительные поля"
                  >
                    <div className={styles.checkboxList}>
                      {(["posting_date", "currency", "balance"] as const).map(
                        (role) => (
                          <label className={styles.checkboxOption} key={role}>
                            <input
                              checked={
                                role in (spec.layouts.first?.fields ?? {})
                              }
                              disabled={pending}
                              onChange={(event) =>
                                change(
                                  withOptionalRole(
                                    spec,
                                    role,
                                    event.target.checked,
                                  ),
                                )
                              }
                              type="checkbox"
                            />
                            <span>
                              {role === "posting_date"
                                ? "Дата проводки"
                                : role === "currency"
                                  ? "Валюта"
                                  : "Остаток"}
                            </span>
                          </label>
                        ),
                      )}
                    </div>
                  </Fieldset>
                </div>
                <div className={styles.settingsGroup}>
                  <h3>Шаблон</h3>
                  <Field htmlFor="coordinate-template" label="Готовый шаблон">
                    <select
                      disabled={pending}
                      id="coordinate-template"
                      onChange={(event) => {
                        setSelectedTemplateId(event.target.value);
                        const selected = overview.templates.find(
                          (item) => item.id === event.target.value,
                        );
                        const next = selected
                          ? completeLayouts(selected.spec, overview)
                          : initialSpec(overview);
                        if (next) change(next);
                        setError(null);
                        if (layout !== "first") {
                          setImage(null);
                          setImageError(null);
                        }
                        setLayout("first");
                      }}
                      value={selectedTemplateId}
                    >
                      <option value="">Не выбран</option>
                      {overview.templates.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field
                    hint="Оставьте пустым, если шаблон сохранять не нужно."
                    htmlFor="new-template-name"
                    label="Название нового шаблона"
                  >
                    <input
                      disabled={pending}
                      id="new-template-name"
                      maxLength={255}
                      onChange={(event) => {
                        setTemplateName(event.target.value);
                        attempt.current = null;
                      }}
                      placeholder="Например, Основная выписка"
                      value={templateName}
                    />
                  </Field>
                </div>
              </div>
            </section>
            {image?.page === activePage ? (
              <CoordinateEditor
                disabled={pending}
                imageUrl={image.url}
                layoutName={layout}
                onChange={change}
                pageNumber={activePage}
                spec={spec}
              />
            ) : imageError ? (
              <section role="alert" className={styles.notice}>
                <p>{imageError}</p>
                <Button
                  disabled={pending}
                  onClick={() => {
                    setImageError(null);
                    setImageRetry((value) => value + 1);
                  }}
                  tone="secondary"
                  type="button"
                >
                  Повторить загрузку страницы
                </Button>
              </section>
            ) : (
              <p role="status">Загружаем страницу PDF…</p>
            )}
            {error ? (
              <p role="alert" className={styles.error}>
                {error}
              </p>
            ) : null}
            {preview ? (
              <section aria-live="polite" className={styles.preview}>
                <h2>
                  {stale
                    ? "Предпросмотр устарел"
                    : `${preview.value.validRowCount} корректных строк`}
                </h2>
                <p>
                  Всего: {preview.value.totalRowCount}; требуют проверки:{" "}
                  {preview.value.invalidRowCount}.
                </p>
                {preview.value.warnings.length ? (
                  <ul aria-label="Предупреждения предпросмотра">
                    {preview.value.warnings.map((warning, index) => (
                      <li key={`${warning.code}:${index}`}>
                        <strong>{warningLabel(warning.code)}</strong>
                        {` — ${warning.severity === "error" ? "ошибка" : "предупреждение"}`}
                        {warning.affectedRowCount == null
                          ? null
                          : `; затронуто: ${warning.affectedRowCount}`}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <ol>
                  {preview.value.rows.map((row) => (
                    <li key={`${row.pageNumber}:${row.sourceRowNumber}`}>
                      <strong>
                        {row.operationDateRaw || "Дата не распознана"}
                      </strong>{" "}
                      · {row.description || "Нет описания"} ·{" "}
                      {(row.amount ?? row.amountRaw) || "Нет суммы"}
                      {row.errors.length ? (
                        <span> — {row.errors.join("; ")}</span>
                      ) : null}
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
            <footer className={styles.actions}>
              <Button
                disabled={pending}
                onClick={runPreview}
                tone="secondary"
                type="button"
              >
                Обновить предпросмотр
              </Button>
              <Button
                disabled={
                  pending ||
                  !session.capabilities.canManageImports ||
                  !preview?.value.canImport ||
                  stale
                }
                onClick={runImport}
                tone="primary"
                type="button"
              >
                Импортировать в проверку
              </Button>
            </footer>
          </>
        )}
      </main>
    </AppShell>
  );
}

export function initialSpec(
  overview: CoordinateOverview,
): CoordinateSpec | null {
  if (
    !overview.capability.allowed ||
    overview.pageCount < 1 ||
    overview.pages.length < overview.pageCount
  )
    return null;
  const names = availableLayouts(overview.pageCount);
  return {
    version: 1,
    defaultCurrency: overview.defaultCurrency,
    unsignedAmountDirection: "require_sign",
    layouts: Object.fromEntries(
      names.map((name) => {
        const page =
          overview.pages[
            name === "first"
              ? 0
              : name === "last"
                ? overview.pages.length - 1
                : 1
          ]!;
        return [
          name,
          {
            pageAspectRatio: page.aspectRatio,
            transactionTop: 0.12,
            transactionBottom: 0.92,
            sampleRow: { x0: 0.04, y0: 0.2, x1: 0.96, y1: 0.26 },
            fields: {
              operation_date: { x0: 0.04, y0: 0.2, x1: 0.2, y1: 0.26 },
              description: { x0: 0.22, y0: 0.2, x1: 0.68, y1: 0.26 },
              amount: { x0: 0.72, y0: 0.2, x1: 0.96, y1: 0.26 },
            },
          },
        ];
      }),
    ),
  };
}
export function completeLayouts(
  spec: CoordinateSpec,
  overview: CoordinateOverview,
): CoordinateSpec {
  const source = spec.layouts.first ?? Object.values(spec.layouts)[0];
  if (!source) return initialSpec(overview) ?? spec;
  return {
    ...spec,
    layouts: Object.fromEntries(
      availableLayouts(overview.pageCount).map((name) => {
        const existing = spec.layouts[name];
        if (existing) return [name, existing];
        const pageIndex =
          name === "first"
            ? 0
            : name === "last"
              ? overview.pages.length - 1
              : 1;
        return [
          name,
          {
            ...source,
            pageAspectRatio: overview.pages[pageIndex]!.aspectRatio,
          },
        ];
      }),
    ),
  };
}

export function withAmountMode(
  spec: CoordinateSpec,
  split: boolean,
): CoordinateSpec {
  const roles = Object.keys(spec.layouts.first?.fields ?? {}).filter(
    (role) => !["amount", "debit", "credit"].includes(role),
  );
  roles.push(...(split ? ["debit", "credit"] : ["amount"]));
  return withRoles(spec, roles);
}

export function withOptionalRole(
  spec: CoordinateSpec,
  role: "posting_date" | "currency" | "balance",
  enabled: boolean,
): CoordinateSpec {
  const roles = Object.keys(spec.layouts.first?.fields ?? {}).filter(
    (item) => item !== role,
  );
  if (enabled) roles.push(role);
  return withRoles(spec, roles);
}

function withRoles(spec: CoordinateSpec, roles: string[]): CoordinateSpec {
  const gap = 0.01;
  const width = (0.92 - gap * (roles.length - 1)) / roles.length;
  return {
    ...spec,
    layouts: Object.fromEntries(
      Object.entries(spec.layouts).map(([name, layout]) => [
        name,
        {
          ...layout,
          fields: Object.fromEntries(
            roles.map((role, index) => [
              role,
              {
                x0: 0.04 + index * (width + gap),
                x1: 0.04 + index * (width + gap) + width,
                y0: layout.sampleRow.y0,
                y1: layout.sampleRow.y1,
              },
            ]),
          ),
        },
      ]),
    ),
  };
}
function availableLayouts(pageCount: number): LayoutName[] {
  return pageCount === 1
    ? ["first"]
    : pageCount === 2
      ? ["first", "last"]
      : ["first", "middle", "last"];
}
function layoutLabel(name: LayoutName) {
  return name === "first"
    ? "Первая"
    : name === "middle"
      ? "Промежуточная"
      : "Последняя";
}
function warningLabel(code: string) {
  return (
    {
      coordinate_date_anchors_missing: "На странице не найдены строки с датами",
      coordinate_date_candidates_unanchored:
        "Часть строк не распознана как строки с датами",
      high_error_rate: "Много строк требуют проверки",
      unsigned_amount_direction_required:
        "Для сумм без знака требуется направление",
      no_valid_rows: "Нет корректных строк",
    }[code] ?? code
  );
}
