import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { BackLink } from "../../ui/back-link/back-link";
import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { Icon } from "../../ui/icon/icon";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import type { ImportUploadReferenceDto } from "./api/import-upload-api";
import { uploadImportDocument } from "./api/import-upload-api";
import styles from "./import-upload-page.module.css";

type FieldErrors = {
  accountId?: string | undefined;
  statement?: string | undefined;
};

export function ImportUploadPage({
  reference,
  session,
}: {
  reference: ImportUploadReferenceDto;
  session: SessionDto;
}) {
  const navigate = useNavigate();
  const accountRef = useRef<HTMLSelectElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [accountId, setAccountId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const resetCommandIdentity = () => {
    idempotencyKey.current = crypto.randomUUID();
    setSubmitError(null);
  };

  const selectFile = (nextFile: File | null) => {
    setFile(nextFile);
    setFieldErrors((current) => ({ ...current, statement: undefined }));
    resetCommandIdentity();
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validateDraft(reference, accountId, file);
    setFieldErrors(nextErrors);
    setSubmitError(null);
    if (nextErrors.accountId || nextErrors.statement || !file) {
      (nextErrors.accountId ? accountRef.current : fileRef.current)?.focus();
      return;
    }

    setPending(true);
    const result = await uploadImportDocument({
      accountId,
      csrfToken: session.csrfToken,
      file,
      idempotencyKey: idempotencyKey.current,
    });
    setPending(false);
    if (result.status === "success") {
      navigate(`/imports/documents/${result.document.id}`);
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/imports/upload");
      return;
    }
    const serverErrors = {
      accountId: result.fieldErrors.accountId?.[0],
      statement: result.fieldErrors.statement?.[0],
    };
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    if (serverErrors.accountId) accountRef.current?.focus();
    else if (serverErrors.statement) fileRef.current?.focus();
  };

  const summaryErrors: FormErrorSummaryItem[] = [
    ...(fieldErrors.accountId
      ? [
          {
            fieldId: "upload-account",
            label: "Счёт",
            message: fieldErrors.accountId,
          },
        ]
      : []),
    ...(fieldErrors.statement
      ? [
          {
            fieldId: "upload-file",
            label: "Файл",
            message: fieldErrors.statement,
          },
        ]
      : []),
  ];

  return (
    <AppShell session={session}>
      <PageFrame className={styles.page} spacing="none">
        <BackLink to="/imports">Все импорты</BackLink>

        <WorkbenchSurface
          aria-busy={pending}
          aria-labelledby="import-upload-title"
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <header className={styles.header}>
              <div>
                <p className={styles.eyebrow}>Импорт банковской выписки</p>
                <h1 id="import-upload-title">Загрузить выписку</h1>
                <p>
                  Привяжите файл к счёту — так строки сразу получат правильную
                  валюту и контекст проверки.
                </p>
              </div>
              <div
                className={styles.headerFacts}
                aria-label="Ограничения загрузки"
              >
                <span>PDF · XLSX</span>
                <span>до {formatFileSize(reference.maxFileSizeBytes)}</span>
              </div>
            </header>
          </WorkbenchHeader>

          {!reference.canUpload ? (
            <section className={styles.statePanel}>
              <Icon name="information" size={24} />
              <div>
                <h2>Загрузка недоступна</h2>
                <p>
                  У вас есть доступ к истории импортов, но нет права добавлять
                  новые документы.
                </p>
              </div>
            </section>
          ) : reference.accounts.length === 0 ? (
            <section className={styles.statePanel}>
              <Icon name="accounts" size={24} />
              <div>
                <h2>Сначала создайте счёт</h2>
                <p>Каждая выписка должна быть привязана к активному счёту.</p>
                <a className={styles.secondaryLink} href="/app/accounts">
                  Перейти к счетам
                </a>
              </div>
            </section>
          ) : (
            <div className={styles.contentGrid}>
              <form className={styles.form} noValidate onSubmit={submit}>
                {(submitError || summaryErrors.length > 0) && (
                  <FormErrorSummary
                    errors={summaryErrors}
                    message={
                      submitError ??
                      "Выберите счёт и подходящий файл банковской выписки."
                    }
                  />
                )}

                <Field
                  error={fieldErrors.accountId}
                  errorId="upload-account-error"
                  hint="Выберите счёт, движения которого содержит выписка."
                  htmlFor="upload-account"
                  label="Счёт выписки"
                  required
                >
                  <select
                    ref={accountRef}
                    id="upload-account"
                    aria-describedby={
                      fieldErrors.accountId ? "upload-account-error" : undefined
                    }
                    aria-invalid={Boolean(fieldErrors.accountId)}
                    disabled={pending}
                    name="accountId"
                    required
                    value={accountId}
                    onChange={(event) => {
                      setAccountId(event.target.value);
                      setFieldErrors((current) => ({
                        ...current,
                        accountId: undefined,
                      }));
                      resetCommandIdentity();
                    }}
                  >
                    <option value="">Выберите счёт</option>
                    {reference.accounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name} · {account.currency}
                        {account.bankName ? ` · ${account.bankName}` : ""}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field
                  error={fieldErrors.statement}
                  errorId="upload-file-error"
                  hint={`Поддерживаются ${reference.acceptedExtensions.join(", ").toUpperCase()}. Максимальный размер — ${formatFileSize(reference.maxFileSizeBytes)}.`}
                  htmlFor="upload-file"
                  label="Файл выписки"
                  required
                >
                  <label
                    className={`${styles.fileControl} ${file ? styles.fileSelected : ""}`}
                    htmlFor="upload-file"
                  >
                    <input
                      ref={fileRef}
                      id="upload-file"
                      accept={reference.acceptedExtensions.join(",")}
                      aria-describedby={
                        fieldErrors.statement ? "upload-file-error" : undefined
                      }
                      aria-invalid={Boolean(fieldErrors.statement)}
                      disabled={pending}
                      name="statement"
                      required
                      type="file"
                      onChange={(event) =>
                        selectFile(event.target.files?.[0] ?? null)
                      }
                    />
                    <Icon name={file ? "source" : "imports"} size={28} />
                    <span>
                      <strong>
                        {file ? file.name : "Выберите PDF или XLSX"}
                      </strong>
                      <small>
                        {file
                          ? formatFileSize(file.size)
                          : "Файл останется на вашем устройстве до отправки"}
                      </small>
                    </span>
                    <span className={styles.chooseLabel}>
                      {file ? "Заменить" : "Выбрать"}
                    </span>
                  </label>
                </Field>

                <FormActions>
                  <Button
                    disabled={pending}
                    icon="imports"
                    isLoading={pending}
                    tone="primary"
                    type="submit"
                  >
                    {pending ? "Сохраняем и распознаём…" : "Загрузить выписку"}
                  </Button>
                  <p aria-live="polite" className={styles.actionHint}>
                    {pending
                      ? "Не закрывайте страницу. Даже при ошибке распознавания исходный файл будет сохранён."
                      : "После загрузки откроется карточка документа с результатом распознавания."}
                  </p>
                </FormActions>
              </form>

              <aside
                className={styles.guide}
                aria-label="Что произойдёт после загрузки"
              >
                <p className={styles.eyebrow}>Дальше автоматически</p>
                <ol>
                  <li>
                    <span>1</span>
                    <div>
                      <strong>Сохраним оригинал</strong>
                      <p>Файл не потеряется, даже если банк не распознается.</p>
                    </div>
                  </li>
                  <li>
                    <span>2</span>
                    <div>
                      <strong>Извлечём строки</strong>
                      <p>Известные форматы сразу подготовим к проверке.</p>
                    </div>
                  </li>
                  <li>
                    <span>3</span>
                    <div>
                      <strong>Покажем следующий шаг</strong>
                      <p>Проверка строк или настройка колонок — без догадок.</p>
                    </div>
                  </li>
                </ol>
              </aside>
            </div>
          )}
        </WorkbenchSurface>
      </PageFrame>
    </AppShell>
  );
}

function validateDraft(
  reference: ImportUploadReferenceDto,
  accountId: string,
  file: File | null,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!accountId) errors.accountId = "Выберите счёт выписки.";
  if (!file) {
    errors.statement = "Выберите файл выписки.";
    return errors;
  }
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!reference.acceptedExtensions.includes(extension)) {
    errors.statement = `Поддерживаются только ${reference.acceptedExtensions.join(", ").toUpperCase()}.`;
  } else if (file.size > reference.maxFileSizeBytes) {
    errors.statement = `Файл больше ${formatFileSize(reference.maxFileSizeBytes)}.`;
  }
  return errors;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toLocaleString("ru-RU", {
    maximumFractionDigits: 1,
  })} МБ`;
}
