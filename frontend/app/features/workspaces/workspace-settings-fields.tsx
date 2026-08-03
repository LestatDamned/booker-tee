import type { FormEvent, RefObject } from "react";

import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import {
  FormActions,
  FormGrid,
  FormGridItem,
} from "../../ui/field/form-layout";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type {
  WorkspaceSettingsDraft,
  WorkspaceSettingsDto,
} from "./api/workspace-settings-api";
import type { WorkspaceFieldErrors } from "./workspace-form";
import { workspaceTypeLabel } from "./workspace-labels";
import styles from "./workspace-settings-page.module.css";

export function WorkspaceSettingsForm({
  currencyOptions,
  dirty,
  draft,
  fieldErrors,
  nameRef,
  onChange,
  onReset,
  onSubmit,
  pending,
  typeOptions,
}: {
  currencyOptions: WorkspaceSettingsDto["currencyOptions"];
  dirty: boolean;
  draft: WorkspaceSettingsDraft;
  fieldErrors: WorkspaceFieldErrors;
  nameRef: RefObject<HTMLInputElement | null>;
  onChange: <FieldName extends keyof WorkspaceSettingsDraft>(
    field: FieldName,
    value: WorkspaceSettingsDraft[FieldName],
  ) => void;
  onReset: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  typeOptions: WorkspaceSettingsDto["workspaceTypeOptions"];
}) {
  const summaryErrors = Object.entries(fieldErrors).flatMap(
    ([field, message]) =>
      message
        ? [
            {
              fieldId: `workspace-settings-${field}`,
              label: settingsFieldLabel(field),
              message,
            },
          ]
        : [],
  );
  return (
    <form className={styles.form} noValidate onSubmit={onSubmit}>
      {summaryErrors.length ? (
        <FormErrorSummary
          errors={summaryErrors}
          message="Проверьте настройки и повторите сохранение."
        />
      ) : null}
      <FormGrid columns="two">
        <div>
          <Field
            error={fieldErrors.name}
            errorId="workspace-settings-name-error"
            htmlFor="workspace-settings-name"
            label="Название"
            required
          >
            <input
              ref={nameRef}
              id="workspace-settings-name"
              aria-describedby={
                fieldErrors.name ? "workspace-settings-name-error" : undefined
              }
              aria-invalid={Boolean(fieldErrors.name)}
              autoComplete="organization"
              disabled={pending}
              maxLength={255}
              required
              value={draft.name}
              onChange={(event) => onChange("name", event.target.value)}
            />
          </Field>
        </div>
        <div>
          <Field
            error={fieldErrors.workspaceType}
            errorId="workspace-settings-workspaceType-error"
            hint="Тип помогает обозначить назначение пространства и не меняет права участников."
            hintId="workspace-settings-workspaceType-hint"
            htmlFor="workspace-settings-workspaceType"
            label="Тип"
            required
          >
            <select
              id="workspace-settings-workspaceType"
              aria-describedby={
                fieldErrors.workspaceType
                  ? "workspace-settings-workspaceType-error"
                  : "workspace-settings-workspaceType-hint"
              }
              aria-invalid={Boolean(fieldErrors.workspaceType)}
              disabled={pending}
              required
              value={draft.workspaceType}
              onChange={(event) =>
                onChange(
                  "workspaceType",
                  event.target.value as WorkspaceSettingsDraft["workspaceType"],
                )
              }
            >
              {typeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <FormGridItem span="full">
          <Field
            error={fieldErrors.defaultCurrency}
            errorId="workspace-settings-defaultCurrency-error"
            htmlFor="workspace-settings-defaultCurrency"
            label="Основная валюта"
            required
          >
            <select
              id="workspace-settings-defaultCurrency"
              aria-describedby={
                fieldErrors.defaultCurrency
                  ? "workspace-settings-defaultCurrency-error"
                  : "workspace-currency-impact"
              }
              aria-invalid={Boolean(fieldErrors.defaultCurrency)}
              disabled={pending}
              required
              value={draft.defaultCurrency}
              onChange={(event) =>
                onChange("defaultCurrency", event.target.value)
              }
            >
              {currencyOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <InlineNotice
            id="workspace-currency-impact"
            title="Ранее сохранённые данные не изменятся"
            tone="information"
          >
            Основная валюта используется по умолчанию для новых счетов и
            операций. Существующие суммы сохранят исходные валюты.
          </InlineNotice>
        </FormGridItem>
      </FormGrid>
      <FormActions layout="split">
        <Button disabled={!dirty || pending} onClick={onReset} tone="secondary">
          Сбросить
        </Button>
        <Button
          disabled={!dirty || pending}
          icon="check"
          isLoading={pending}
          tone="primary"
          type="submit"
        >
          {pending ? "Сохраняем…" : "Сохранить"}
        </Button>
      </FormActions>
    </form>
  );
}

export function WorkspaceReadOnlySettings({
  settings,
}: {
  settings: WorkspaceSettingsDto;
}) {
  const workspace = settings.workspace;
  return (
    <div className={styles.readOnlyBlock}>
      <InlineNotice title="Изменение доступно владельцу" tone="neutral">
        Вы можете просматривать параметры, но изменять их может только владелец.
      </InlineNotice>
      <dl className={styles.facts}>
        <Fact label="Название" value={workspace.name} />
        <Fact label="Тип" value={workspaceTypeLabel(workspace.type)} />
        <Fact label="Основная валюта" value={workspace.defaultCurrency} />
      </dl>
    </div>
  );
}

export function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function settingsFieldLabel(field: string) {
  const labels: Record<string, string> = {
    defaultCurrency: "Основная валюта",
    name: "Название",
    workspaceType: "Тип",
  };
  return labels[field] ?? field;
}
