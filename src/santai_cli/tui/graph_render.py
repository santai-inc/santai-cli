"""Obsidian-style graph visualization for terminal rendering.

Implements a force-directed layout and renders nodes/edges
using Braille/Unicode characters for smooth, organic-looking graphs.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class GraphNode:
    """A node in the visual graph."""

    id: str
    label: str
    directory: str
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    degree: int = 0
    size_bytes: int = 0


@dataclass
class GraphEdge:
    """An edge in the visual graph."""

    source: str
    target: str
    edge_type: str = "reference"  # "reference" or "semantic"


@dataclass
class LayoutConfig:
    """Configuration for the force-directed layout."""

    repulsion: float = 500.0
    spring_strength: float = 0.02
    spring_length: float = 8.0
    gravity: float = 0.05
    damping: float = 0.9
    max_velocity: float = 2.0
    iterations: int = 200
    repulsion_max_dist: float = 40.0


def force_directed_layout(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    width: int,
    height: int,
    config: LayoutConfig | None = None,
) -> list[GraphNode]:
    """Run force-directed layout (Fruchterman-Reingold style)."""
    if not nodes:
        return nodes
    if len(nodes) == 1:
        nodes[0].x = width / 2.0
        nodes[0].y = height / 2.0
        nodes[0].degree = 0
        return nodes

    cfg = config or LayoutConfig()

    # Scale repulsion based on node count for better spacing
    n = len(nodes)
    area = width * height
    k = math.sqrt(area / max(n, 1))  # optimal distance
    cfg.repulsion = k * k * 1.5
    cfg.spring_length = k * 0.8

    # Build adjacency
    node_map: dict[str, GraphNode] = {nd.id: nd for nd in nodes}
    adjacency: dict[str, set[str]] = {}
    for e in edges:
        adjacency.setdefault(e.source, set()).add(e.target)
        adjacency.setdefault(e.target, set()).add(e.source)

    for nd in nodes:
        nd.degree = len(adjacency.get(nd.id, set()))

    # Initialize positions: place connected components near each other
    # First, find connected components
    visited: set[str] = set()
    components: list[list[GraphNode]] = []

    def bfs(start_id: str) -> list[GraphNode]:
        queue = [start_id]
        comp = []
        while queue:
            nid = queue.pop(0)
            if nid in visited or nid not in node_map:
                continue
            visited.add(nid)
            comp.append(node_map[nid])
            for neighbor in adjacency.get(nid, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        return comp

    for nd in nodes:
        if nd.id not in visited:
            comp = bfs(nd.id)
            if comp:
                components.append(comp)

    # Place each component in a different region
    cx, cy = width / 2.0, height / 2.0
    if len(components) == 1:
        # Single component: circular layout
        comp = components[0]
        radius = min(width, height) * 0.3
        for i, nd in enumerate(comp):
            angle = 2 * math.pi * i / max(len(comp), 1)
            nd.x = cx + radius * math.cos(angle) + random.uniform(-2, 2)
            nd.y = cy + radius * math.sin(angle) + random.uniform(-1, 1)
            nd.vx = 0.0
            nd.vy = 0.0
    else:
        # Multiple components: spread them out
        comp_angle_step = 2 * math.pi / max(len(components), 1)
        spread_radius = min(width, height) * 0.25
        for ci, comp in enumerate(components):
            comp_cx = cx + spread_radius * math.cos(ci * comp_angle_step)
            comp_cy = cy + spread_radius * math.sin(ci * comp_angle_step)
            sub_radius = min(width, height) * 0.12
            for i, nd in enumerate(comp):
                angle = 2 * math.pi * i / max(len(comp), 1)
                nd.x = comp_cx + sub_radius * math.cos(angle) + random.uniform(-1, 1)
                nd.y = (
                    comp_cy + sub_radius * math.sin(angle) + random.uniform(-0.5, 0.5)
                )
                nd.vx = 0.0
                nd.vy = 0.0

    # Simulation with cooling
    for iteration in range(cfg.iterations):
        temperature = max(0.1, 1.0 - iteration / cfg.iterations)

        forces: dict[str, list[float]] = {nd.id: [0.0, 0.0] for nd in nodes}

        # Repulsion (all pairs, with cutoff)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dx = a.x - b.x
                dy = (a.y - b.y) * 2.0  # Scale Y since terminal chars are ~2x tall
                dist_sq = dx * dx + dy * dy
                dist = math.sqrt(dist_sq) if dist_sq > 0.01 else 0.1

                if dist > cfg.repulsion_max_dist:
                    continue

                force = cfg.repulsion / max(dist_sq, 1.0)
                fx = (dx / dist) * force
                fy = ((a.y - b.y) / dist) * force  # Use original dy for force

                forces[a.id][0] += fx
                forces[a.id][1] += fy
                forces[b.id][0] -= fx
                forces[b.id][1] -= fy

        # Spring attraction along edges
        for edge in edges:
            if edge.source not in node_map or edge.target not in node_map:
                continue
            a = node_map[edge.source]
            b = node_map[edge.target]
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.1:
                dist = 0.1

            force = cfg.spring_strength * (dist - cfg.spring_length)
            fx = (dx / dist) * force
            fy = (dy / dist) * force

            forces[a.id][0] += fx
            forces[a.id][1] += fy
            forces[b.id][0] -= fx
            forces[b.id][1] -= fy

        # Center gravity
        for nd in nodes:
            dx = cx - nd.x
            dy = cy - nd.y
            forces[nd.id][0] += dx * cfg.gravity
            forces[nd.id][1] += dy * cfg.gravity

        # Apply forces with temperature cooling
        for nd in nodes:
            fx, fy = forces[nd.id]
            nd.vx = (nd.vx + fx) * cfg.damping * temperature
            nd.vy = (nd.vy + fy) * cfg.damping * temperature

            speed = math.sqrt(nd.vx**2 + nd.vy**2)
            max_v = cfg.max_velocity * temperature
            if speed > max_v:
                nd.vx = (nd.vx / speed) * max_v
                nd.vy = (nd.vy / speed) * max_v

            nd.x += nd.vx
            nd.y += nd.vy

            # Keep within bounds with padding
            pad = 3
            nd.x = max(pad, min(width - pad - 1, nd.x))
            nd.y = max(pad, min(height - pad - 1, nd.y))

    return nodes


# ── Braille sub-pixel rendering ──
# Each braille character is a 2x4 dot grid.
# We use a high-res buffer (2x width, 4x height) and map to braille.

BRAILLE_BASE = 0x2800
BRAILLE_DOTS = [
    [0x01, 0x08],  # row 0: dots 1,4
    [0x02, 0x10],  # row 1: dots 2,5
    [0x04, 0x20],  # row 2: dots 3,6
    [0x40, 0x80],  # row 3: dots 7,8
]


class BrailleCanvas:
    """High-resolution canvas using Braille characters for sub-pixel rendering."""

    def __init__(self, char_width: int, char_height: int):
        self.char_width = char_width
        self.char_height = char_height
        self.pixel_width = char_width * 2
        self.pixel_height = char_height * 4
        # Pixel buffer
        self._pixels: set[tuple[int, int]] = set()
        # Color per character cell
        self._colors: dict[tuple[int, int], str] = {}
        # Override characters (for node symbols)
        self._char_override: dict[
            tuple[int, int], tuple[str, str]
        ] = {}  # (char, color)
        # Labels
        self._labels: list[tuple[int, int, str, str]] = []  # (cx, cy, text, color)

    def set_pixel(self, px: int, py: int, color: str | None = None) -> None:
        """Set a sub-pixel."""
        if 0 <= px < self.pixel_width and 0 <= py < self.pixel_height:
            self._pixels.add((px, py))
            if color:
                cx, cy = px // 2, py // 4
                self._colors[(cx, cy)] = color

    def draw_line(
        self, x0: float, y0: float, x1: float, y1: float, color: str = "dim #555555"
    ) -> None:
        """Draw a line using sub-pixels (Bresenham's algorithm on the pixel grid)."""
        # Convert graph coords to pixel coords
        px0 = round(x0 * 2)
        py0 = round(y0 * 4)
        px1 = round(x1 * 2)
        py1 = round(y1 * 4)

        dx = abs(px1 - px0)
        dy = abs(py1 - py0)
        sx = 1 if px0 < px1 else -1
        sy = 1 if py0 < py1 else -1
        err = dx - dy

        steps = 0
        max_steps = (dx + dy + 1) * 2

        while steps < max_steps:
            steps += 1
            self.set_pixel(px0, py0, color)

            if px0 == px1 and py0 == py1:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                px0 += sx
            if e2 < dx:
                err += dx
                py0 += sy

    def set_node(self, x: float, y: float, char: str, color: str) -> None:
        """Place a node character at graph coordinates."""
        cx = round(x)
        cy = round(y)
        if 0 <= cx < self.char_width and 0 <= cy < self.char_height:
            self._char_override[(cx, cy)] = (char, color)

    def add_label(self, x: float, y: float, text: str, color: str) -> None:
        """Add a text label near a position."""
        cx = round(x)
        cy = round(y)
        self._labels.append((cx, cy, text, color))

    def render(self) -> list[list[tuple[str, str | None]]]:
        """Render to a grid of (character, color) tuples."""
        grid: list[list[tuple[str, str | None]]] = [
            [(" ", None) for _ in range(self.char_width)]
            for _ in range(self.char_height)
        ]

        # First pass: render braille from pixels
        for cy in range(self.char_height):
            for cx in range(self.char_width):
                code = BRAILLE_BASE
                has_dots = False
                for row in range(4):
                    for col in range(2):
                        px = cx * 2 + col
                        py = cy * 4 + row
                        if (px, py) in self._pixels:
                            code |= BRAILLE_DOTS[row][col]
                            has_dots = True
                if has_dots:
                    color = self._colors.get((cx, cy), "dim #555555")
                    grid[cy][cx] = (chr(code), color)

        # Second pass: overlay node characters
        for (cx, cy), (char, color) in self._char_override.items():
            if 0 <= cx < self.char_width and 0 <= cy < self.char_height:
                grid[cy][cx] = (char, color)

        # Third pass: overlay labels
        for lx, ly, text, color in self._labels:
            # Try to place label to the right of the node
            start_x = lx + 2
            if start_x + len(text) >= self.char_width:
                start_x = lx - len(text) - 1
            if start_x < 0:
                start_x = 0

            if 0 <= ly < self.char_height:
                for i, ch in enumerate(text):
                    px = start_x + i
                    if 0 <= px < self.char_width:
                        # Only place on empty or braille cells, not on nodes
                        existing = grid[ly][px]
                        if existing[0] == " " or (
                            ord(existing[0]) >= BRAILLE_BASE
                            and ord(existing[0]) <= BRAILLE_BASE + 0xFF
                        ):
                            grid[ly][px] = (ch, color)

        return grid


def search_nodes(
    nodes: list[GraphNode],
    query: str,
    max_results: int = 20,
) -> list[GraphNode]:
    """Fuzzy search nodes by label/id. Returns matches sorted by relevance."""
    if not query:
        return []

    query_lower = query.lower()
    scored: list[tuple[float, GraphNode]] = []

    for node in nodes:
        label_lower = node.label.lower()
        id_lower = node.id.lower()

        # Exact match on label
        if label_lower == query_lower:
            scored.append((0.0, node))
            continue

        # Starts with query
        if label_lower.startswith(query_lower):
            scored.append((1.0, node))
            continue

        # Contains query as substring
        idx = label_lower.find(query_lower)
        if idx >= 0:
            scored.append((2.0 + idx * 0.01, node))
            continue

        # Check id (path) contains query
        idx = id_lower.find(query_lower)
        if idx >= 0:
            scored.append((3.0 + idx * 0.01, node))
            continue

        # Fuzzy: check if all query chars appear in order
        qi = 0
        penalty = 0.0
        for _ci, ch in enumerate(label_lower):
            if qi < len(query_lower) and ch == query_lower[qi]:
                qi += 1
            else:
                penalty += 0.1
        if qi == len(query_lower):
            scored.append((4.0 + penalty, node))

    scored.sort(key=lambda x: x[0])
    return [node for _, node in scored[:max_results]]


@dataclass
class RenderedGraph:
    """Result of rendering a graph, including markup and node positions."""

    markup: str
    node_positions: dict[str, tuple[float, float]]  # node_id -> (x, y)
    node_map: dict[str, GraphNode]  # node_id -> GraphNode


def render_graph(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    width: int,
    height: int,
    dir_colors: dict[str, str],
    selected_id: str | None = None,
    highlight_ids: set[str] | None = None,
    show_labels: bool = True,
    fullscreen: bool = False,
) -> RenderedGraph:
    """Render the graph to a Rich markup string using Braille sub-pixel edges.

    Returns a RenderedGraph with the markup string and node position data.
    """
    if not nodes:
        return RenderedGraph(
            markup="[dim]No files found. Add files to media/, notes/, etc.[/dim]",
            node_positions={},
            node_map={},
        )

    # Run layout
    layout_nodes = force_directed_layout(nodes, edges, width, height)
    node_map = {n.id: n for n in layout_nodes}

    # Build adjacency
    adjacency: dict[str, set[str]] = {}
    for e in edges:
        adjacency.setdefault(e.source, set()).add(e.target)
        adjacency.setdefault(e.target, set()).add(e.source)

    # Create braille canvas
    canvas = BrailleCanvas(width, height)

    # Determine which nodes are highlighted (search results or neighbors of selected)
    hl = highlight_ids or set()

    # Build set of nodes whose edges should be highlighted
    highlighted_edge_nodes = set()
    if selected_id:
        highlighted_edge_nodes.add(selected_id)
    if hl:
        highlighted_edge_nodes.update(hl)

    # Draw edges — highlight edges connected to selected/highlighted nodes
    highlight_edge_color = "bold #FFD700"  # gold for highlighted edges
    dimmed_edge_color = "dim #2a2a2a"
    _default_colors = {
        "reference": "dim #444444",
        "semantic": "dim #2d4a7a",  # indigo
        "name": "dim #2d5a3a",  # dark green — filename-pattern matches
    }

    for edge in edges:
        if edge.source not in node_map or edge.target not in node_map:
            continue
        src = node_map[edge.source]
        tgt = node_map[edge.target]
        default_color = _default_colors.get(
            edge.edge_type, _default_colors["reference"]
        )

        if highlighted_edge_nodes:
            src_hl = edge.source in highlighted_edge_nodes
            tgt_hl = edge.target in highlighted_edge_nodes
            if src_hl or tgt_hl:
                canvas.draw_line(src.x, src.y, tgt.x, tgt.y, highlight_edge_color)
            else:
                canvas.draw_line(src.x, src.y, tgt.x, tgt.y, dimmed_edge_color)
        else:
            canvas.draw_line(src.x, src.y, tgt.x, tgt.y, default_color)

    # Draw nodes
    for node in layout_nodes:
        degree = len(adjacency.get(node.id, set()))
        color = dir_colors.get(node.directory, dir_colors.get("other", "#6b6560"))

        # Dim non-highlighted nodes when there's an active highlight set
        is_highlighted = node.id in hl or node.id == selected_id
        if hl and not is_highlighted:
            color = "dim #3a3a3a"

        if node.id == selected_id:
            char = "◉"
            color = "bold #ffffff"
        elif node.id in hl and hl:
            char = "◈"
            color = "bold " + dir_colors.get(
                node.directory, dir_colors.get("other", "#6b6560")
            )
        elif degree >= 5:
            char = "⬢"
        elif degree >= 3:
            char = "◆"
        else:
            # All nodes with any connections (degree >= 1) AND isolated nodes
            # use filled circle to ensure colored visibility
            char = "●"

        canvas.set_node(node.x, node.y, char, color)

    # Add labels — always show file names for all nodes
    if show_labels:
        for node in layout_nodes:
            degree = len(adjacency.get(node.id, set()))
            is_highlighted = node.id in hl or node.id == selected_id

            color = dir_colors.get(node.directory, dir_colors.get("other", "#6b6560"))
            label = node.label
            max_len = 14 if fullscreen else 10
            if len(label) > max_len:
                label = label[: max_len - 1] + "…"

            if is_highlighted:
                color = "bold " + color
            elif degree < 1:
                color = f"dim {color}"

            # Dim labels when highlight is active but this node isn't highlighted
            if hl and not is_highlighted:
                color = "dim #3a3a3a"

            canvas.add_label(node.x, node.y, label, color)

    # Render canvas to Rich markup
    grid = canvas.render()
    lines = []
    for row in grid:
        parts = []
        current_color = None
        current_text = ""

        for ch, col in row:
            if col != current_color:
                if current_text:
                    if current_color:
                        parts.append(
                            f"[{current_color}]{current_text}[/{current_color}]"
                        )
                    else:
                        parts.append(current_text)
                current_color = col
                current_text = ch
            else:
                current_text += ch

        if current_text:
            if current_color:
                parts.append(f"[{current_color}]{current_text}[/{current_color}]")
            else:
                parts.append(current_text)

        lines.append("".join(parts).rstrip())

    # Remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    # Build node position and map data
    node_positions = {n.id: (n.x, n.y) for n in layout_nodes}
    node_map_out = {n.id: n for n in layout_nodes}

    return RenderedGraph(
        markup="\n".join(lines),
        node_positions=node_positions,
        node_map=node_map_out,
    )


def build_graph_from_project_data(
    graph_data,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Convert project graph data to our internal format."""
    nodes = []
    for node in graph_data.nodes:
        nodes.append(
            GraphNode(
                id=node.id,
                label=node.name,
                directory=node.directory,
                size_bytes=node.size_bytes,
            )
        )

    edges = []
    for edge in graph_data.edges:
        edges.append(
            GraphEdge(
                source=edge.source,
                target=edge.target,
                edge_type=getattr(edge, "edge_type", "reference"),
            )
        )

    return nodes, edges
