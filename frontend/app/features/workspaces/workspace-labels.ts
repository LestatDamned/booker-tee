import type {
  WorkspaceDirectoryItemDto,
  WorkspaceType,
} from "./api/workspaces-api";

export function workspaceTypeLabel(type: WorkspaceType): string {
  const labels: Record<WorkspaceType, string> = {
    personal: "Личное",
    family: "Семейное",
    business: "Бизнес",
    property_management: "Недвижимость",
    project: "Проект",
    other: "Другое",
  };
  return labels[type];
}

export function workspaceRoleLabel(
  role: WorkspaceDirectoryItemDto["membership"]["role"],
): string {
  const labels: Record<
    WorkspaceDirectoryItemDto["membership"]["role"],
    string
  > = {
    owner: "Владелец",
    admin: "Администратор",
    editor: "Редактор",
    viewer: "Наблюдатель",
    uploader: "Загрузка данных",
    analyst: "Аналитик",
  };
  return labels[role];
}

export function workspaceRoleDescription(
  role: WorkspaceDirectoryItemDto["membership"]["role"],
): string {
  const descriptions: Record<
    WorkspaceDirectoryItemDto["membership"]["role"],
    string
  > = {
    owner: "Полный доступ и управление пространством.",
    admin: "Управление финансами и командой без передачи владения.",
    editor: "Финансовые данные и импорты без управления командой.",
    uploader:
      "Загрузка и подготовка импортов без ручного редактирования финансов.",
    analyst: "Отчёты и финансовые итоги без исходных документов импорта.",
    viewer: "Полное чтение, включая документы и данные импорта.",
  };
  return descriptions[role];
}

export function workspaceRoleOptionLabel(
  role: WorkspaceDirectoryItemDto["membership"]["role"],
): string {
  return `${workspaceRoleLabel(role)} — ${workspaceRoleDescription(role)}`;
}
