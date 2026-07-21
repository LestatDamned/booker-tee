import styles from "./form-error-summary.module.css";

export type FormErrorSummaryItem = {
  fieldId: string;
  label: string;
  message: string;
};

type FormErrorSummaryProps = {
  errors?: FormErrorSummaryItem[];
  headingLevel?: 3 | 4;
  message: string;
  title?: string;
};

export function FormErrorSummary({
  errors = [],
  headingLevel = 3,
  message,
  title = "Проверьте форму",
}: FormErrorSummaryProps) {
  const Heading = headingLevel === 4 ? "h4" : "h3";
  return (
    <div className={styles.summary} role="alert">
      <Heading>{title}</Heading>
      <p>{message}</p>
      {errors.length > 0 ? (
        <ul>
          {errors.map((error) => (
            <li key={`${error.fieldId}-${error.message}`}>
              <a href={`#${error.fieldId}`}>
                {error.label}: {error.message}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
