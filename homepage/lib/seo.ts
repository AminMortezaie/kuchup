const APP_SURFACE_PATHS = [
  "/panel",
  "/remote",
  "/apply",
  "/admin",
  "/company",
] as const;

export function appSurfaceRel(href: string): "nofollow" | undefined {
  const path = href.split("?")[0];
  const blocked = APP_SURFACE_PATHS.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
  return blocked ? "nofollow" : undefined;
}
