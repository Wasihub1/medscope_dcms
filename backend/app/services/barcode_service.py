"""
Pure-Python Code 128 Barcode Generator (Zero Dependencies).
Generates standards-compliant, high-precision SVG vector barcodes
tailored for diagnostic-center specimen labels (50mm x 25mm / 50mm x 30mm).
"""
from typing import List

# Code 128 Bar-Space Patterns (107 patterns: 0..102 data/control, 103-105 start, 106 stop)
# Each number is the width of alternate bars and spaces (sum = 11 modules, except stop = 13 modules)
CODE128_PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131",
    "211412",  # 103: Start A
    "211214",  # 104: Start B (ASCII 32..126)
    "211232",  # 105: Start C
    "2331112"  # 106: Stop (13 modules)
]

START_B = 104
STOP = 106


def encode_code128_b(data: str) -> List[int]:
    """Encodes ASCII string into Code 128 Character Set B symbols with checksum."""
    values = [START_B]
    checksum = START_B

    for i, ch in enumerate(data, start=1):
        code_val = ord(ch) - 32
        if code_val < 0 or code_val > 95:
            # Fallback for characters outside printable ASCII 32..127
            code_val = ord("?") - 32
        values.append(code_val)
        checksum += i * code_val

    checksum_symbol = checksum % 103
    values.append(checksum_symbol)
    values.append(STOP)
    return values


def generate_code128_svg(
    data: str,
    module_width: float = 1.4,
    height: float = 40.0,
    include_text: bool = True,
    quiet_zone: float = 10.0,
) -> str:
    """
    Renders pure vector SVG string for the specified barcode data.
    Designed for 200/300 DPI thermal barcode printer output.
    """
    clean_data = (data or "").strip()
    if not clean_data:
        clean_data = "SAMPLE"

    symbol_values = encode_code128_b(clean_data)

    # Convert symbols to alternating bar and space widths
    bars: List[tuple[float, float]] = []  # (x, width)
    current_x = quiet_zone

    for symbol_idx in symbol_values:
        pattern = CODE128_PATTERNS[symbol_idx]
        is_bar = True
        for digit in pattern:
            width = int(digit) * module_width
            if is_bar:
                bars.append((current_x, width))
            current_x += width
            is_bar = not is_bar

    total_width = current_x + quiet_zone
    total_height = height + (14 if include_text else 0)

    rects = "".join(
        f'<rect x="{round(x, 2)}" y="0" width="{round(w, 2)}" height="{height}" fill="#000000" />'
        for x, w in bars
    )

    text_element = ""
    if include_text:
        text_element = (
            f'<text x="{round(total_width / 2, 2)}" y="{round(height + 11, 2)}" '
            f'text-anchor="middle" font-family="monospace" font-size="9" '
            f'font-weight="bold" fill="#000000">{clean_data}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {round(total_width, 2)} {round(total_height, 2)}" '
        f'width="{round(total_width, 2)}" height="{round(total_height, 2)}" style="background-color: #ffffff;">'
        f'{rects}'
        f'{text_element}'
        f'</svg>'
    )
    return svg

