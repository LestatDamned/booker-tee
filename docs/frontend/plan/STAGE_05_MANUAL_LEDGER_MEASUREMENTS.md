# Stage 05: Manual Ledger Cutover Measurements

Measured: 2026-07-20.

Цель измерения — проверить отсутствие явной регрессии и N+1 перед cutover, а не
создать преждевременный performance framework. Значения сравнивают warmed
workspace и 50 однотипных rows; это инженерный baseline, не production SLA.

## Response And Bundle Size

| Variant                       |        Financial response, 50 rows |                               Cacheable browser assets | Interpretation                                               |
| ----------------------------- | ---------------------------------: | -----------------------------------------------------: | ------------------------------------------------------------ |
| Current SSR                   |                 235,846 bytes HTML |                          shared legacy CSS/JS отдельно | весь HTML повторяется при полной навигации                   |
| Frontend Next SSR             |                 230,094 bytes HTML |                          Next CSS/HTMX/Alpine отдельно | размер почти не изменился относительно current SSR           |
| React JSON API                | 26,966 bytes raw; 3,064 bytes gzip |                                  React chunks отдельно | финансовый response примерно в 8.5 раза меньше SSR HTML raw  |
| React first-route upper bound |                          JSON выше | 444,948 bytes raw; 141,166 bytes independently gzipped | первый SPA load дороже, chunks cacheable и не повторяют rows |

Upper bound включает index, runtime, session/schema, shell, error boundary,
Workbench Row и manual-ledger chunks. Это консервативная сумма подходящих build
artifacts, а не утверждение, что browser обязательно скачивает каждый chunk до
первого paint.

Отдельные manual-ledger artifacts production build:

- route JS: 29,301 bytes raw, 8,383 bytes gzip;
- route CSS: 4,040 bytes raw, 932 bytes gzip;
- SPA index: 1,712 bytes raw, 812 bytes gzip.

## Query Shape

Current baseline зафиксировал 9 SQL round trips на warmed list: references,
count, operation select и четыре batched relationship loads. Frontend Next и
React API вызывают тот же `LedgerPostingService.list_manual_operations` и три
workspace-scoped reference queries, поэтому сохраняют тот же row-independent
shape. React дополнительно загружает session отдельным API request; это auth
boundary, не row-dependent ledger query.

Ни одна из трёх реализаций не выполняет запрос на каждую строку. React edit
references остаются lazy и загружаются только после открытия конкретной формы.

## Browser Gate

Realistic audit после canonical switch проверил три маршрута на desktop, 920 px
и mobile: historical redirect, Frontend Next и React. Все 9 combinations прошли
без horizontal overflow, console/page/request и UX assertion errors.

React-only gate дополнительно прошёл create/edit/`422`/`409`, cancel/restore/
delete, readonly DOM, missing session, explicit refresh, Back/Forward и stable
target URL. Seeding выполняется через React и больше не зависит от current SSR.

## Trade-Off Accepted For Pilot

React увеличивает первый cache-cold transfer относительно одного SSR document,
но существенно уменьшает повторяемый financial payload и заменяет HTML fragment
coordination явной client state model. Следующий checkpoint — сложный import
review: именно он покажет, оправдывает ли интерактивность этот runtime cost на
наиболее тяжёлом workflow.
