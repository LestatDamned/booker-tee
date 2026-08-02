import { Fragment, type ReactNode } from "react";

import { Button } from "../../ui/button/button";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag, type TagTone } from "../../ui/tag/tag";
import type { TransactionRuleSummaryDto } from "./api/transaction-rules-api";
import styles from "./transaction-rules-page.module.css";

type TransactionRuleRecordsProps = {
  editPanel: ReactNode;
  editingRuleId: string | null;
  editingVariant: "desktop" | "mobile" | null;
  onEdit: (
    ruleId: string,
    variant: "desktop" | "mobile",
    trigger: HTMLButtonElement,
  ) => void;
  lifecyclePendingId: string | null;
  deletePendingId: string | null;
  onDisable: (rule: TransactionRuleSummaryDto) => void;
  onEnable: (rule: TransactionRuleSummaryDto) => void;
  onEnableBlocked: (rule: TransactionRuleSummaryDto) => void;
  onDelete: (rule: TransactionRuleSummaryDto) => void;
  onDeleteBlocked: (rule: TransactionRuleSummaryDto) => void;
  rules: TransactionRuleSummaryDto[];
  targetId: string | null;
};

export function TransactionRuleTable({
  editPanel,
  editingRuleId,
  editingVariant,
  onEdit,
  deletePendingId,
  lifecyclePendingId,
  onDisable,
  onEnable,
  onEnableBlocked,
  onDelete,
  onDeleteBlocked,
  rules,
  targetId,
}: TransactionRuleRecordsProps) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">
        Правила обработки операций текущего workspace
      </caption>
      <thead>
        <tr>
          <th scope="col">Правило и условие</th>
          <th scope="col">Область</th>
          <th scope="col">Результат</th>
          <th scope="col">Режим и состояние</th>
          <th scope="col">Действия</th>
        </tr>
      </thead>
      <tbody>
        {rules.map((rule) => {
          const isEditing =
            editingRuleId === rule.id && editingVariant === "desktop";
          const panelId = `rule-edit-desktop-${rule.id}-panel`;
          return (
            <Fragment key={rule.id}>
              <tr
                data-rule-id={rule.id}
                data-targeted={targetId === rule.id ? "true" : undefined}
                id={`rule-${rule.id}`}
                tabIndex={-1}
              >
                <th scope="row">
                  <RuleIdentity rule={rule} />
                  <p className={styles.condition}>{conditionLabel(rule)}</p>
                </th>
                <td>
                  <RuleScope rule={rule} />
                </td>
                <td>
                  <RuleOutcome rule={rule} />
                </td>
                <td>
                  <RuleBehavior rule={rule} />
                </td>
                <td>
                  <RuleActions
                    editing={editingRuleId !== null}
                    deletePendingId={deletePendingId}
                    isEditing={isEditing}
                    lifecyclePendingId={lifecyclePendingId}
                    onDisable={onDisable}
                    onEdit={(trigger) => onEdit(rule.id, "desktop", trigger)}
                    onEnable={onEnable}
                    onEnableBlocked={onEnableBlocked}
                    onDelete={onDelete}
                    onDeleteBlocked={onDeleteBlocked}
                    panelId={panelId}
                    rule={rule}
                  />
                </td>
              </tr>
              {isEditing ? (
                <tr className={styles.editRow}>
                  <td colSpan={5}>{editPanel}</td>
                </tr>
              ) : null}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

export function TransactionRuleMobileList({
  editPanel,
  editingRuleId,
  editingVariant,
  onEdit,
  deletePendingId,
  lifecyclePendingId,
  onDisable,
  onEnable,
  onEnableBlocked,
  onDelete,
  onDeleteBlocked,
  rules,
  targetId,
}: TransactionRuleRecordsProps) {
  return (
    <ol aria-label="Правила обработки операций текущего workspace">
      {rules.map((rule) => {
        const isEditing =
          editingRuleId === rule.id && editingVariant === "mobile";
        const panelId = `rule-edit-mobile-${rule.id}-panel`;
        return (
          <li key={rule.id}>
            <article
              data-responsive-record
              data-rule-id={rule.id}
              data-targeted={targetId === rule.id ? "true" : undefined}
              tabIndex={-1}
            >
              <div className={styles.mobileHeading}>
                <RuleIdentity rule={rule} />
                <RuleStatus rule={rule} />
              </div>
              <p className={styles.condition}>{conditionLabel(rule)}</p>
              <RuleScope rule={rule} />
              <RuleOutcome rule={rule} />
              <RuleBehavior rule={rule} showStatus={false} />
              <RuleActions
                editing={editingRuleId !== null}
                deletePendingId={deletePendingId}
                isEditing={isEditing}
                lifecyclePendingId={lifecyclePendingId}
                onDisable={onDisable}
                onEdit={(trigger) => onEdit(rule.id, "mobile", trigger)}
                onEnable={onEnable}
                onEnableBlocked={onEnableBlocked}
                onDelete={onDelete}
                onDeleteBlocked={onDeleteBlocked}
                panelId={panelId}
                rule={rule}
              />
            </article>
            {isEditing ? editPanel : null}
          </li>
        );
      })}
    </ol>
  );
}

function RuleIdentity({ rule }: { rule: TransactionRuleSummaryDto }) {
  return (
    <span data-record-identity>
      {rule.name}
      <small className={styles.priority}>Приоритет {rule.priority}</small>
    </span>
  );
}

function RuleScope({ rule }: { rule: TransactionRuleSummaryDto }) {
  return (
    <div className={styles.factStack}>
      <Tag variant="soft">{directionLabel(rule.condition.direction)}</Tag>
      <span>
        {amountLabel(rule.condition.amountMin, rule.condition.amountMax)}
      </span>
      {rule.condition.account ? (
        <span>
          Счёт: {rule.condition.account.name}
          {!rule.condition.account.isActive ? " · недоступен" : ""}
        </span>
      ) : (
        <span>Любой счёт</span>
      )}
    </div>
  );
}

function RuleOutcome({ rule }: { rule: TransactionRuleSummaryDto }) {
  const operationType = rule.outcome.operationType;
  return (
    <div className={styles.factStack}>
      {operationType ? (
        <Tag tone={operationTone(operationType)} variant="soft">
          {operationTypeLabel(operationType)}
        </Tag>
      ) : (
        <Tag variant="soft">Тип не меняется</Tag>
      )}
      <span>{referenceLabel("Категория", rule.outcome.category)}</span>
      <span>{referenceLabel("Объект", rule.outcome.property)}</span>
      {rule.outcome.autoDescription ? (
        <span>Описание: {rule.outcome.autoDescription}</span>
      ) : null}
      <span>{profitLabel(rule.outcome.affectsProfit)}</span>
    </div>
  );
}

function RuleBehavior({
  rule,
  showStatus = true,
}: {
  rule: TransactionRuleSummaryDto;
  showStatus?: boolean;
}) {
  return (
    <div className={styles.factStack}>
      {showStatus ? <RuleStatus rule={rule} /> : null}
      <Tag tone="automation" variant="soft">
        {rule.outcome.applicationMode === "auto_apply"
          ? "Быстрое подтверждение"
          : "Предложение"}
      </Tag>
      <span>
        {rule.usage.directRawSuggestionCount === 0
          ? "Существующих предложений нет"
          : `${rule.usage.directRawSuggestionCount} существующих предложений сохранены`}
      </span>
      <span>
        {rule.isActive
          ? "Сопоставляет только будущие review-операции"
          : "Будущие операции не сопоставляются"}
      </span>
    </div>
  );
}

function RuleActions({
  editing,
  deletePendingId,
  isEditing,
  lifecyclePendingId,
  onDisable,
  onEdit,
  onEnable,
  onEnableBlocked,
  onDelete,
  onDeleteBlocked,
  panelId,
  rule,
}: {
  editing: boolean;
  deletePendingId: string | null;
  isEditing: boolean;
  lifecyclePendingId: string | null;
  onDisable: (rule: TransactionRuleSummaryDto) => void;
  onEdit: (trigger: HTMLButtonElement) => void;
  onEnable: (rule: TransactionRuleSummaryDto) => void;
  onEnableBlocked: (rule: TransactionRuleSummaryDto) => void;
  onDelete: (rule: TransactionRuleSummaryDto) => void;
  onDeleteBlocked: (rule: TransactionRuleSummaryDto) => void;
  panelId: string;
  rule: TransactionRuleSummaryDto;
}) {
  const pending = lifecyclePendingId === rule.id;
  const deletePending = deletePendingId === rule.id;
  const mutationPending =
    lifecyclePendingId !== null || deletePendingId !== null;
  const lifecycle = rule.isActive ? (
    rule.capabilities.canDisable ? (
      <Button
        disabled={editing || mutationPending}
        isLoading={pending}
        onClick={() => onDisable(rule)}
        tone="secondary"
      >
        Выключить
      </Button>
    ) : null
  ) : rule.capabilities.canEnable ? (
    <Button
      disabled={editing || mutationPending}
      isLoading={pending}
      onClick={() => onEnable(rule)}
      tone="secondary"
    >
      Включить
    </Button>
  ) : rule.capabilities.enableBlockedReasonCode ? (
    <Button
      disabled={editing || mutationPending}
      onClick={() => onEnableBlocked(rule)}
      tone="secondary"
    >
      Почему нельзя включить
    </Button>
  ) : null;
  return (
    <ActionStack
      orientation="row"
      primary={
        rule.capabilities.canUpdate ? (
          <Button
            aria-controls={panelId}
            aria-expanded={isEditing}
            disabled={mutationPending}
            icon="edit"
            onClick={(event) => onEdit(event.currentTarget)}
            tone="secondary"
          >
            {isEditing ? "Закрыть" : "Изменить"}
          </Button>
        ) : undefined
      }
      secondary={lifecycle ?? undefined}
      danger={
        rule.capabilities.canDelete ? (
          <Button
            disabled={editing || mutationPending}
            icon="delete"
            isLoading={deletePending}
            onClick={() => onDelete(rule)}
            tone="danger"
          >
            Удалить правило
          </Button>
        ) : undefined
      }
      overflow={
        !rule.isActive &&
        rule.capabilities.deleteBlockedReasonCode === "raw_suggestions" ? (
          <Button
            disabled={editing || mutationPending}
            onClick={() => onDeleteBlocked(rule)}
          >
            Почему нельзя удалить
          </Button>
        ) : undefined
      }
    />
  );
}

function RuleStatus({ rule }: { rule: TransactionRuleSummaryDto }) {
  return rule.isActive ? (
    <StatusLabel tone="success">Активно</StatusLabel>
  ) : (
    <StatusLabel tone="neutral">Выключено</StatusLabel>
  );
}

function conditionLabel(rule: TransactionRuleSummaryDto): string {
  return rule.condition.matchType === "exact"
    ? `Описание в точности «${rule.condition.pattern}»`
    : `Описание содержит «${rule.condition.pattern}»`;
}

function directionLabel(
  direction: TransactionRuleSummaryDto["condition"]["direction"],
): string {
  if (direction === "inflow") return "Поступление";
  if (direction === "outflow") return "Списание";
  return "Любое направление";
}

function amountLabel(minimum: string | null, maximum: string | null): string {
  if (minimum && maximum) return `Сумма ${minimum}–${maximum}`;
  if (minimum) return `Сумма от ${minimum}`;
  if (maximum) return `Сумма до ${maximum}`;
  return "Любая абсолютная сумма";
}

function referenceLabel(
  label: string,
  reference: TransactionRuleSummaryDto["outcome"]["category"],
): string {
  if (!reference) return `${label}: не задана`;
  return `${label}: ${reference.name}${reference.isActive ? "" : " · архив"}`;
}

function operationTypeLabel(
  type: NonNullable<TransactionRuleSummaryDto["outcome"]["operationType"]>,
): string {
  return {
    adjustment: "Корректировка",
    expense: "Расход",
    income: "Доход",
    transfer: "Перевод",
  }[type];
}

function operationTone(
  type: NonNullable<TransactionRuleSummaryDto["outcome"]["operationType"]>,
): TagTone {
  return type;
}

function profitLabel(affectsProfit: boolean | null): string {
  if (affectsProfit === true) return "Влияет на финансовый результат";
  if (affectsProfit === false) return "Не влияет на финансовый результат";
  return "Влияние на результат определяется типом операции";
}
