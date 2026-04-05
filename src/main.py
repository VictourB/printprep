import argparse
import sys, json
import shutil
from pathlib import Path
from ticketing import PrintPrepJob, CASE_MAP, DEFAULT_CASE_SIZE
from processor import JobProcessor

def main():
    parser = argparse.ArgumentParser(description="PrintPrep: Workshop Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands", required=True)

    # --- INITIALIZE ---
    init_p = subparsers.add_parser("initialize", help="Initialize a new job. Setup folders/ticket.")
    init_p.add_argument("job_id", help="The unique identifier for the job (e.g., 2026-A01)")
    init_p.add_argument("client", help="The name of the client/customer")
    init_p.add_argument("qty", type=int, help="Total quantity in cases to print")
    init_p.add_argument("--type", default="digital_print", choices=["digital_print", "proof", "sample"])

    init_p.add_argument("--size", choices=["12oz", "16oz", "20oz", "24oz", "32oz"], default="20oz",
                            help="The cup size preset for the cylindrical wrap")
    init_p.add_argument("--cup_color", default="clear",
                            help="The base color of the cup")
    init_p.add_argument("--mode", choices=["CMYK", "SPOT"], default="SPOT",
                            help="The ink configuration (Full CMYK or Single-color)")

    init_p.add_argument("--image", type=Path, required=True,
                            help="Path to the primary client image asset")
    init_p.add_argument("--logo", choices=["pepsi", "coke", "drpepper"],
                            help="Optional partner logo to include in the composite")
    init_p.add_argument("--units", action="store_true", help="Treat qty as individual cups instead of cases")

    # --- STATUS ---
    stat_p = subparsers.add_parser("status", help="View jobs or ticket info")
    stat_p.add_argument("target", nargs='?', help="Job ID or Status (e.g., in_progress)")

    # --- UPDATE ---
    up_p = subparsers.add_parser("update", help="Change ticket information")
    up_p.add_argument("job_id", help="The ID of the job to update")
    up_p.add_argument("value", nargs='?', help="Number to add to completed case count OR a new value for a key")
    up_p.add_argument("--scrap", type=int, default=0, help="Number of misprints/waste")
    up_p.add_argument("--key", help="The specific ticket key to change (e.g., specs, notes, deadline)")
    up_p.add_argument("--op", help="Operator initials")
    up_p.add_argument("--units", action="store_true", help="Treat value as individual cups")

    # --- PROCESS ---
    proc_p = subparsers.add_parser("process", help="Run image processing")
    proc_p.add_argument("job_id", help="The ID of the job to process")
    proc_p.add_argument("--proof", action="store_true", help="Generate a digital proof composite")

    # --- DELETE ---
    del_p = subparsers.add_parser("delete", help="Permanently remove a job and its folders")
    del_p.add_argument("job_id", help="The Job ID to delete")
    del_p.add_argument("--force", action="store_true", help="Skip confirmation prompt")


    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    execute_command(args)

def format_qty(cups, case_size):
    cases = cups // case_size
    rem = cups % case_size
    return f"{cases}cs {rem}u" if rem > 0 else f"{cases}cs"


def display_dashboard(display_list):
    print(f"\n{'JOB ID':<12} | {'CLIENT':<15} | {'STATUS':<12} | {'PROGRESS':<22} | {'SPP':<5} | {'ETM':<8} | {'DEADLINE'}")
    print("-" * 95)

    for t in display_list:
        qty = t.get("quantity", {})
        specs = t.get("specs", {})
        c_size = specs.get("case_size", 72)
        spp = t.get("SPP", 45)

        comp = qty.get('completed', 0)
        total = qty.get('total', 0)

        # Formatting for cases/units
        def fmt(c): return f"{c // c_size}c {c % c_size}u" if c % c_size else f"{c // c_size}cs"

        # Combine Progress into one string to pad it as a single block
        prog_combined = f"{fmt(comp)}/{fmt(total)}"

        spp = int(spp)

        # Calculate ETM based on remaining units
        remaining_units = max(0, total - comp)
        etm_mins = (remaining_units * spp) // 60
        etm_str = f"{etm_mins}m" if remaining_units > 0 else "--"

        deadline = t.get("timestamps", {}).get("deadline", "N/A")[:10]

        print(
            f"{t['job_id']:<12} | {t['client_name'][:15]:<15} | {t['status'].upper():<12} | {prog_combined:<22} | {spp:<6} | {etm_str:<8} | {deadline}")
    print(f"\nActive Workload: {len(display_list)} jobs.\n")

