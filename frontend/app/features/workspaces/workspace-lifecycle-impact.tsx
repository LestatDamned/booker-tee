import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { WorkspaceSettingsDto } from "./api/workspace-settings-api";
import { Fact } from "./workspace-settings-fields";
import styles from "./workspace-settings-page.module.css";

export function WorkspaceLifecycleImpact({
  settings,
}: {
  settings: WorkspaceSettingsDto;
}) {
  const impact = settings.lifecycleImpact;
  return (
    <section
      aria-labelledby="workspace-lifecycle-title"
      className={styles.section}
    >
      <div className={styles.sectionHeading}>
        <div>
          <h2 id="workspace-lifecycle-title">Связанные данные</h2>
          <p>Что сохранится при деактивации пространства.</p>
        </div>
      </div>
      {impact ? (
        <>
          <InlineNotice
            title="Финансовая история сохранится"
            tone="information"
          >
            Счета, импорты, правила, операции и отчёты не будут удалены.
          </InlineNotice>
          <dl className={styles.impactGrid}>
            <Fact
              label="Активные сессии"
              value={String(impact.currentSessionCount)}
            />
            <Fact
              label="Приглашения"
              value={String(impact.pendingInvitationCount)}
            />
            <Fact
              label="Интеграции"
              value={String(impact.activeIntegrationConnectionCount)}
            />
            <Fact
              label="Подключения к чату"
              value={String(impact.activeChatIdentityBindingCount)}
            />
          </dl>
        </>
      ) : (
        <InlineNotice title="Доступно только владельцу" tone="neutral">
          Сведения о сессиях, приглашениях и подключениях скрыты.
        </InlineNotice>
      )}
    </section>
  );
}
