#!/usr/bin/env python

import argparse
import sys, json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from ticketing import PrintPrepJob
from processor import JobProcessor
from config import TYPE_SUFFIXES, CUP_PRESETS, DEFAULT_SIZE, PARTNERS
import utils

def main():
    parser = argparse.ArgumentParser(description="PrintPrep: Workshop Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands", required=True)

    # --- INITIALIZE ---
    init_p = subparsers.add_parser("initialize", help="Initialize a new job. Setup folders/ticket.")
    # init_p.add_argument("job_id", help="The unique identifier for the job (e.g., 2026-A01)")
    init_p.add_argument("client", help="The name of the client/customer")
    init_p.add_argument("qty", type=int, help="Total quantity in cases to print")
    init_p.add_argument("--type", default="digital_print", choices=TYPE_SUFFIXES.keys())

    init_p.add_argument("--size", choices=CUP_PRESETS.keys(), default="20oz",
                            help="The cup size preset for the cylindrical wrap")
    init_p.add_argument("--cup_color", default="clear",
                            help="The base color of the cup")
    init_p.add_argument("--mode", choices=["CMYK", "SPOT"], default="SPOT",
                            help="The ink configuration (Full CMYK or Single-color)")

    init_p.add_argument("--images", type=Path, nargs='*',
                            help="Path to the primary client image asset")
    init_p.add_argument("--logo", choices=PARTNERS, default="none",
                            help="Optional partner logo to include in the composite")
    init_p.add_argument("--units", action="store_true", help="Treat qty as individual cups instead of cases")
    init_p.add_argument("--scrap", type=int, default=0)

    # --- STATUS ---
    stat_p = subparsers.add_parser("status", help="View jobs or ticket info")
    stat_p.add_argument("target", nargs='?', help="Job ID or Status (e.g., in_progress)")

    # --- UPDATE ---
    up_p = subparsers.add_parser("update", help="Change ticket information")
    up_p.add_argument("job_id", help="The ID of the job to update")
    up_p.add_argument("value", nargs='?', default=None, help="Number to add to completed case count OR a new value for a key")
    up_p.add_argument("--scrap", type=int, default=0, help="Number of misprints/waste")
    up_p.add_argument("--key", help="The specific ticket key to change (e.g., specs, notes, deadline)")
    up_p.add_argument("--op", help="Operator initials")
    up_p.add_argument("--units", action="store_true", help="Treat value as individual cups")
    up_p.add_argument("--image", type=Path, help="Add or replace client artwork")
    up_p.add_argument("--logo", choices=PARTNERS, default="none",
                        help="Optional partner logo to include in the composite")

    # --- PROCESS ---
    proc_p = subparsers.add_parser("process", help="Run image processing")
    proc_p.add_argument("job_id", help="The ID of the job to process")
    proc_p.add_argument("--proof", action="store_true", help="Generate a digital proof composite")

    # --- DELETE ---
    del_p = subparsers.add_parser("delete", help="Permanently remove a job and its folders")
    del_p.add_argument("job_id", help="The Job ID to delete")
    del_p.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    # --- SHOW HELP ---
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    # --- EXECUTE COMMANDS ---
    args = parser.parse_args()
    execute_commands(args)

def display_dashboard(display_list):
    print(f"\n{'JOB ID':<12} | {'CLIENT':<15} | {'STATUS':<12} | {'PROGRESS':<22} | {'SPP':<5} | {'ETM':<8} | {'DEADLINE'}")
    print("-" * 95)

    for t in display_list:
        qty = t.get("quantity", {})
        specs = t.get("specs", {})
        c_size = specs.get("case_size", 72)
        try:
            spp = int(t.get("SPP", 45))
        except (ValueError, TypeError):
            spp = 45

        comp = qty.get('completed', 0)
        total = qty.get('total', 0)

        # Formatting for cases/units
        def fmt(c): return f"{c // c_size}c {c % c_size}u" if c % c_size else f"{c // c_size}cs"

        # Combine Progress into one string to pad it as a single block
        prog_combined = f"{fmt(comp)}/{fmt(total)}"

        # Calculate ETM based on remaining units
        remaining_units = max(0, total - comp)

        total_seconds = remaining_units * spp
        total_minutes = total_seconds // 60

        if remaining_units <= 0:
            etm_str = "--"
        elif total_minutes > 120:
            # Convert to hours if over 2 hours
            etm_hours = total_minutes / 60
            etm_str = f"{etm_hours:.1f}h"
        else:
            etm_str = f"{total_minutes}m"

        deadline = t.get("timestamps", {}).get("deadline", "N/A")[:10]

        print(
            f"{t['job_id']:<12} | {t['client_name'][:15]:<15} | {t['status'].upper():<12} | {prog_combined:<22} | {spp:<6} | {etm_str:<8} | {deadline}")

    # After the loop, add a summary line
    finished_count = len([t for t in display_list if t.get('status') == 'finished'])
    active_count = len(display_list) - finished_count

    print(f"\nDashboard View: {active_count} Active | {len(display_list)} Total")

