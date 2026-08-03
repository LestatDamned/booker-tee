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
