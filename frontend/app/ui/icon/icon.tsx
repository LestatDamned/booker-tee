import type { Icon as PhosphorIcon, IconWeight } from "@phosphor-icons/react";
import {
  ArrowClockwise,
  ArrowUUpLeft,
  ArrowsLeftRight,
  Buildings,
  CaretDown,
  CaretLeft,
  CaretRight,
  ChartBar,
  CheckCircle,
  Copy,
  DotsThree,
  FileArrowUp,
  FileText,
  Funnel,
  FunnelSimple,
  House,
  Info,
  Lightning,
  ListBullets,
  ListChecks,
  MagnifyingGlass,
  MinusCircle,
  PencilSimple,
  Plus,
  Tag,
  Trash,
  Wallet,
  WarningCircle,
  X,
  XCircle,
} from "@phosphor-icons/react";

export type IconName =
  | "accounts"
  | "automation"
  | "back"
  | "categories"
  | "check"
  | "close"
  | "copy"
  | "delete"
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