def process_command(args):
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

    # Look specifically for the client image, regardless of extension
    client_files = list(raw_dir.glob("client_image.*"))

    if not client_files:
        print(f"Error: Could not find 'client_image' in {raw_dir.name}.")
        return

    source_image = client_files[0]  # Grab the first file in raw/
    logo_name = specs.get("partner_logo")

    # 4. Initialize Processor
    processor = JobProcessor(base_path=folder_path, specs=specs)

    # 5. Execute requested action
    if args.proof:
        # Assuming you pass a logo path via args, or leave None
        processor.generate_proof(source_image, utils.select_partner_asset(logo_name, data.get("specs").get("print_mode", "SPOT")))
        # print(data.get("specs").get("print_mode"))
        # Automatically update the ticket status to note a proof was made
        job = PrintPrepJob(args.job_id, data["client_name"], 0)
        job.base_path = folder_path
        job.update_ticket(key="status", value="proof_generated")
    else:
        # Standard dialog/interactive mode
        run_prod = input("Generate 8-channel production TIFF? (y/n): ")
        if run_prod.lower() == 'y':
            processor.generate_production_tiff(source_image)

def initialize_command(args):
    try:
        print(f"--- Initializing New Job for {args.client} ---")

        preset = CUP_PRESETS.get(args.size, CUP_PRESETS[DEFAULT_SIZE])
        case_size = preset["case_size"]

        # total_cups = args.qty if args.units else (args.qty * case_size)

        # Initialize the Job Object
        job = PrintPrepJob(
            client_name=args.client,
            quantity=args.qty,
            job_type=args.type,
            cup_size=args.size,  # Pass the string "12oz", "16oz", etc.
            units=args.units
        )
        job.initialize_structure()

        # Package Specifications
        specs = {
            "cup_size": args.size,
            "cup_color": args.cup_color,
            "print_mode": args.mode,
            "partner_logo": args.logo
        }

        # Handle Asset Ingestion
        if args.images:
            for img_path in args.images:
                if img_path.exists():
                    ext = img_path.suffix
                    new_name = f"client_image{ext}"
                    dest = job.base_path / "raw" / new_name
                    shutil.copy(img_path, dest)
            print(f"-> {len(args.images)} assets imported.")

        if args.logo and args.logo != "none":
            asset_path = utils.select_partner_asset(args.logo, args.mode)

            if asset_path:
                dest = job.base_path / "raw" / asset_path.name
                shutil.copy(asset_path, dest)
                print(f"Linked partner asset: {asset_path.name}")


        # Create the Ticket
        ticket_path = job.create_ticket(specs)
        print(f"Success: Ticket created at {ticket_path}")

    except Exception as e:
        print(f"Error: Could not initialize job. {e}")
        sys.exit(1)

