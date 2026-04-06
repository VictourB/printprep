# src/processor.py
import numpy as np
import tifffile
from PIL import Image
from pathlib import Path
from config import *

class JobProcessor:
    def __init__(self, base_path, specs):
        self.base_path = Path(base_path)
        self.specs = specs

        # Determine dimensions based on the ticket's specs
        size_key = self.specs.get("cup_size", "20oz")
        self.dimensions = CUP_PRESETS.get(size_key, CUP_PRESETS["20oz"])

    def generate_proof(self, source_image_path, logo_path=None):
        """Generates a low-resolution JPG composite for client approval."""
        print("Generating digital proof...")
        try:
            # 1. Select Template
            color = self.specs.get("cup_color", "clear").lower()
            template_path = Path(f"assets/templates/{color}_cup_base.png")
            if not template_path.exists():
                template_path = Path("assets/templates/clear_cup_base.png")

            with Image.open(template_path).convert("RGBA") as base:
                bw, bh = base.size

                # Define Center Points
                front_center_x = int(bw * 0.25)
                back_center_x = int(bw * 0.75)
                center_y = int(bh * 0.35)

                # 2. Composite Client Image (Front)
                with Image.open(source_image_path).convert("RGBA") as artwork:
                    # Scale artwork to fit comfortably (e.g., 40% of template height)
                    art_h = int(bh * 0.3)
                    art_w = int(artwork.width * (art_h / artwork.height))
                    artwork = artwork.resize((art_w, art_h), Image.Resampling.LANCZOS)

                    # Calculate Top-Left corner to keep it centered at 25%
                    art_pos = (front_center_x - (art_w // 2), center_y - (art_h // 2))
                    base.paste(artwork, art_pos, artwork)

                # 3. Composite Partner Logo (Back - Optional)
                if logo_path and Path(logo_path).exists():
                    with Image.open(logo_path).convert("RGBA") as logo:
                        # Scale logo slightly smaller than main art
                        logo_h = int(bh * 0.25)
                        logo_w = int(logo.width * (logo_h / logo.height))
                        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

                        # Calculate Top-Left corner to keep it centered at 75%
                        logo_pos = (back_center_x - (logo_w // 2), center_y - (logo_h // 2))
                        base.paste(logo, logo_pos, logo)

                # 4. Save Final
                output_path = self.base_path / "preflight" / "customer_proof.jpg"
                base.convert("RGB").save(output_path, "JPEG", quality=90)
                return True

        except Exception as e:
            print(f"Error during proof generation: {e}")
            return False

    def generate_production_tiff(self, source_image_path):
        """
        Scaffolds the 8-channel Multichannel TIFF (CMYK + 4 White Spots).
        Requires 'tifffile' for explicit extra samples tagging.
        """
        print("Initializing 8-Channel RIP Output...")
        try:
            w, h = self.dimensions["width"], self.dimensions["height"]

            # --- PHASE 1: Scaffolding the Image Arrays ---
            # In production, you would map the actual RGB pixels to CMYK using an ICC profile.
            # Here, we initialize empty arrays representing the exact data structure the printer needs.

            # 1. CMYK Base (4 Channels, 8-bit integers)
            cmyk_data = np.zeros((h, w, 4), dtype=np.uint8)

            # 2. Spot Channels (4 White Underbase Channels)
            # The 1-pixel choke logic will eventually be applied to these arrays
            spot_data = np.zeros((h, w, 4), dtype=np.uint8)

            # Combine into a single 8-channel volume
            final_image_data = np.concatenate((cmyk_data, spot_data), axis=-1)

            # --- PHASE 2: TIFF Metadata Writing ---
            output_path = self.base_path / "output" / "production_ready.tif"

            # Write using tifffile to strictly enforce the Planar/Separated layout
            tifffile.imwrite(
                output_path,
                final_image_data,
                photometric='separated',  # Photometric Interpretation 5 (CMYK)
                compression='lzw',  # Lossless compression for industrial printers
                extrasamples=[1, 1, 1, 1],  # 4 Unassociated Alpha channels (Spot colors)
                metadata={'Resolution': (300.0, 300.0)}
            )
            print(f"Production TIFF saved: {output_path.name}")
            return True

        except Exception as e:
            print(f"Error generating production TIFF: {e}")
            return False