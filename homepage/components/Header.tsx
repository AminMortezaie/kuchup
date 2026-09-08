"use client";

import { useEffect, useId, useState } from "react";
import { AuthCta, AuthPresence } from "@/components/AuthCta";
import { BrandLockup } from "@/components/BrandMark";

const NAV_LINKS = [
  { href: "/#product", label: "Product" },
  { href: "/mcp", label: "MCP" },
  { href: "/#countries", label: "Countries" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/#access", label: "Access" },
] as const;

export function Header() {
  const [open, setOpen] = useState(false);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    function onResize() {
      if (window.matchMedia("(min-width: 768px)").matches) setOpen(false);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <header className="nav-glass relative sticky top-0 z-40">
      <div className="landing-nav-inner flex items-center justify-between gap-3">
        <a
          href="/"
          className="inline-flex shrink-0 items-center text-inherit no-underline"
          onClick={() => setOpen(false)}
        >
          <BrandLockup markSize="compact" />
        </a>

        <nav aria-label="Primary" className="hidden md:block">
          <ul className="flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <li key={link.label}>
                <a
                  href={link.href}
                  className="whitespace-nowrap rounded-app px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <div className="hidden md:flex items-center gap-3">
            <AuthPresence />
            <AuthCta
              signedOutLabel="Sign in"
              signedInLabel="Board"
              compact
            />
          </div>
          <button
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded-app border border-[var(--color-rule)] text-text-primary transition-transform duration-150 ease-out active:translate-y-px md:hidden"
            aria-expanded={open}
            aria-controls={menuId}
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>
      </div>

      <nav
        id={menuId}
        aria-label="Primary mobile"
        aria-hidden={!open}
        data-open={open}
        className="mobile-menu-panel absolute inset-x-0 top-full z-50 md:hidden"
      >
        <div className="landing-nav-inner flex flex-col gap-2 pb-4 pt-2">
          <ul className="flex flex-col gap-0.5">
            {NAV_LINKS.map((link) => (
              <li key={link.label}>
                <a
                  href={link.href}
                  tabIndex={open ? undefined : -1}
                  className="block whitespace-nowrap rounded-app px-3 py-2.5 text-sm font-medium text-text-secondary transition-[color,background-color,transform] duration-150 ease-out active:translate-y-px hover:bg-bg-surface-hover hover:text-text-primary"
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-2 border-t border-[var(--color-rule)] pt-3">
            <AuthPresence variant="sheet" />
            <AuthCta
              signedOutLabel="Sign in"
              signedInLabel="Open workspace"
              className="w-full"
              tabIndex={open ? 0 : -1}
            />
          </div>
        </div>
      </nav>
    </header>
  );
}

function MenuIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}
