import type { ComponentPropsWithoutRef } from "react";

import styles from "./page-frame.module.css";

type PageFrameProps = ComponentPropsWithoutRef<"section"> & {
  mobileTop?: "compact" | "standard";
  spacing?: "block" | "top";
};

export function PageFrame({
  children,
  className,
  mobileTop = "standard",
  spacing = "top",
  ...props
}: PageFrameProps) {
  return (
    <section
      className={
        className === undefined ? styles.frame : `${styles.frame} ${className}`
      }
      data-mobile-top={mobileTop}
      data-spacing={spacing}
      {...props}
    >
      {children}
    </section>
  );
}
