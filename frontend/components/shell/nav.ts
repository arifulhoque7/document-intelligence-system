import { ClipboardCheck, FileStack, GitCompareArrows, LayoutGrid, Receipt, Search, Settings, type LucideIcon } from "lucide-react";

export type NavItem = { href: string; title: string; icon: LucideIcon };

export const NAV: NavItem[] = [
  { href: "/", title: "Dashboard", icon: LayoutGrid },
  { href: "/documents", title: "Documents", icon: FileStack },
  { href: "/review", title: "Review queue", icon: ClipboardCheck },
  { href: "/invoices", title: "Invoices", icon: Receipt },
  { href: "/search", title: "Search", icon: Search },
  { href: "/cross-checks", title: "Cross-checks", icon: GitCompareArrows },
  { href: "/settings", title: "Settings", icon: Settings },
];

export function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
