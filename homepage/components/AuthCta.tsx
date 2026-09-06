"use client";

import { authUserInitial, authUserLabel } from "@/lib/auth";
import { useAuthStatus } from "@/hooks/useAuthStatus";
import { Button, buttonClass, type ButtonVariant } from "@/components/ui/Button";

type AuthCtaProps = {
  signedOutLabel: string;
  signedInLabel: string;
  href?: string;
  className?: string;
  variant?: ButtonVariant;
  showIdentity?: boolean;
};

export function AuthCta({
  signedOutLabel,
  signedInLabel,
  href = "/panel",
  className = "",
  variant = "primary",
  showIdentity = false,
}: AuthCtaProps) {
  const auth = useAuthStatus();
  const placeholder = signedInLabel.length >= signedOutLabel.length
    ? signedInLabel
    : signedOutLabel;

  if (auth.status === "loading") {
    return (
      <span
        className={buttonClass(variant, `${className} pointer-events-none`)}
        aria-busy="true"
        aria-label="Checking sign-in"
      >
        <span className="invisible inline-flex items-center gap-2">
          {showIdentity ? (
            <>
              <span className="inline-flex h-6 w-6 shrink-0 rounded-full" />
              <span className="hidden max-w-[9rem] truncate sm:inline">
                user@example.com
              </span>
              <span>{signedInLabel}</span>
            </>
          ) : (
            placeholder
          )}
        </span>
      </span>
    );
  }

  if (auth.status === "signedOut") {
    return (
      <Button as="a" href={href} variant={variant} className={className}>
        {signedOutLabel}
      </Button>
    );
  }

  const label = authUserLabel(auth.user);
  const initial = authUserInitial(label);

  if (!showIdentity) {
    return (
      <Button as="a" href={href} variant={variant} className={className} title={label}>
        {signedInLabel}
      </Button>
    );
  }

  return (
    <Button
      as="a"
      href={href}
      variant={variant}
      className={`${className} gap-2`}
      title={label}
    >
      <span
        aria-hidden="true"
        className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-ink)] text-xs font-bold text-[var(--color-paper)]"
      >
        {initial}
      </span>
      <span className="hidden max-w-[9rem] truncate sm:inline">{label}</span>
      <span>{signedInLabel}</span>
    </Button>
  );
}
