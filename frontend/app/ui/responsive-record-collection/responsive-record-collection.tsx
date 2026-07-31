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
      <div className={styles.tableRegion}>{table}</div>
      <div className={styles.mobileRegion}>{mobileList}</div>
    </div>
  );
}
