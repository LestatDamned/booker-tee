import type { ReactNode } from "react";

import styles from "./responsive-record-collection.module.css";

type ResponsiveRecordCollectionProps = {
  mobileList: ReactNode;
  table: ReactNode;
};

export function ResponsiveRecordCollection({
  mobileList,
  table,
}: ResponsiveRecordCollectionProps) {
  return (
    <div className={styles.collection}>
      <div className={styles.tableRegion} data-responsive-table-region>
        {table}
      </div>
      <div className={styles.mobileRegion} data-responsive-mobile-region>
        {mobileList}
      </div>
    </div>
  );
}
