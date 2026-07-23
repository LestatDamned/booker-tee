# ADR-0003: Tokenized CSS And Themes

Status: accepted 2026-07-20.

## Context

Legacy CSS велик, глобален и связан с DOM/HTMX. Предыдущие SSR experiments
содержали полезную геометрию и semantic palette, но их stylesheets нельзя было
сделать React foundation без переноса старой связанности.

## Decision

- CSS разделяется на semantic tokens, theme values, global foundation и
  colocated component/feature CSS Modules.
- Theme выбирается одним root `data-theme` attribute.
- Компоненты используют semantic tokens и не знают имя palette/theme.
- Новая theme заменяет token values и не копирует component stylesheet.
- Theme не меняет geometry, density и information hierarchy.
- Повторяемые spacing, type, radius, shadow, motion и control sizes tokenized;
  уникальное локальное число не становится token автоматически.
- Shared component владеет повторяемой geometry; feature CSS владеет только
  composition и уникальными states.
- Legacy stylesheets не импортируются в React. Из них вручную извлекаются
  проверенные tokens, geometry и interaction states.
- Наблюдаемые screenshots на desktop, `920px` и mobile являются migration
  baseline. Исправления старых UI bugs документируются как intentional diff.
- Минимальная test theme проверяет полноту token contract до theme switcher.

## Consequences

- Raw palette values в component/feature CSS являются ошибкой review.
- Общий line count не является целью сам по себе; контролируются duplication,
  leakage, specificity и unused selectors.
- Compact/comfortable density, если понадобится, создается отдельной token axis,
  а не как побочный эффект theme.
