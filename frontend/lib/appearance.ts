// Shared with the client hook in hooks/use-appearance.ts; kept here so the server layout can import it.
export const APPEARANCE_KEY = "appearance";

/** Runs before first paint (see app/layout.tsx) so a dark theme never flashes light. */
export const APPEARANCE_BOOT = `(function(){try{var a=localStorage.getItem("${APPEARANCE_KEY}");var d=a==="dark"||(a!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d);document.documentElement.style.colorScheme=d?"dark":"light"}catch(e){}})();`;
