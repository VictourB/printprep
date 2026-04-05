import os
from pathlib import Path


def select_partner_asset(partner_name, mode, asset_root="assets/partners"):
    partner_path = Path(asset_root) / partner_name

    if not partner_path.exists():
        print(f"Error: Partner directory '{partner_name}' not found.")
        return None

    # Filter files based on mode (CMYK or SPOT)
    # Most digital printers use _4W for 4-pass white or _CMYK for direct
    search_term = "_CMYK" if mode == "CMYK" else "_SPOT"

    matches = [f for f in partner_path.glob(f"*{search_term}*") if f.is_file()]

    if not matches:
        print(f"No assets found for {partner_name} in {mode} mode.")
        # Fallback to all files in directory if specific mode fails
        matches = list(partner_path.glob("*"))

    if len(matches) == 1:
        return matches[0]

    # Selection Menu
    print(f"\n--- Multiple assets found for {partner_name} ---")
    for i, file in enumerate(matches, 1):
        print(f"[{i}] {file.name}")

    while True:
        try:
            choice = int(input(f"Select image (1-{len(matches)}): "))
            if 1 <= choice <= len(matches):
                return matches[choice - 1]
        except ValueError:
            pass
        print("Invalid selection. Please use the number keys.")