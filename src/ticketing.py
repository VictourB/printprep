import json
from pathlib import Path
from datetime import datetime, timedelta
from config import TYPE_SUFFIXES, CUP_PRESETS, DEFAULT_SIZE

class PrintPrepJob:
    def __init__(self, client_name, quantity, job_type, cup_size=DEFAULT_SIZE, root_dir="jobs", units=False):
        # Determine case size from presets immediately
        preset = CUP_PRESETS.get(cup_size, CUP_PRESETS[DEFAULT_SIZE])
        self.case_size = preset["case_size"]

        self.job_id = self.generate_job_id(client_name, job_type, root_dir)
        self.client_name = client_name.strip()

        self.quantity = quantity if units else (quantity * self.case_size)
        self.SPP = 45
        self.units = units
        self.cup_size = cup_size

        # Create Folder
        date_str = datetime.now().strftime('%Y-%m-%d')
        safe_client_name = self.client_name.replace(' ', '_')
        self.folder_name = f"{date_str}_{self.job_id}_{safe_client_name}"

        self.base_path = Path(root_dir) / self.folder_name

    def initialize_structure(self):
        """Creates the necessary subdirectories for the job."""
        if self.base_path.exists():
            print(f"Notice: Workspace {self.folder_name} already exists.")

        subfolders = ['raw', 'preflight', 'output']
        for folder in subfolders:
            (self.base_path / folder).mkdir(parents=True, exist_ok=True)

        return self.base_path

    def create_ticket(self, specs, job_type="digital_print"):
        """Generates the ticket.json with job specifications."""
        ticket_file = self.base_path / "ticket.json"

        # Guardrail: Prevent accidental overwriting of an existing ticket
        if ticket_file.exists():
            print("Notice: ticket.json already exists. Skipping creation to preserve data.")
            return ticket_file

        # Calculate default 2-week deadline
        created_dt = datetime.now()
        deadline_dt = created_dt + timedelta(days=14)

        ticket_data = {
            "job_id": self.job_id,
            "client_name": self.client_name,
            "job_type": job_type,
            "status": "initialized",
            "timestamps": {
                "created_at": created_dt.isoformat(),
                "deadline": deadline_dt.isoformat(),
                "finished_at": None
            },
            "quantity": {
                "total": self.quantity,
                "completed": 0,
                "scrap": 0
            },
            "SPP": self.SPP,
            "operators": [],
            "specs": {
                **specs,
                "case_size": self.case_size
            },

            "notes": ""
        }

        with open(ticket_file, 'w') as f:
            json.dump(ticket_data, f, indent=4)
        return ticket_file

    @staticmethod
    def generate_job_id(client_name, job_type, root_dir="jobs"):
        # 1. Get Initials (AB)
        words = client_name.split()
        if len(words) >= 2:
            initials = (words[0][0] + words[1][0]).upper()
        else:
            initials = client_name[:2].upper()

        # 2. Get Suffix (ZZ)
        suffix = TYPE_SUFFIXES.get(job_type, "XX")

        # 3. Find the next number (XXX)
        root = Path(root_dir)
        root.mkdir(exist_ok=True)

        existing_numbers = []
        # Scan for folders starting with the client initials
        for folder in root.iterdir():
            if folder.is_dir():
                # Folder format: YYYY-MM-DD_AB001ZZ_Client_Name
                parts = folder.name.split('_')
                if len(parts) >= 2:
                    folder_id = parts[1]  # e.g., CD003DP
                    if folder_id.startswith(initials):
                        # Extract the 3 digits between initials and suffix
                        try:
                            num_str = folder_id[2:5]
                            existing_numbers.append(int(num_str))
                        except (ValueError, IndexError):
                            continue

        next_num = max(existing_numbers, default=0) + 1

        # Return formatted ID: AB + 001 + ZZ
        return f"{initials}{next_num:03d}{suffix}"

    def _calculate_status(self, data):
        """Internal helper to sync status with current progress."""
        qty = data.get("quantity", {})
        completed = qty.get("completed", 0)
        total = qty.get("total", 0)

        if data["status"] != "canceled" and data["status"] != "on_hold":
            if completed >= total and total > 0:
                data["status"] = "finished"
                # Set finished_at only if it wasn't already set
                if "timestamps" in data and not data["timestamps"].get("finished_at"):
                    data["timestamps"]["finished_at"] = datetime.now().isoformat()
            elif completed > 0:
                data["status"] = "in_progress"
                # Optional: Clear finished_at if a job is reopened
                if "timestamps" in data:
                    data["timestamps"]["finished_at"] = None
            elif data["status"] != "proof_generated":
                data["status"] = "initialized"
        else:
            pass # in canceled or on_hold state only allow manual update
        return data

    def update_ticket(self, value=None, key=None, operator=None, units=False, scrap=0):
        """
        Updates the completed quantity.
        """
        ticket_file = self.base_path / "ticket.json"

        # Guardrail: Ensure the ticket actually exists before trying to read it
        if not ticket_file.exists():
            print(f"Error: Could not find ticket.json in {self.folder_name}.")
            return False

        # Read the current state
        with open(ticket_file, 'r') as f:
            data = json.load(f)

        use_units_mode = units if units is not None else self.units
        case_size = data.get("specs", {}).get("case_size", DEFAULT_SIZE)
        multiplier = 1 if use_units_mode else case_size

        # SCENARIO 1: Update a specific Metadata Key (e.g., notes, specs)
        if key:
            # Check Root Keys
            if key in data:
                data[key] = value
                print(f"Updated {key} to: {value}")

            # Check if the key belongs in the 'quantity' sub-dict
            elif key in ["total", "completed"]:
                # Apply case multiplier to the override value
                data["quantity"][key] = int(value) * multiplier
                print(f"Updated {key} to {value} cases ({data['quantity'][key]} units).")
            elif key == "scrap":
                # Scrap is almost always entered as individual units
                data["quantity"]["scrap"] += int(value)

            # Check if the key belongs in the 'timestamps' sub-dict (e.g. deadline)
            elif key in ["deadline", "created_at", "finished_at"]:
                if "timestamps" not in data:
                    data["timestamps"] = {}

                # Logic for relative deadline adjustment (+/- days)
                if key == "deadline" and (value.startswith('+') or value.startswith('-')):
                    try:
                        # Get existing deadline or fallback to today if missing
                        current_str = data["timestamps"].get("deadline", datetime.now().isoformat())
                        # Standardize format (remove time if present)
                        current_dt = datetime.fromisoformat(current_str.split('T')[0])

                        days_offset = int(value)  # value is "+7" or "-3"
                        new_dt = current_dt + timedelta(days=days_offset)
                        value = new_dt.isoformat()
                    except (ValueError, TypeError):
                        print("Error: Could not calculate relative deadline.")

                data["timestamps"][key] = value
                print(f"Updated timestamp.{key} to: {value[:10]}")

            # Check if it's a Spec
            elif key in data.get("specs", {}):
                data["specs"][key] = value
                print(f"Updated spec {key} to: {value}")

            # Root level fallback
            else:
                create_key = input(f"There is no key {key} would you like to create it? y/N ")
                if create_key.upper() == "y".upper():
                    data[key] = value
                    print(f"Added key {key} and set to: {value}")

        # SCENARIO 2: Update Quantity & Scrap
        if not key:
            qty = data.get("quantity", {"completed": 0, "total": 0, "scrap": 0})
            # Update Production only if a value was actually passed
            if value is not None:
                added_qty = int(value) * multiplier
                qty["completed"] += added_qty

            # Update Scrap regardless of whether value exists
            if scrap != 0:
                qty["scrap"] += int(scrap)
                # Optional: Prevent scrap from ever falling below 0
                if qty["scrap"] < 0:
                    qty["scrap"] = 0

            data["quantity"] = qty

        # SCENARIO 3: Log Operator
        if operator:
            if "operators" not in data:
                data["operators"] = []
            if operator.upper() not in data["operators"]:
                data["operators"].append(operator.upper())

        # Update Status
        self._calculate_status(data)

        with open(ticket_file, 'w') as f:
            json.dump(data, f, indent=4)

        print(f"Job {data["job_id"]} successfully updated.")

    @staticmethod
    def get_all_jobs(root_dir="jobs"):
        """Retrieves all valid job tickets"""
        root = Path(root_dir)

        tickets = []
        for ticket_path in root.glob("*/ticket.json"):
            try:
                with open(ticket_path, "r") as f:
                    tickets.append(json.load(f))
            except Exception:
                continue
        return tickets

    def display_ticket(self):
        """Reads and prints a summary of the job ticket to the console."""
        ticket_file = self.base_path / "ticket.json"

        if not ticket_file.exists():
            print(f"Error: No ticket found for {self.job_id}")
            return

        with open(ticket_file, 'r') as f:
            data = json.load(f)

        # SELF-HEAL ON VIEW ---
        original_status = data.get("status")
        data = self._calculate_status(data)
        # If the status changed during recalculation, save it back to the file
        if data.get("status") != original_status:
            with open(ticket_file, 'w') as f:
                json.dump(data, f, indent=4)


        # SAFELY RETRIEVE THE CREATION DATE
        # Check new nested schema first, then old flat schema, then fallback to "Unknown"
        created_val = data.get("timestamps", {}).get("created_at") or data.get("created_at", "Unknown")
        deadline_val = data.get("timestamps", {}).get("deadline") or data.get("deadline", "Unknown")

        # Clean up the string for display if it's not "Unknown"
        if created_val != "Unknown":
            created_display = created_val.replace("T", " ")[:16]
        else:
            created_display = created_val
        deadline_display = deadline_val.replace("T", " ")[:10]

        print(f"\n--- JOB TICKET: {data.get('job_id', 'N/A')} ---")
        print(f"Client:   {data.get('client_name', 'N/A')}")
        print(f"Status:   {data.get('status', 'N/A').upper()}")
        print(f"Job Type: {data.get('job_type', 'N/A').upper()}")

        # Handle the quantity display which also changed from a list [0, qty] to a dict
        qty = data.get("quantity", {})
        if isinstance(qty, list):
            print(f"Progress: {qty[0]} / {qty[1]}")
        else:
            print(f"Progress: {qty.get('completed', 0)} / {qty.get('total', 0)}")
            print(f"Scrap: {qty.get('scrap', 0)}")
            print(f"Created:  {created_display}")

        # Handle the optional finished_at
        finished_val = data.get("timestamps", {}).get("finished_at") or data.get("finished_at")
        if finished_val:
            print(f"Finished: {finished_val.replace('T', ' ')[:16]}")

        print(f"Deadline: {deadline_display}\n")
        print(f"Specs:    {data.get('specs', {})}")

        if data.get("operators"):
            print(f"Operators:  {data.get('operators')}")

        print(f"\nNotes: {data.get('notes')}")
        print("-" * 25 + "\n")