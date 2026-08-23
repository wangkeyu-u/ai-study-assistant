import type { IconProps as PhosphorIconProps } from '@phosphor-icons/react';
import {
  ArrowRight,
  ArrowSquareOut,
  ArrowsClockwise,
  Books,
  CaretDown,
  ChartBar,
  ChatCircleDots,
  Check,
  CheckSquare,
  Clock,
  Copy,
  Database,
  DotsThree,
  FileText,
  GearSix,
  Graph,
  House,
  MagnifyingGlass,
  NotePencil,
  Plus,
  SlidersHorizontal,
  Sparkle,
  Stack,
  Trash,
  UploadSimple,
  WifiSlash,
  X,
  type Icon as PhosphorIcon,
} from '@phosphor-icons/react';

export type IconName =
  | 'home'
  | 'library'
  | 'chat'
  | 'quiz'
  | 'chart'
  | 'graph'
  | 'settings'
  | 'search'
  | 'plus'
  | 'upload'
  | 'file'
  | 'note'
  | 'arrow'
  | 'clock'
  | 'more'
  | 'database'
  | 'check'
  | 'offline'
  | 'sparkles'
  | 'copy'
  | 'external'
  | 'sliders'
  | 'trash'
  | 'layers'
  | 'chevron'
  | 'x'
  | 'refresh';

interface IconProps extends Omit<PhosphorIconProps, 'size'> {
  name: IconName;
  size?: number;
}

const icons: Record<IconName, PhosphorIcon> = {
  home: House,
  library: Books,
  chat: ChatCircleDots,
  quiz: CheckSquare,
  chart: ChartBar,
  graph: Graph,
  settings: GearSix,
  search: MagnifyingGlass,
  plus: Plus,
  upload: UploadSimple,
  file: FileText,
  note: NotePencil,
  arrow: ArrowRight,
  clock: Clock,
  more: DotsThree,
  database: Database,
  check: Check,
  offline: WifiSlash,
  sparkles: Sparkle,
  copy: Copy,
  external: ArrowSquareOut,
  sliders: SlidersHorizontal,
  trash: Trash,
  layers: Stack,
  chevron: CaretDown,
  x: X,
  refresh: ArrowsClockwise,
};

export default function Icon({ name, size = 18, ...props }: IconProps) {
  const Component = icons[name];
  return <Component aria-hidden="true" size={size} weight="regular" {...props} />;
}
