# TUI Design Systems

> Combined design reference for Santai TUI themes.

## Available Themes

1. **[Claude Code](DESIGN-claude.md)** — Warm, playful, content-forward with terracotta accent
2. **[Catppuccin](DESIGN-cat.md)** — Soothing pastel theme with mauve primary
3. **[btop](DESIGN-btop.md)** — Data-dense, gradient-rich system monitor style

---

# Quick Theme Reference

## Theme Comparison

| Aspect | Claude Code | Catppuccin | btop |
|--------|------------|------------|-----|
| Mood | Warm, playful | Pastel, soothing | Data-dense, dashboard |
| Background | `#1a1a1a` | `#1e1e2e` | `#000000` |
| Primary | `#d77757` (terracotta) | `#cba6f7` (mauve) | `#eeeeee` (white titles) |
| Secondary | `#fd5db1` (hot pink) | `#89b4fa` (blue) | `#77ca9b` (green) |
| Accent | `#b1b9f9` (lavender) | `#f5c2e7` (pink) | `#dc4c4c` (red alerts) |
| Border Style | Dashed ASCII (input) / Unicode (tools) | Rounded ╭╮│╰─ | Rounded colored per-box |
| Density | Balanced | Cozy | Very dense |
| Target | AI coding agents | Personal tools | System monitors |

---

## Theme Names (for selector)

- `claude` — Claude Code (warm, terracotta)
- `catppuccin` — Catppuccin Mocha (pastel, mauve)
- `btop` — btop (dense, gradients)

---

## Color Palettes

### Claude Code

```css
--bg: #1a1a1a;
--fg: #ffffff;
--primary: #d77757;      /* Terracotta */
--secondary: #fd5db1;   /* Hot pink */
--accent: #b1b9f9;       /* Lavender */
--success: #4eba65;
--warning: #ffc107;
--error: #ff6b80;
--muted: #888888;
--surface: #373737;
```

### Catppuccin Mocha

```css
--bg: #1e1e2e;
--fg: #cdd6f4;
--primary: #cba6f7;     /* Mauve */
--secondary: #89b4fa;    /* Blue */
--accent: #f5c2e7;       /* Pink */
--success: #a6e3a1;
--warning: #f9e2af;
--error: #f38ba8;
--muted: #585b70;
--surface: #313244;
```

### btop

```css
--bg: #000000;
--fg: #cccccc;
--primary: #eeeeee;       /* Titles */
--secondary: #77ca9b;    /* Green healthy */
--accent: #dc4c4c;       /* Red alerts */
--success: #77ca9b;
--warning: #cbc06c;
--error: #dc4c4c;
--muted: #555555;
--surface: #111111;
```

---

## Border Characters

### Claude Code
- Input: `- - -` (dashed ASCII)
- Tools: `┌─┐│└─┘` (hot pink)

### Catppuccin
- `╭─┐│╰─╯` (rounded, muted)

### btop
- `╭─┐│╰─╯` (colored per box)

---

## Icons & Indicators

| Purpose | Claude | Catppuccin | btop |
|---------|-------|-----------|------|
| Success | `✓` / `+` | `✓` | `█` |
| Error | `✗` / `x` | `✗` | `R` |
| Running | `▸` | `▸` / `⠋` | `R` |
| Spinner | `· ✢ ✳ ✶ ✻ ✽` | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | (realtime) |
| Selected | `>` | `▸` | reverse |
| Bullet | `•` | `◦` | `│` |

---

## Usage in TUI

### Setting a Theme

```python
from santai_cli.tui.themes import ThemeManager

# Set theme by name
ThemeManager.set_theme("claude")    # or "catppuccin", "btop"

# Get current theme
theme = ThemeManager.get_current_theme()
```

### Available Commands

- `t` — Toggle theme selector
- `Ctrl+T` — Cycle to next theme

---

## Do's and Don'ts by Theme

### Claude Code
- **Do**: Terracotta accents, dashed input, hot pink tools
- **Don't**: Cold blues, Unicode box-drawing for input

### Catppuccin  
- **Do**: Mauve primary, rounded borders, pastel colors
- **Don't**: Neon colors, heavy borders, ALL CAPS

### btop
- **Do**: Gradient coloring, braille graphs, dense layout
- **Don't**: Flat colors, wasted space, light backgrounds