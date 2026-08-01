import { Fragment, type ReactNode } from "react";

import { ActionStack } from "../../ui/action-stack/action-stack";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { StatusLabel } from "../../ui/status-label/status-label";
import type { PropertySummaryDto } from "./api/properties-api";
import styles from "./properties-page.module.css";

export function PropertyTable({
  editingId,
  lifecyclePendingId,
  onArchive,
  onEdit,
  onRestore,
  properties,
  renderEditor,
}: PropertyRecordsProps) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Объекты текущего workspace</caption>
      <thead>
        <tr>
          <th scope="col">Объект</th>
          <th scope="col">Адрес</th>
          <th scope="col">Состояние</th>
          <th scope="col">
            <span className="visually-hidden">Действие</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {properties.map((property) => {
          const panelId = `property-edit-desktop-${property.id}`;
          const editing = editingId === property.id;
          return (
            <Fragment key={property.id}>
              <tr data-property-record>
                <th scope="row">
                  <strong data-record-identity>{property.name}</strong>
                  {property.shortName ? (
                    <span className={styles.shortName}>
                      {property.shortName}
                    </span>
                  ) : null}
                </th>
                <td className={styles.addressCell}>
                  {property.address ?? (
                    <span aria-label="Адрес не указан">—</span>
                  )}
                </td>
                <td>
                  <PropertyStatus property={property} />
                </td>
                <td className={styles.actionCell}>
                  <PropertyActions
                    editing={editing}
                    lifecyclePending={lifecyclePendingId === property.id}
                    onArchive={onArchive}
                    onEdit={onEdit}
                    onRestore={onRestore}
                    panelId={panelId}
                    property={property}
                  />
                </td>
              </tr>
              {editing ? (
                <tr className={styles.expansionRow}>
                  <td colSpan={4}>{renderEditor(property, panelId)}</td>
                </tr>
              ) : null}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

export function PropertyMobileList({
  editingId,
  lifecyclePendingId,
  onArchive,
  onEdit,
  onRestore,
  properties,
  renderEditor,
}: PropertyRecordsProps) {
  return (
    <ol aria-label="Объекты текущего workspace">
      {properties.map((property) => {
        const panelId = `property-edit-mobile-${property.id}`;
        const editing = editingId === property.id;
        return (
          <li key={property.id}>
            <article data-property-record data-responsive-record>
              <div className={styles.mobileHeading}>
                <div>
                  <strong data-record-identity>{property.name}</strong>
                  {property.shortName ? (
                    <span className={styles.shortName}>
                      Коротко: {property.shortName}
                    </span>
                  ) : null}
                </div>
                <PropertyStatus property={property} />
              </div>
              <p className={styles.mobileAddress}>
                {property.address ?? "Адрес не указан"}
              </p>
              <div className={styles.mobileFooter}>
                <PropertyActions
                  editing={editing}
                  lifecyclePending={lifecyclePendingId === property.id}
                  onArchive={onArchive}
                  onEdit={onEdit}
                  onRestore={onRestore}
                  panelId={panelId}
                  property={property}
                />
              </div>
              {editing ? renderEditor(property, panelId) : null}
            </article>
          </li>
        );
      })}
    </ol>
  );
}

type PropertyRecordsProps = {
  editingId: string | null;
  lifecyclePendingId: string | null;
  onArchive: (property: PropertySummaryDto) => void;
  onEdit: (property: PropertySummaryDto, trigger: HTMLButtonElement) => void;
  onRestore: (property: PropertySummaryDto) => void;
  properties: PropertySummaryDto[];
  renderEditor: (property: PropertySummaryDto, panelId: string) => ReactNode;
};

function PropertyStatus({ property }: { property: PropertySummaryDto }) {
  return property.status === "active" ? (
    <StatusLabel tone="success">Активен</StatusLabel>
  ) : (
    <StatusLabel tone="neutral">Архив</StatusLabel>
  );
}

function PropertyActions({
  editing,
  lifecyclePending,
  onArchive,
  onEdit,
  onRestore,
  panelId,
  property,
}: {
  editing: boolean;
  lifecyclePending: boolean;
  onArchive: PropertyRecordsProps["onArchive"];
  onEdit: PropertyRecordsProps["onEdit"];
  onRestore: PropertyRecordsProps["onRestore"];
  panelId: string;
  property: PropertySummaryDto;
}) {
  const report = (
    <RouterButtonLink
      aria-label={`Открыть отчёт по объекту «${property.name}»`}
      icon="reports"
      to={`/reports?property_id=${property.id}`}
    >
      Отчёт
    </RouterButtonLink>
  );
  return (
    <ActionStack
      orientation="row"
      primary={
        property.capabilities.canUpdate ? (
          <Button
            aria-controls={panelId}
            aria-expanded={editing}
            icon="edit"
            onClick={(event) => onEdit(property, event.currentTarget)}
            tone="secondary"
          >
            {editing ? "Закрыть" : "Изменить"}
          </Button>
        ) : (
          report
        )
      }
      danger={
        property.capabilities.canArchive ? (
          <Button
            disabled={editing || lifecyclePending}
            isLoading={lifecyclePending}
            onClick={() => onArchive(property)}
            tone="dangerSecondary"
          >
            В архив
          </Button>
        ) : undefined
      }
      overflow={
        property.capabilities.canUpdate ? (
          <>
            {report}
            {property.capabilities.canRestore ? (
              <Button
                disabled={editing || lifecyclePending}
                isLoading={lifecyclePending}
                onClick={() => onRestore(property)}
                tone="secondary"
              >
                Восстановить
              </Button>
            ) : null}
          </>
        ) : undefined
      }
    />
  );
}
