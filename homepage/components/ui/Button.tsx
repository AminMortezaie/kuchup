import type { ButtonHTMLAttributes, ReactNode } from "react";
import { appSurfaceRel } from "@/lib/seo";

export type ButtonVariant = "primary" | "secondary";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  children: ReactNode;
  className?: string;
  href?: string;
  as?: "button" | "a";
  rel?: string;
};

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary:
    "btn-primary inline-flex items-center justify-center px-5 py-2.5 text-sm font-bold text-text-on-accent",
  secondary:
    "btn-secondary inline-flex items-center justify-center px-5 py-2.5 text-sm font-semibold",
};

export function buttonClass(variant: ButtonVariant = "primary", className = "") {
  return `${VARIANT_CLASS[variant]} ${className}`.trim();
}

export function Button({
  variant = "primary",
  children,
  className = "",
  href,
  as,
  rel,
  ...rest
}: ButtonProps) {
  const classes = buttonClass(variant, className);

  if (as === "a" || href) {
    return (
      <a
        href={href}
        className={classes}
        title={rest.title}
        tabIndex={rest.tabIndex}
        rel={rel ?? (href ? appSurfaceRel(href) : undefined)}
      >
        {children}
      </a>
    );
  }

  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  );
}
