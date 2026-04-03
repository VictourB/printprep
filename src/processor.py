from PIL import Image, ImageOps
import json
from pathlib import Path
import numpy as np
import tifffile


class PrintProcessor:
    def __init__(self, job_path):
        self.job_path = Path(job_path)
        with open(self.job_path / "ticket.json", "r") as f:
            self.ticket = json.load(f)

    def process(self):
        # 1. Access Preflight Directory
        preflight_dir = self.job_path / "preflight"

        # 2. & 3. Create Canvas and Determine Sizes (Using Preset Logic)
        # Assuming 20oz preset: 3000x2000px for example
        canvas_width, canvas_height = 3000, 2000
        canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        # Load Client Image
        raw_image_path = list((self.job_path / "raw").glob("*"))[0]
        client_img = Image.open(raw_image_path).convert("RGBA")

        # 4. Placement Logic
        # Calculate centers
        front_center = int(canvas_width * 0.25)
        back_center = int(canvas_width * 0.75)
        vertical_center = int(canvas_height * 0.5)

        # Place Client Logo (1/4 Width)
        client_img.thumbnail((800, 800))  # Placeholder resizing
        c_w, c_h = client_img.size
        canvas.paste(client_img, (front_center - c_w // 2, vertical_center - c_h // 2), client_img)

        # Place Partner Logo (3/4 Width) if exists
        partner_logo_name = self.ticket['specs'].get('partner_logo')
        if partner_logo_name:
            logo_path = Path(f"assets/logos/{partner_logo_name}.png")
            if logo_path.exists():
                partner_img = Image.open(logo_path).convert("RGBA")
                partner_img.thumbnail((600, 600))
                p_w, p_h = partner_img.size
                canvas.paste(partner_img, (back_center - p_w // 2, vertical_center - p_h // 2), partner_img)

        # 6. Trim Excess Transparent Space (Autocrop)
        bbox = canvas.getbbox()
        if bbox:
            canvas = canvas.crop(bbox)

        # 5. Create Spot Channels (Alpha mask for White/Varnish)
        # In digital printing, a 'White' channel is often an Alpha band
        # We ensure it exists for all non-transparent pixels
        full_stack = self.apply_spot_channels(canvas)

        output_path = self.job_path / "output" / f"{self.ticket['job_id']}_final.tif"

        # Write as MULTICHANNEL (Photometric 0 or 1 with ExtraSamples)
        # Most industrial RIPs recognize Photometric=0 (Min-is-White) for multichannel

        channel_names = [
            "Cyan", "Magenta", "Yellow", "Black",
            "White 1", "White 2", "White 3", "White 4"
        ]

        extra_samples = [1, 1, 1, 1]

        tifffile.imwrite(
            output_path,
            full_stack,
            photometric=5,
            planarconfig='separate',
            extrasamples=extra_samples,
            compression='lzw',
            metadata={
                'Description': f"Channels: {', '.join(channel_names)}",
                'Labels': channel_names
            }
        )
        return output_path

    def apply_spot_channels(self, canvas):
        # 1. Convert canvas to CMYK to get the ink data
        cmyk_image = canvas.convert("CMYK")
        cmyk_data = np.array(canvas.convert("CMYK")).astype('uint8')

        # 2. Generate White underbase mask (Non-transparent pixels)
        # We invert this because in Multichannel TIFFs, 255 usually = 100% ink
        alpha_mask = np.array(canvas.getchannel('A')).astype('uint8')

        mask_boolean = alpha_mask > 0
        for i in range(4):
            channel = cmyk_data[:, :, i]
            channel[~mask_boolean] = 0
            cmyk_data[:, :, i] = channel

        # Ensure the alpha mask itself is clean
        alpha_mask[~mask_boolean] = 0

        # 4. Stack: [C, M, Y, K, W1, W2, W3, W4]
        white_channels = [alpha_mask] * 4
        all_channels = [cmyk_data[:, :, i] for i in range(4)] + white_channels

        # Use axis=0 for 'separate' planar configuration
        full_stack = np.stack(all_channels, axis=0)  # Shape: (8, H, W)

        return full_stack



