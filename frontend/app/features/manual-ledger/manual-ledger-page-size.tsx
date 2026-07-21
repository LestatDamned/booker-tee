import { useLocation, useNavigate } from "react-router";

import styles from "./manual-ledger.module.css";

type ManualLedgerPageSizeProps = {
  disabled?: boolean;
  options: number[];
  value: number;
};

export function ManualLedgerPageSize({
  disabled = false,
  options,
  value,
}: ManualLedgerPageSizeProps) {
  const location = useLocation();
  const navigate = useNavigate();

  function changePageSize(nextValue: string) {
    const pageSize = Number(nextValue);
    if (!options.includes(pageSize)) {
      return;
    }
    const search = new URLSearchParams(location.search);
    search.set("page", "1");
    search.set("per_page", String(pageSize));
    void navigate({
      pathname: location.pathname,
      search: `?${search.toString()}`,
    });
  }

  return (
    <label className={styles.pageSize} htmlFor="manual-ledger-page-size">
      На странице
      <select
        id="manual-ledger-page-size"
        disabled={disabled}
        name="perPage"
        onChange={(event) => changePageSize(event.currentTarget.value)}
        value={String(value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