def execute_command(args):
    # Logic for finding and loading job folders remains as previously established
    # Use glob(*_{args.job_id}_*) to locate the base_path on Windows
    if args.command == "process":
        # 1. Locate the job folder
        root_jobs = Path("jobs")
        target_folders = list(root_jobs.glob(f"*_{args.job_id}_*"))

        if not target_folders:
            print(f"Error: No folder found for Job ID {args.job_id}")
            return

        folder_path = target_folders[0]

        # 2. Read the ticket to get the specs
        ticket_file = folder_path / "ticket.json"
        with open(ticket_file, 'r') as f:
            data = json.load(f)
            specs = data.get("specs", {})

        # 3. Find the raw source image
        raw_dir = folder_path / "raw"
        raw_files = list(raw_dir.glob("*.*"))
        if not raw_files:
            print("Error: No source image found in the 'raw' directory.")
            return

        source_image = raw_files[0]  # Grab the first file in raw/

        # 4. Initialize Processor
        processor = JobProcessor(base_path=folder_path, specs=specs)

        # 5. Execute requested action
        if args.proof:
            # Assuming you pass a logo path via args, or leave None
            processor.generate_proof(source_image)
            # Automatically update the ticket status to note a proof was made
            job = PrintPrepJob(args.job_id, data["client_name"], 0)
            job.base_path = folder_path
            job.update_ticket(key="status", value="proof_generated")
        else:
            # Standard dialog/interactive mode
            run_prod = input("Generate 8-channel production TIFF? (y/n): ")
            if run_prod.lower() == 'y':
                processor.generate_production_tiff(source_image)

    elif args.command == "initialize":
        try:
            print(f"--- Initializing Job: {args.job_id} for {args.client} ---")

            case_size = CASE_MAP.get(args.size, DEFAULT_CASE_SIZE)
            total_cups = args.qty * case_size

            # 1. Initialize the Job Object
            job = PrintPrepJob(args.job_id, args.client, total_cups, units=args.units)
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
            if args.image and args.image.exists():
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

        # If no arguments at all, show ticket. Otherwise, update.
        if args.value is None and args.key is None and args.op is None:
            job.display_ticket()
        else:
            # We assume scrap is passed as 0 via argparse default
            # but you can add init_p.add_argument("--scrap", type=int, default=0)
            scrap_val = getattr(args, 'scrap', 0)
            job.update_ticket(
                value=args.value,
                key=args.key,
                operator=args.op,
                scrap=scrap_val,
                units=args.units
            )
    elif args.command == "status":
        root_jobs = Path("jobs")
        all_tickets = PrintPrepJob.get_all_jobs()

        # Behavior 1: Detailed Job View (Exact Match for Job ID)
        if args.target:
            target_folders = list(root_jobs.glob(f"*_{args.target}_*"))
            if target_folders:
                # Reconstruct and display specific ticket
                job = PrintPrepJob(args.target, "ViewOnly", 0)
                job.base_path = target_folders[0]
                job.display_ticket()
                return

        # Behavior 2: Filtered or Global Overview
        # Determine if 'target' is a status filter (e.g., 'finished', 'in_progress')
        valid_statuses = ["initialized", "in_progress", "on_hold", "cancelled", "finished"]
        filter_status = args.target if args.target in valid_statuses else None

        # Filter out finished jobs unless specifically requested
        display_list = []
        for t in all_tickets:
            completed = t.get("quantity", {}).get("completed", 0)
            total = t.get("quantity", {}).get("total", 0)

            if completed >= total and total > 0:
                t["status"] = "finished"
            elif completed > 0:
                t["status"] = "in_progress"
            else:
                t["status"] = "initialized"

            if filter_status:
                if t["status"] == filter_status:
                    display_list.append(t)
            elif t["status"] != "finished":  # Default: show only active work
                display_list.append(t)

        # Sort by deadline (earliest first)
        display_list.sort(key=lambda x: x["timestamps"]["deadline"])

        display_dashboard(display_list)
    elif args.command == "delete":
        # Find the job folder
        target_folders = list(Path("jobs").glob(f"*_{args.job_id}_*"))
        if not target_folders:
            print(f"Error: Job {args.job_id} not found.")
            return

        target_path = target_folders[0]

        # Security Check
        if not args.force:
            confirm = input(f"Are you sure you want to PERMANENTLY DELETE job {args.job_id}? (y/N): ")
            if confirm.lower() != 'y':
                print("Deletion cancelled.")
                return

        try:
            shutil.rmtree(target_path)
            print(f"Successfully deleted Job {args.job_id} and all associated files.")
        except Exception as e:
            print(f"Error during deletion: {e}")

if __name__ == "__main__":
    main()