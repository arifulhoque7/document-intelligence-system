"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { NAV } from "./nav";

type Crumb = { title: string; href?: string };

function crumbsFor(pathname: string, detail: string | null): Crumb[] {
  if (pathname === "/") return [{ title: "Dashboard" }];
  const [section, id] = pathname.split("/").filter(Boolean);
  const nav = NAV.find((n) => n.href === `/${section}`);
  const root: Crumb = { title: nav?.title ?? section, href: `/${section}` };
  if (!id) return [{ title: root.title }];
  const fallback = section === "documents" ? "Document" : section === "invoices" ? "Invoice" : id;
  return [root, { title: detail ?? fallback }];
}

export function AppHeader({ detail }: { detail: string | null }) {
  const crumbs = crumbsFor(usePathname(), detail);
  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-sidebar-border/50 px-6 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 md:px-4">
      <SidebarTrigger className="-ml-1" />
      <Breadcrumb>
        <BreadcrumbList>
          {crumbs.map((c, i) => (
            <Fragment key={i}>
              <BreadcrumbItem>
                {i === crumbs.length - 1 || !c.href ? (
                  <BreadcrumbPage className="max-w-[40ch] truncate">{c.title}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link href={c.href}>{c.title}</Link>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
              {i < crumbs.length - 1 && <BreadcrumbSeparator />}
            </Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  );
}
