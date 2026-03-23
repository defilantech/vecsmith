"""SVG post-processing: cleanup, viewBox normalization, coordinate rounding."""

import logging
import re
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# Register namespaces so ET doesn't mangle them
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def optimize_svg(svg_str: str, precision: int = 2) -> str:
    """Clean up and optimize an SVG string.

    - Ensures proper viewBox attribute
    - Rounds coordinates to reduce file size
    - Removes empty groups and unnecessary attributes
    - Strips XML declaration and comments

    Args:
        svg_str: Raw SVG string (e.g., from vtracer).
        precision: Decimal places for coordinate rounding.

    Returns:
        Cleaned SVG string.
    """
    # Strip XML declaration if present
    svg_str = re.sub(r'<\?xml[^?]*\?>\s*', '', svg_str)

    # Strip comments
    svg_str = re.sub(r'<!--.*?-->', '', svg_str, flags=re.DOTALL)

    try:
        root = ET.fromstring(svg_str)
    except ET.ParseError:
        logger.warning("Failed to parse SVG as XML, returning as-is")
        return svg_str

    # Ensure viewBox is set
    _ensure_viewbox(root)

    # Round numeric values in path data and attributes
    _round_coordinates(root, precision)

    # Remove empty groups
    _remove_empty_groups(root)

    # Serialize back to string
    output = ET.tostring(root, encoding="unicode")

    # Add XML declaration
    output = '<?xml version="1.0" encoding="UTF-8"?>\n' + output

    logger.info(
        "Optimized SVG: %d -> %d bytes (%.0f%% of original)",
        len(svg_str),
        len(output),
        100 * len(output) / max(len(svg_str), 1),
    )
    return output


def _ensure_viewbox(root: ET.Element) -> None:
    """Add viewBox if missing, based on width/height attributes."""
    if root.get("viewBox"):
        return

    width = root.get("width", "").replace("px", "")
    height = root.get("height", "").replace("px", "")

    if width and height:
        try:
            w = float(width)
            h = float(height)
            root.set("viewBox", f"0 0 {w:g} {h:g}")
        except ValueError:
            pass


def _round_number(match: re.Match, precision: int) -> str:
    """Round a single numeric match."""
    try:
        val = float(match.group(0))
        rounded = round(val, precision)
        # Use 'g' format to strip trailing zeros
        return f"{rounded:.{precision}f}".rstrip('0').rstrip('.')
    except ValueError:
        return match.group(0)


def _round_coordinates(root: ET.Element, precision: int) -> None:
    """Round numeric values in path 'd' attributes and transform attributes."""
    number_re = re.compile(r'-?\d+\.\d{3,}')

    for elem in root.iter():
        # Round path data
        d = elem.get("d")
        if d:
            elem.set("d", number_re.sub(lambda m: _round_number(m, precision), d))

        # Round transform values
        transform = elem.get("transform")
        if transform:
            elem.set(
                "transform",
                number_re.sub(lambda m: _round_number(m, precision), transform),
            )

        # Round numeric style properties (e.g., stroke-width)
        for attr in ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
                      "width", "height", "stroke-width", "opacity"):
            val = elem.get(attr)
            if val:
                try:
                    num = float(val)
                    rounded = round(num, precision)
                    elem.set(attr, f"{rounded:g}")
                except ValueError:
                    pass


def _remove_empty_groups(root: ET.Element) -> None:
    """Recursively remove <g> elements with no children."""
    g_tag = f"{{{SVG_NS}}}g" if root.tag.startswith("{") else "g"

    for elem in list(root):
        _remove_empty_groups(elem)

    for elem in list(root):
        if elem.tag == g_tag and len(elem) == 0 and not elem.text:
            root.remove(elem)
