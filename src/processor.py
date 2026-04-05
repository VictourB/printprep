# src/processor.py
import numpy as np
import tifffile
from PIL import Image
from pathlib import Path

# Standardized Canvas Sizes at 300 DPI
CUP_PRESETS = {
    "16oz": {"width": 2700, "height": 1800},
    "20oz": {"width": 2850, "height": 2100}
}


class JobProcessor:
    def __init__(self, base_path, specs):
        self.base_path = Path(base_path)
        self.specs = specs

        # Determine dimensions based on the ticket's specs
        size_key = self.specs.get("size", "20oz")
        self.dimensions = CUP_PRESETS.get(size_key, CUP_PRESETS["20oz"])

    def generate_proof(self, source_image_path, logo_path=None):
        """Generates a low-resolution JPG composite for client approval."""
        print("Generating digital proof...")
        try:
            # 1. Load and resize the main artwork
            with Image.open(source_image_path) as img:
                # Convert to RGB for JPG saving
                img = img.convert("RGB")
                img = img.resize((self.dimensions["width"], self.dimensions["height"]), Image.Resampling.LANCZOS)

            # 2. Overlay partner logo if provided (e.g., Pepsi/Monster)
            if logo_path and Path(logo_path).exists():
                with Image.open(logo_path) as logo:
                    logo = logo.convert("RGBA")
                    # Example placement: Top Right Corner
                    logo.thumbnail((500, 500))
                    position = (self.dimensions["width"] - logo.width - 50, 50)
                    img.paste(logo, position, logo)

            # 3. Save to the preflight directory
            proof_path = self.base_path / "preflight" / "proof_composite.jpg"
            # Quality reduced for quick emailing/viewing
            img.save(proof_path, "JPEG", quality=75)
            print(f"Proof successfully generated at: {proof_path.name}")
            return True

        except Exception as e:
            print(f"Error generating proof: {e}")
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