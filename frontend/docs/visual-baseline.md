# Visual geometry baseline

Stage 02 извлекает устойчивые решения current SSR и Frontend Next, не копируя
их selectors или stylesheet. Этот файл фиксирует измеримые исходные контракты.

| Область         | Сохраняемый контракт                                                                 |
| --------------- | ------------------------------------------------------------------------------------ |
| Page            | centered content, спокойный vertical rhythm, явные eyebrow/title/description/actions |
| Control         | минимальная высота `2.75rem` (44px), видимый focus ring, full-width на mobile        |
| Date            | first-class row data, semantic `time`, формат `DD.MM.YYYY`, не secondary metadata    |
| Money           | tabular numerals, amount сильнее currency, направление различается не только знаком  |
| Workbench row   | main + action aside `15–20rem`, gap `1rem`, aside отделен border                     |
| Row at 920px    | одна колонка, aside переносится вниз и отделяется сверху                             |
| Mobile at 560px | header/value/actions складываются, horizontal overflow отсутствует                   |
| Expansion       | full-row область, border сверху, явные title/close/content                           |
| Feedback        | loading объявляется через `aria-live`, error через `role=alert`, focus не теряется   |

Intentional differences:

- React components используют CSS Modules, а не публичные BEM classes;
- debug UUID не отображаются;
- icon-only control всегда требует accessible label;
- цвет темы не меняет размеры, spacing или responsive breakpoints;
- hover translation удален: спокойный financial UI меняет surface/border без
  движения layout.

Comparison viewports: `1440×1000`, `920×900`, `390×844`.
