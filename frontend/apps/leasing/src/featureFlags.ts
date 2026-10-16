/**
 * Build-time feature flags.
 *
 * Each flag is read from the build environment via Vite's `VITE_` prefix
 * convention. Set the corresponding env var before building to enable a flag.
 */
export const FLAG_PLOTSEARCH = import.meta.env.VITE_FLAG_PLOTSEARCH === "true";
