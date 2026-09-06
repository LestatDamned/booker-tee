import type { Icon as PhosphorIcon, IconWeight } from "@phosphor-icons/react";
import { ArrowDown } from "@phosphor-icons/react/dist/csr/ArrowDown";
import { ArrowClockwise } from "@phosphor-icons/react/dist/csr/ArrowClockwise";
import { ArrowsDownUp } from "@phosphor-icons/react/dist/csr/ArrowsDownUp";
import { ArrowUp } from "@phosphor-icons/react/dist/csr/ArrowUp";
import { ArrowUUpLeft } from "@phosphor-icons/react/dist/csr/ArrowUUpLeft";
import { ArrowsLeftRight } from "@phosphor-icons/react/dist/csr/ArrowsLeftRight";
import { Buildings } from "@phosphor-icons/react/dist/csr/Buildings";
import { CaretDown } from "@phosphor-icons/react/dist/csr/CaretDown";
import { CaretLeft } from "@phosphor-icons/react/dist/csr/CaretLeft";
import { CaretRight } from "@phosphor-icons/react/dist/csr/CaretRight";
import { ChartBar } from "@phosphor-icons/react/dist/csr/ChartBar";
import { CheckCircle } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { Copy } from "@phosphor-icons/react/dist/csr/Copy";
import { DotsThree } from "@phosphor-icons/react/dist/csr/DotsThree";
import { FileArrowUp } from "@phosphor-icons/react/dist/csr/FileArrowUp";
import { FileText } from "@phosphor-icons/react/dist/csr/FileText";
import { Funnel } from "@phosphor-icons/react/dist/csr/Funnel";
import { FunnelSimple } from "@phosphor-icons/react/dist/csr/FunnelSimple";
import { HandCoins } from "@phosphor-icons/react/dist/csr/HandCoins";
import { House } from "@phosphor-icons/react/dist/csr/House";
import { Info } from "@phosphor-icons/react/dist/csr/Info";
import { Lightning } from "@phosphor-icons/react/dist/csr/Lightning";
import { ListBullets } from "@phosphor-icons/react/dist/csr/ListBullets";
import { ListChecks } from "@phosphor-icons/react/dist/csr/ListChecks";
import { MagnifyingGlass } from "@phosphor-icons/react/dist/csr/MagnifyingGlass";
import { MinusCircle } from "@phosphor-icons/react/dist/csr/MinusCircle";
import { PencilSimple } from "@phosphor-icons/react/dist/csr/PencilSimple";
import { Plus } from "@phosphor-icons/react/dist/csr/Plus";
import { Tag } from "@phosphor-icons/react/dist/csr/Tag";
import { Trash } from "@phosphor-icons/react/dist/csr/Trash";
import { Wallet } from "@phosphor-icons/react/dist/csr/Wallet";
import { WarningCircle } from "@phosphor-icons/react/dist/csr/WarningCircle";
import { X } from "@phosphor-icons/react/dist/csr/X";
import { XCircle } from "@phosphor-icons/react/dist/csr/XCircle";

export type IconName =
  | "accounts"
  | "automation"
  | "back"
  | "categories"
  | "check"
  | "close"
  | "copy"
  | "delete"
  | "debts"
  | "edit"
  | "expand"
  | "filter"
  | "filterApply"
  | "forward"
  | "home"
  | "imports"
  | "information"
  | "menu"
  | "more"
  | "neutral"
  | "operations"
  | "plus"
  | "properties"
  | "reports"
  | "retry"
  | "rules"
  | "search"
  | "source"
  | "sort"
  | "sortAscending"
  | "sortDescending"
  | "transfer"
  | "undo"
  | "warning"
  | "error";

const icons: Record<IconName, PhosphorIcon> = {
  accounts: Wallet,
  automation: Lightning,
  back: CaretLeft,
  categories: Tag,
  check: CheckCircle,
  close: X,
  copy: Copy,
  delete: Trash,
  debts: HandCoins,
  edit: PencilSimple,
  error: XCircle,
  expand: CaretDown,
  filter: Funnel,
  filterApply: FunnelSimple,
  forward: CaretRight,
  home: House,
  imports: FileArrowUp,
  information: Info,
  menu: ListBullets,
  more: DotsThree,
  neutral: MinusCircle,
  operations: ArrowsLeftRight,
  plus: Plus,
  properties: Buildings,
  reports: ChartBar,
  retry: ArrowClockwise,
  rules: ListChecks,
  search: MagnifyingGlass,
  source: FileText,
  sort: ArrowsDownUp,
  sortAscending: ArrowUp,
  sortDescending: ArrowDown,
  transfer: ArrowsLeftRight,
  undo: ArrowUUpLeft,
  warning: WarningCircle,
};

type IconProps = {
  className?: string | undefined;
  name: IconName;
  size?: number | string;
  weight?: IconWeight;
};

export function Icon({
  className,
  name,
  size = "1em",
  weight = "regular",
}: IconProps) {
  const Glyph = icons[name];
  return (
    <Glyph
      aria-hidden="true"
      className={className}
      focusable="false"
      size={size}
      weight={weight}
    />
  );
}
