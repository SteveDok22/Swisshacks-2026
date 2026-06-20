import type { Config } from "tailwindcss";

/**
 * Swiss Institutional Design System
 *
 * Philosophy: refined minimalism for a FINMA-regulated compliance tool.
 * Monochrome base with risk-driven accent colors only.
 * Dense information grids, generous negative space around decisions.
 */
const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // === Monochrome base (the "paper and ink" of the app) ===
        ink: {
          DEFAULT: "#0a0a0b",   // near-black, primary text
          soft: "#3f3f46",      // secondary text
          muted: "#71717a",     // tertiary text
          faint: "#a1a1aa",     // disabled / hints
        },
        paper: {
          DEFAULT: "#fafafa",   // main background
          raised: "#ffffff",    // cards, raised surfaces
          sunken: "#f4f4f5",    // wells, insets
          line: "#e4e4e7",      // borders, dividers
        },
        // === Risk spectrum (the ONLY decorative color, semantic) ===
        risk: {
          low: "#15803d",       // forest green
          "low-bg": "#f0fdf4",
          medium: "#a16207",    // amber
          "medium-bg": "#fefce8",
          high: "#c2410c",      // burnt orange
          "high-bg": "#fff7ed",
          critical: "#b91c1c",  // deep red
          "critical-bg": "#fef2f2",
        },
        // === Functional accent (teal — AMINA brand-aligned) ===
        accent: {
          DEFAULT: "#003d4c",   // AMINA deep teal
          soft: "#1a5f6f",      // lighter teal for hover/active
          bg: "#e8f1f3",        // pale teal wash
        },
        "accent-2": "#7c3aed",  // violet — BOCPD regime-change marker

      },
      fontFamily: {
        sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Tighter, more precise type scale
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
      },
      spacing: {
        "18": "4.5rem",
      },
      borderRadius: {
        DEFAULT: "0.375rem",
        sm: "0.25rem",
      },
      boxShadow: {
        // Subtle, layered — never dramatic
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
        raised: "0 2px 8px -2px rgb(0 0 0 / 0.08), 0 4px 16px -4px rgb(0 0 0 / 0.06)",
        focus: "0 0 0 3px rgb(30 58 95 / 0.12)",
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out forwards",
        "slide-up": "slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "scale-in": "scaleIn 0.2s ease-out forwards",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
