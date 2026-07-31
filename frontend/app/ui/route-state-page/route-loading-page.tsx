import styles from "./route-state-page.module.css";

type RouteLoadingPageProps = {
  eyebrow: string;
  title: string;
};

export function RouteLoadingPage({ eyebrow, title }: RouteLoadingPageProps) {
  const titleId = "route-loading-title";

  return (
    <main aria-busy="true" aria-labelledby={titleId} className={styles.page}>
      <section aria-live="polite" className={styles.loadingState}>
        <span aria-hidden="true" className={styles.spinner} />
        <div className={styles.copy}>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 id={titleId}>{title}</h1>
        </div>
      </section>
    </main>
  );
}
