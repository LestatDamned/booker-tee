import { ActionStack } from "../../ui/action-stack/action-stack";
import { Button } from "../../ui/button/button";
import type { CategoryDetailDto } from "./api/category-detail-api";

type CategorySummary = CategoryDetailDto["category"];

export function CategoryLifecycleActions({
  category,
  editing,
  onArchive,
  onArchiveBlocked,
  onDelete,
  onEdit,
  onRestore,
  pending,
}: {
  category: CategorySummary;
  editing: boolean;
  onArchive: () => void;
  onArchiveBlocked: () => void;
  onDelete: () => void;
  onEdit: (trigger: HTMLButtonElement) => void;
  onRestore: () => void;
  pending: boolean;
}) {
  const archiveBlocked =
    category.capabilities.canUpdate &&
    category.capabilities.archiveBlockedReasonCode === "active_rules";
  const lifecycleAction = category.isActive ? (
    category.capabilities.canArchive || archiveBlocked ? (
      <Button
        disabled={editing || pending}
        isLoading={pending}
        onClick={
          category.capabilities.canArchive ? onArchive : onArchiveBlocked
        }
        tone="secondary"
      >
        В архив
      </Button>
    ) : null
  ) : category.capabilities.canRestore ? (
    <Button
      disabled={editing || pending}
      icon="undo"
      isLoading={pending}
      onClick={onRestore}
      tone="secondary"
    >
      Восстановить
    </Button>
  ) : null;

  return (
    <ActionStack
      danger={
        category.capabilities.canDelete ? (
          <Button
            disabled={editing || pending}
            icon="delete"
            onClick={onDelete}
            tone="danger"
          >
            Удалить категорию
          </Button>
        ) : undefined
      }
      orientation="row"
      primary={
        category.capabilities.canUpdate ? (
          <Button
            disabled={pending}
            icon="edit"
            onClick={(event) => onEdit(event.currentTarget)}
          >
            Изменить
          </Button>
        ) : undefined
      }
      secondary={lifecycleAction ?? undefined}
    />
  );
}