def update_command(args):
    # Logic to find the folder since the folder name includes a date and client name
    target_folders = list(Path("jobs").glob(f"*_{args.job_id}_*"))
    if not target_folders:
        print(f"Error: No folder found for Job ID {args.job_id}")
        return

    # Reconstruct the job object from the existing folder
    # We extract client name from the folder string for the object
    folder_path = target_folders[0]
    client_name = folder_path.name.split('_')[-1]

    job = PrintPrepJob(args.job_id, target_folders[0].name.split('_')[-1], 0)
    job.base_path = target_folders[0]

    # --- IMAGE INJECTION LOGIC ---
    if getattr(args, 'image', None):
        if args.image.exists():
            raw_dir = job.base_path / "raw"

            # 1. Purge any existing client artwork to prevent conflicts
            for old_file in raw_dir.glob("client_image.*"):
                old_file.unlink()
                print(f"Removed old artwork: {old_file.name}")

            # 2. Copy and rename the new artwork
            ext = args.image.suffix
            new_name = f"client_image{ext}"
            shutil.copy(args.image, raw_dir / new_name)
            print(f"Success: Linked new artwork as {new_name}")
        else:
            print(f"Error: Source image file '{args.image}' not found.")

        # If the user ONLY wanted to update the image, exit cleanly here
        if args.value is None and args.key is None and args.op is None:
            return
    # ---------------------------------

    # --- LOGO SWAP LOGIC ---
    if args.logo and args.logo != "none":
        raw_dir = job.base_path / "raw"


        # 2. Select new logo using our multi-mode utility
        # We pull the current mode from the ticket to give the [REC] tag
        with open(job.base_path / "ticket.json", 'r') as f:
            current_ticket = json.load(f)
            current_mode = current_ticket.get("specs", {}).get("print_mode", "SPOT")

        actual_id = current_ticket.get("job_id")
        new_logo_path = utils.select_partner_asset(args.logo, current_mode)

        if new_logo_path:
            # Remove ONLY partner files (not client_image)
            for old_file in raw_dir.glob("*.*"):
                if "client_image" not in old_file.name:
                    try:
                        old_file.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete {old_file.name}: {e}")

            shutil.copy(new_logo_path, raw_dir / new_logo_path.name)
            job.update_ticket(key="partner_logo", value=args.logo)
            print(f"Successfully updated logo to: {new_logo_path.name}")

        if args.value is None and args.key is None and args.image is None:
            return

    if args.value is None and args.key is None and args.op is None:
        job.display_ticket()
    else:
        job.update_ticket(value=args.value, key=args.key, operator=args.op, scrap=args.scrap, units=args.units)

def status_command(args):
    root_jobs = Path("jobs")
    all_tickets = PrintPrepJob.get_all_jobs()
    valid_statuses = ["initialized", "in_progress", "on_hold", "canceled", "finished", "proof_generated"]

    # Handle the 'all' keyword
    if args.target is not None and args.target.lower() == "all":
        # Show everything, no filtering
        display_list = all_tickets
    elif args.target in valid_statuses or args.target is None:
        # Global Overview
        # Determine if 'target' is a status filter (e.g., 'finished', 'in_progress')
        filter_status = args.target if args.target in valid_statuses else None

        # Filter out finished jobs unless specifically requested
        display_list = []
        for t in all_tickets:
            # completed = t.get("quantity", {}).get("completed", 0)
            # total = t.get("quantity", {}).get("total", 0)
            if filter_status:
                if t["status"] == filter_status:
                    display_list.append(t)
            elif t["status"] != "finished":  # Default: show only active work
                display_list.append(t)
    else:
        # Reconstruct and display specific ticket
        target_folders = list(root_jobs.glob(f"*_{args.target}_*"))
        if target_folders:
            job = PrintPrepJob(args.target, "ViewOnly", 0)
            job.base_path = target_folders[0]
            job.display_ticket()
            return
        else:
            print(f"Error: Job {args.target} not found.")
            return

    # Sort by deadline (earliest first)
    display_list.sort(key=lambda x: x["timestamps"]["deadline"])
    display_dashboard(display_list)

def delete_command(args):
    # Find the job folder
    target_folders = list(Path("jobs").glob(f"*_{args.job_id}_*"))
    if not target_folders:
        print(f"Error: Job {args.job_id} not found.")
        return

    target_path = target_folders[0]

    # Safety Check
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

def execute_commands(args):
    if args.command == "process":
        process_command(args)
    elif args.command == "initialize":
        initialize_command(args)
    elif args.command == "update":
        update_command(args)
    elif args.command == "status":
        status_command(args)
    elif args.command == "delete":
        delete_command(args)

if __name__ == "__main__":
    main()