import sys
from pathlib import Path
from processor import PrintProcessor


def run_processing_task(job_id, root_dir="jobs"):
    """Locates a job by ID and runs the PrintProcessor logic."""
    # Find the folder that starts with the date and contains the job_id
    job_folders = list(Path(root_dir).glob(f"*_{job_id}_*"))

    if not job_folders:
        print(f"Error: No job folder found for ID '{job_id}'.")
        return

    job_path = job_folders[0]
    print(f"--- Processing Job: {job_id} ---")

    try:
        processor = PrintProcessor(job_path)
        output_file = processor.process()
        print(f"Success! RIP-ready file created at: {output_file}")
    except Exception as e:
        print(f"Processing failed: {e}")

def run_update_task(job_id, root_dir="jobs"):
    """Locates a job by ID and runs the update logic."""
    # Find the folder that starts with the date and contains the job_id
    job_folders = list(Path(root_dir).glob(f"*_{job_id}_*"))

    if not job_folders:
        print(f"Error: No job folder found for ID '{job_id}'.")
        return

    job_path = job_folders[0]
    print(f"--- Updating Job: {job_id} ---")

    try:
        processor = PrintProcessor(job_path)
        output_file = processor.process()
        print(f"Success! RIP-ready file created at: {output_file}")
    except Exception as e:
        print(f"Processing failed: {e}")