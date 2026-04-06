import os
from pathlib import Path


def select_partner_asset(partner_name, mode, asset_root="assets/partners"):
    partner_path = Path(asset_root) / partner_name

    if partner_name == "none":
        return None

    if not partner_path.exists():
        print(f"Error: Partner directory '{partner_name}' not found.")
        return None

    # Get ALL files in the partner folder
    all_files = [f for f in partner_path.glob("*.*") if f.is_file()]

    if not all_files:
        print(f"No assets found in {partner_path}")
        return None

    # Recommendation Logic: if job is CMYK, look for "_CMYK" in filename
    search_term = f"_{mode}"

    matches = sorted(all_files, key=lambda x: search_term not in x.name)

    if len(matches) == 1:
        return matches[0]

    # Selection Menu
    print(f"\n--- Multiple assets found for {partner_name} ---")
    for i, file in enumerate(matches, 1):
        recommend = "*" if search_term in file.name else " "
        print(f"[{i}]{recommend} {file.name}")

    while True:
        try:
            choice = int(input(f"Select image (1-{len(matches)}): "))
            if 1 <= choice <= len(matches):
                return matches[choice - 1]
        except ValueError:
            pass
        print("Invalid selection. Please use the number keys.")