# TUI Design Systems — Combined Reference

> Combined design reference for Santai TUI themes. See individual files for full details.

## Available Themes

| # | Name | File | Mood | Primary Accent |
|---|------|------|------|----------------|
| 1 | `claude` | [DESIGN-claude.md](DESIGN-claude.md) | Warm, playful, content-forward | Terracotta `#d77757` |
| 2 | `catppuccin` | [DESIGN-cat.md](DESIGN-cat.md) | Soothing pastel, cozy | Mauve `#cba6f7` |
| 3 | `btop` | [DESIGN-btop.md](DESIGN-btop.md) | Data-dense, gradient-rich | White titles `#eeeeee` / Green `#77ca9b` |

---

## Theme Comparison

| Aspect | Claude Code | Catppuccin | btop |
|--------|------------|------------|------|
| Mood | Warm, playful | Pastel, soothing | Data-dense, dashboard |
| Background | `#1a1a1a` | `#1e1e2e` | `#000000` |
| Foreground | `#ffffff` | `#cdd6f4` | `#cccccc` |
| Primary | `#d77757` (terracotta) | `#cba6f7` (mauve) | `#eeeeee` (white titles) |
| Secondary | `#fd5db1` (hot pink) | `#89b4fa` (blue) | `#77ca9b` (green) |
| Accent | `#b1b9f9` (lavender) | `#f5c2e7` (pink) | `#dc4c4c` (red alerts) |
| Success | `#4eba65` | `#a6e3a1` | `#77ca9b` |
| Warning | `#ffc107` | `#f9e2af` | `#cbc06c` |
| Error | `#ff6b80` | `#f38ba8` | `#dc4c4c` |
| Muted | `#888888` | `#585b70` | `#555555` |
| Surface | `#373737` | `#313244` | `#111111` |
| Border Style | `┌─┐│└─┘` | `╭─╮│╰─╯` (rounded) | `╭─╮│╰─╯` (rounded, colored) |
| Density | Balanced | Cozy | Very dense |
| Target | AI coding agents | Personal tools | System monitors |

---

## Color Palettes

### Claude Code
```css
--bg: #1a1a1a;      --fg: #ffffff;
--primary: #d77757;  --secondary: #fd5db1;
--accent: #b1b9f9;   --success: #4eba65;
--warning: #ffc107;  --error: #ff6b80;
--muted: #888888;    --surface: #373737;
```

### Catppuccin Mocha
```css
--bg: #1e1e2e;      --fg: #cdd6f4;
--primary: #cba6f7;  --secondary: #89b4fa;
--accent: #f5c2e7;   --success: #a6e3a1;
--warning: #f9e2af;  --error: #f38ba8;
--muted: #585b70;    --surface: #313244;
```

### btop
```css
--bg: #000000;      --fg: #cccccc;
--primary: #eeeeee;  --secondary: #77ca9b;
--accent: #dc4c4c;   --success: #77ca9b;
--warning: #cbc06c;  --error: #dc4c4c;
--muted: #555555;    --surface: #111111;
```

---

## Icons & Indicators

| Purpose | Claude | Catppuccin | btop |
|---------|--------|-----------|------|
| Success | `✓` | `✓` | `✓` |
| Error | `✗` | `✗` | `✗` |
| Warning | `!` | `!` | `!` |
| Running | `▸` | `▸` | `R` |
| Spinner | `· ✢ ✳ ✶ ✻ ✽` | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | `│ / ─ \` |
| Bullet | `•` | `◦` | `│` |

---

## Usage

### CLI
```bash
santai ui                    # Default theme (btop)
santai ui --theme claude     # Claude Code theme
santai ui --theme catppuccin # Catppuccin theme
santai ui --theme btop       # btop theme
```

### Python API
```python
from santai_cli.tui.themes import ThemeManager

# Set theme by name
ThemeManager.set_theme("claude")    # or "catppuccin", "btop"

# Get current theme
theme = ThemeManager.get_current_theme()

# Cycle to next theme
next_theme = ThemeManager.cycle_theme()

# Get available themes
names = ThemeManager.get_available_themes()  # ["claude", "catppuccin", "btop"]
```

### TUI Controls
| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all panels |
| `g` | Toggle graph (panel ↔ fullscreen) |
| `t` | Open theme selector (1/2/3 to switch) |
| `n` | Open notes viewer |
| Click file | Preview file contents |
| `Esc` | Close modal/dialog |

---

## Architecture

```
src/santai_cli/tui/
├── __init__.py
├── app.py          # SantaiApp + panels + modal screens
├── themes.py       # ThemeManager + 3 theme definitions + CSS generator
└── design/
    ├── DESIGNS.md       # This file — combined reference
    ├── DESIGN-claude.md # Claude Code full design spec
    ├── DESIGN-cat.md    # Catppuccin full design spec
    └── DESIGN-btop.md   # btop full design spec
```

### Theme System Design

- `ThemeManager` is a class-level singleton managing the active theme
- Each theme defines: `name`, `display_name`, `colors` (ThemeColors), `border_chars`, `icons`
- CSS is generated dynamically from `ThemeColors` via `get_theme_css()`
- Runtime theme switching updates the app stylesheet and reapplies CSS
- Theme selector modal (press `t`) allows switching without restart

---

## Do's and Don'ts by Theme

### Claude Code
- **Do**: Terracotta accents, dashed input, hot pink tools, whimsical verbs
- **Don't**: Cold blues, Unicode box-drawing for input, generic loading text

### Catppuccin
- **Do**: Mauve primary, rounded borders, pastel colors, cozy spacing
- **Don't**: Neon colors, heavy borders, ALL CAPS, overcrowding

### btop
- **Do**: Gradient coloring, braille graphs, dense layout, per-box accent colors
- **Don't**: Flat colors, wasted space, light backgrounds, single accent color
