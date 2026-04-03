import argparse
import sys
import shutil
from pathlib import Path
from ticketing import PrintPrepJob
import actions


def main():
    parser = argparse.ArgumentParser(
        description="PrintPrep: Digital Printing Job Initialization & Automation"
    )
    # Add this to your existing main.py argparse setup
    subparsers = parser.add_subparsers(dest="command", help="Commands", required=True)

    new_parser = subparsers.add_parser("new", help="Initialize a new job")
    # Required Arguments
    new_parser.add_argument("job_id", help="The unique identifier for the job (e.g., 2026-A01)")
    new_parser.add_argument("client", help="The name of the client/customer")
    new_parser.add_argument("qty", type=int, help="Total quantity to print")

    # Specification Arguments (with defaults)
    new_parser.add_argument("--size", choices=["12oz", "16oz", "20oz", "24oz", "32oz"], default="20oz",
                        help="The cup size preset for the cylindrical wrap")
    new_parser.add_argument("--cup_color", default="clear",
                        help="The base color of the cup")
    new_parser.add_argument("--mode", choices=["CMYK", "SPOT"], default="SPOT",
                        help="The ink configuration (Full CMYK or Single-color)")

    # Asset Arguments
    new_parser.add_argument("--image", type=Path, required=True,
                        help="Path to the primary client image asset")
    new_parser.add_argument("--logo", choices=["pepsi", "coke", "drpepper"],
                        help="Optional partner logo to include in the composite")

    # 'process' command
    process_parser = subparsers.add_parser("process", help="Run the image processor on a job")
    process_parser.add_argument("job_id", help="The ID of the job to process")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update completed quantity")
    update_parser.add_argument("job_id", help="The ID of the job to update")
    update_parser.add_argument(
        "count",
        type=int,
        nargs='?',
        default=None,
        help="Number of items completed (optional)"
    )
    # Optional status flag with restricted choices
    update_parser.add_argument(
        "--status",
        choices=["in_progress", "on_hold", "cancelled", "finished"],
        help="Manually override the job status"
    )


    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.command == "process":
        actions.run_processing_task(args.job_id)
    if args.command == "new":
        # Execution Logic
        try:
            print(f"--- Initializing Job: {args.job_id} for {args.client} ---")

            # 1. Initialize the Job Object
            job = PrintPrepJob(args.job_id, args.client, args.qty)
            job.initialize_structure()

            # 2. Package Specifications
            specs = {
                "cup_size": args.size,
                "cup_color": args.cup_color,
                "print_mode": args.mode,
                "partner_logo": args.logo
            }

            # 3. Create the Ticket
            ticket_path = job.create_ticket(specs)
            print(f"Success: Ticket created at {ticket_path}")

            # 4. Handle Asset Ingestion
            # (This is where we move the --image file into the /raw/ folder)
            dest_path = job.base_path / "raw" / args.image.name
            shutil.copy(args.image, dest_path)
            print(f"Asset Logged: {args.image.name} copied to client storage.")

        except Exception as e:
            print(f"Error: Could not initialize job. {e}")
            sys.exit(1)
    elif args.command == "update":
        # Logic to find the folder since the folder name includes a date and client name
        root_jobs = Path("jobs")
        # Search for any folder containing the job_id
        target_folders = list(root_jobs.glob(f"*_{args.job_id}_*"))

        if not target_folders:
            print(f"Error: No folder found for Job ID {args.job_id}")
            return

        # Reconstruct the job object from the existing folder
        # We extract client name from the folder string for the object
        folder_path = target_folders[0]
        client_name = folder_path.name.split('_')[-1]

        # We don't need the original 'qty' here because update_progress reads the ticket
        job = PrintPrepJob(args.job_id, client_name, 0)
        job.base_path = folder_path  # Override base path to the existing one

        # If no count and no status override are provided, just display info
        if args.count is None and args.status is None:
            job.display_ticket()
        else:
            # If a count is missing but a status is provided, treat count as 0
            update_qty = args.count if args.count is not None else 0
            job.update_progress(update_qty, manual_status=args.status)


if __name__ == "__main__":
    main()