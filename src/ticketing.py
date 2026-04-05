import json
from pathlib import Path
from datetime import datetime, timedelta

# Example usage:
# job = PrintPrepJob("A101", "BeverageCo")
# job.initialize_structure()
# job.create_ticket({"cup_size": "16oz", "ink": "CMYK"})

CASE_MAP = {
    "12oz": 100,
    "16oz": 80,
    "20oz": 72,
    "24oz": 60,
    "32oz": 40
}
DEFAULT_CASE_SIZE = 72

class PrintPrepJob:
    def __init__(self, job_id, client_name, quantity, root_dir="jobs", units=False):
        self.job_id = job_id
        self.client_name = client_name.strip()
        self.quantity = quantity
        self.SPP = 45
        self.units = units

        # Create Folder - Added dashes to date for better readability and consistency
        date_str = datetime.now().strftime('%Y-%m-%d')
        safe_client_name = self.client_name.replace(' ', '_')
        self.folder_name = f"{date_str}_{job_id}_{safe_client_name}"

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

        cup_size = specs.get("cup_size", "20oz")
        case_size = CASE_MAP.get(cup_size, DEFAULT_CASE_SIZE)

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
                "case_size": case_size
            },

            "notes": ""
        }

        with open(ticket_file, 'w') as f:
            json.dump(ticket_data, f, indent=4)
        return ticket_file

    def _calculate_status(self, data):
        """Internal helper to sync status with current progress."""
        qty = data.get("quantity", {})
        completed = qty.get("completed", 0)
        total = qty.get("total", 0)

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
        else:
            data["status"] = "initialized"

        return data

    def update_ticket(self, value=None, key=None, operator=None, units=False, scrap=0):
        """
        Updates the completed quantity. If completed meets or exceeds the total,
        the status is automatically updated to 'finished'.
        """
        ticket_file = self.base_path / "ticket.json"

        # Guardrail: Ensure the ticket actually exists before trying to read it
        if not ticket_file.exists():
            print(f"Error: Could not find ticket.json in {self.folder_name}.")
            return False

        # Read the current state
        with open(ticket_file, 'r') as f:
            data = json.load(f)

        case_size = data.get("specs", {}).get("case_size", DEFAULT_CASE_SIZE)
        multiplier = 1 if units else case_size

        # SCENARIO 1: Update a specific Metadata Key (e.g., notes, specs)
        if key:
            # Check Root Keys
            if key in data:
                data[key] = value
                print(f"Updated {key} to: {value}")

            # 1. Check if the key belongs in the 'quantity' sub-dict
            elif key in ["total", "completed"]:
                # Apply case multiplier to the override value
                data["quantity"][key] = int(value) * multiplier
                print(f"Updated {key} to {value} cases ({data['quantity'][key]} units).")
            elif key == "scrap":
                # Scrap is almost always entered as individual units
                data["quantity"]["scrap"] = int(value)

            # 2. Check if the key belongs in the 'timestamps' sub-dict (e.g. deadline)
            elif key in ["deadline", "created_at", "finished_at"]:
                if "timestamps" not in data:
                    data["timestamps"] = {}
                data["timestamps"][key] = value
                print(f"Updated timestamp.{key} to: {value}")

            # 3. Check if it's a Spec
            elif key in data.get("specs", {}):
                data["specs"][key] = value
                print(f"Updated spec {key} to: {value}")

            # 4. Root level fallback
            else:
                create_key = input(f"There is no key {key} would you like to create it? y/N ")
                if create_key.upper() == "y".upper():
                    data[key] = value
                    print(f"Added key {key} and set to: {value}")

        # SCENARIO 2: Update Quantity & Scrap
        if not key:
            # Logic: Default to Cases unless units_mode is flagged
            amount = int(value) if value else 0

            added_cups = amount * multiplier

            # Handle legacy list-style quantity [0, 100] or new dict-style
            qty = data.get("quantity", {"completed": 0, "total": self.quantity, "scrap": 0})
            if isinstance(qty, list):  # Migration on the fly
                qty = {"completed": qty[0], "total": qty[1], "scrap": 0}

            try:
                added_qty = (int(value) if value else 0) * multiplier
            except ValueError:
                print("Error: Quantity must be a number.")
                return False

            qty["completed"] += added_qty
            qty["scrap"] += int(scrap)
            data["quantity"] = qty

        # SCENARIO 3: Log Operator
        if operator:
            if "operators" not in data:
                data["operators"] = []
            if operator.upper() not in data["operators"]:
                data["operators"].append(operator.upper())

        # Update Status automatically
        self._calculate_status(data)

        with open(ticket_file, 'w') as f:
            json.dump(data, f, indent=4)

        print(f"Job {self.job_id} successfully updated.")


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
        # If someone changed the total/completed manually, this fixes the status
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
            deadline_display = deadline_val.replace("T", " ")[:10]
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