"use client";

import { authDisplayName, authGivenName } from "@/lib/auth";
import { useAuthStatus } from "@/hooks/useAuthStatus";
import { Button, buttonClass, type ButtonVariant } from "@/components/ui/Button";

type AuthCtaProps = {
  signedOutLabel: string;
  signedInLabel: string;
  href?: string;
  className?: string;
  variant?: ButtonVariant;
  compact?: boolean;
  tabIndex?: number;
};

export function AuthPresence({
  variant = "inline",
}: {
  variant?: "inline" | "sheet";
}) {
  const auth = useAuthStatus();
  if (auth.status !== "signedIn") return null;

  const fullName = authDisplayName(auth.user);
  const givenName = authGivenName(auth.user);
  if (variant === "sheet") {
    return (
      <p className="px-3 text-sm text-text-secondary">
        {fullName ? `Signed in as ${fullName}` : "Signed in"}
      </p>
    );
  }
  if (!givenName) return null;
  return (
    <span className="max-w-[9rem] truncate text-sm font-medium text-text-secondary">
      {givenName}
    </span>
  );
}

export function AuthCta({
  signedOutLabel,
  signedInLabel,
  href = "/panel",
  className = "",
  variant = "primary",
  compact = false,
  tabIndex,
}: AuthCtaProps) {
  const auth = useAuthStatus();
  const placeholder = signedInLabel.length >= signedOutLabel.length
    ? signedInLabel
    : signedOutLabel;
  const buttonClassName = compact
    ? `whitespace-nowrap px-3.5 py-2 text-sm ${className}`
    : `whitespace-nowrap ${className}`;

  if (auth.status === "loading") {
    return (
      <span
        className={buttonClass(variant, `${buttonClassName} pointer-events-none`)}
        aria-busy="true"
        aria-label="Checking sign-in"
      >
        <span className="invisible">{compact ? signedOutLabel : placeholder}</span>
      </span>
    );
  }

  if (auth.status === "signedOut") {
    return (
      <Button as="a" href={href} variant={variant} className={buttonClassName} tabIndex={tabIndex}>
        {signedOutLabel}
      </Button>
    );
  }

  return (
    <Button as="a" href={href} variant={variant} className={buttonClassName} tabIndex={tabIndex}>
      {signedInLabel}
    </Button>
  );
}
