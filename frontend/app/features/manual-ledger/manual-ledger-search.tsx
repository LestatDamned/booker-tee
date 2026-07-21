import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/button/button";
import styles from "./manual-ledger.module.css";

type ManualLedgerSearchProps = {
  disabled?: boolean;
};

export function ManualLedgerSearch({
  disabled = false,
}: ManualLedgerSearchProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const appliedSearch =
    new URLSearchParams(location.search).get("search") ?? "";
  const [draft, setDraft] = useState(appliedSearch);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const search = new URLSearchParams(location.search);
    const normalized = draft.trim().replace(/\s+/g, " ");
    if (normalized) {
      search.set("search", normalized);
    } else {
      search.delete("search");
    }
    search.set("page", "1");
    search.delete("operation_id");
    void navigate({
      pathname: location.pathname,
      search: search.size > 0 ? `?${search.toString()}` : "",
      hash: "",
    });
  }

  return (
    <form
      aria-label="Поиск операций"
      className={styles.searchForm}
      onSubmit={submitSearch}
      role="search"
    >
      <label className="visually-hidden" htmlFor="manual-ledger-search">
        Поиск по описанию
      </label>
      <input
        disabled={disabled}
        id="manual-ledger-search"
        name="search"
        onChange={(event) => setDraft(event.currentTarget.value)}
        placeholder="Поиск по описанию"
        type="search"
        value={draft}
      />
      <Button disabled={disabled} type="submit">
        Найти
      </Button>
    </form>
  );
}
