import type { Config } from "tailwindcss";

/**
 * AMINA-aligned Design System
 *
 * Brand match to aminagroup.com: Bitter (serif display) + Satoshi (UI sans),
 * teal-500 primary accent over a Tailwind-gray neutral scale. Risk spectrum
 * is kept functional/semantic and untouched.
 */
const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // === Neutral base (AMINA gray scale — "paper and ink") ===
        ink: {
          DEFAULT: "#111827",   // gray-900, primary text
          soft: "#374151",      // gray-700, secondary text
          muted: "#6b7280",     // gray-500, tertiary text
          faint: "#9ca3af",     // gray-400, disabled / hints
        },
        paper: {
          DEFAULT: "#f9fafb",   // gray-50, main background
          raised: "#ffffff",    // cards, raised surfaces
          sunken: "#f3f4f6",    // gray-100, wells, insets
          line: "#e5e7eb",      // gray-200, borders, dividers
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
        // === Brand accent (AMINA teal) ===
        accent: {
          DEFAULT: "#0d9488",   // teal-600 — links, active, chart curves
          soft: "#0f766e",      // teal-700 — hover/active
          strong: "#14b8a6",    // teal-500 — primary CTA fills
          bg: "#f0fdfa",        // teal-50 — pale teal wash
        },
        "accent-2": "#7c3aed",  // violet — BOCPD regime-change marker

      },
      fontFamily: {
        // CSS variables provided by next/font (see src/app/layout.tsx). Fallback
        // stacks keep text legible before the self-hosted fonts paint.
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "ui-serif", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
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
        focus: "0 0 0 3px rgb(13 148 136 / 0.18)",
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
