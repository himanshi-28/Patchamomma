export const tokens = {
  color: {
    canvas: "#FFFFFF",
    surface: "#EEF5F1",
    surfaceStrong: "#DFEBE4",
    ink: "#15201B",
    muted: "#6A746F",
    border: "#C9D8D0",
    primary: "#24483B",
    primaryPressed: "#1D3D32",
    accent: "#5E7F70",
    error: "#A12B32",
    white: "#FFFFFF",
    scrim: "rgba(21, 32, 27, 0.45)",
  },
  space: {
    xxs: 4,
    xs: 8,
    sm: 12,
    md: 16,
    lg: 24,
    xl: 32,
  },
  radius: {
    sm: 8,
    md: 12,
    lg: 16,
  },
  type: {
    small: 15,
    body: 18,
    title: 28,
    display: 36,
  },
  target: {
    minimum: 48,
    primary: 54,
  },
  motion: {
    state: 180,
  },
  a11y: {
    largeTextScale: 1.6,
    maxFontMultiplier: 1.3,
  },
  font: {
    regular: "NotoSansDevanagari_400Regular",
    medium: "NotoSansDevanagari_500Medium",
    bold: "NotoSansDevanagari_700Bold",
  },
} as const;

export type AppTokens = typeof tokens;
