import json
from pathlib import Path
from datetime import datetime

# Example usage:
# job = PrintPrepJob("A101", "BeverageCo")
# job.initialize_structure()
# job.create_ticket({"cup_size": "16oz", "ink": "CMYK"})

class PrintPrepJob:
    def __init__(self, job_id, client_name, quantity, root_dir="jobs"):
        self.job_id = job_id
        self.client_name = client_name.strip()
        self.quantity = quantity

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

    def create_ticket(self, specs):
        """Generates the ticket.json with job specifications."""
        ticket_file = self.base_path / "ticket.json"

        # Guardrail: Prevent accidental overwriting of an existing ticket
        if ticket_file.exists():
            print("Notice: ticket.json already exists. Skipping creation to preserve data.")
            return ticket_file

        ticket_data = {
            "job_id": self.job_id,
            "client_name": self.client_name,
            "specs": specs,
            # Switched to a dictionary for explicit clarity
            "quantity": {
                "completed": 0,
                "total": self.quantity
            },
            "status": "initialized",
            # ISO format is safer for future parsing and data analysis
            "created_at": datetime.now().isoformat()
        }

        with open(ticket_file, 'w') as f:
            json.dump(ticket_data, f, indent=4)
        return ticket_file

    def update_progress(self, added_quantity, manual_status=None):
        """
        Updates the completed quantity. If completed meets or exceeds the total,
        the status is automatically updated to 'finished'.
        """
        ticket_file = self.base_path / "ticket.json"

        # Guardrail: Ensure the ticket actually exists before trying to read it
        if not ticket_file.exists():
            print(f"Error: Could not find ticket.json in {self.folder_name}.")
            return False

        # 1. Read the current state
        with open(ticket_file, 'r') as f:
            ticket_data = json.load(f)

        # 2. Calculate the new completed amount
        current_completed = ticket_data["quantity"]["completed"]
        target_total = ticket_data["quantity"]["total"]

        new_completed = current_completed + added_quantity
        ticket_data["quantity"]["completed"] = new_completed

        new_status = manual_status
        if not new_status:
            if new_completed >= target_total:
                new_status = "finished"
            elif new_completed > 0:
                new_status = "in_progress"
            else:
                new_status = ticket_data["status"]

        # Timestamp Logic: Only set finished_at if we are transitioning to 'finished'
        # and it hasn't been set yet.
        if new_status == "finished" and "finished_at" not in ticket_data:
            ticket_data["finished_at"] = datetime.now().isoformat()

        ticket_data["status"] = new_status

        # 4. Write the updated state back to the ledger
        with open(ticket_file, 'w') as f:
            json.dump(ticket_data, f, indent=4)

        print(
            f"Job {self.job_id} Update: {new_completed}/{target_total} tumblers printed. Status: {ticket_data['status']}")
        return ticket_data["status"]

    def display_ticket(self):
        """Reads and prints a summary of the job ticket to the console."""
        ticket_file = self.base_path / "ticket.json"

        if not ticket_file.exists():
            print(f"Error: No ticket found for {self.job_id}")
            return

        with open(ticket_file, 'r') as f:
            data = json.load(f)

        print(f"\n--- JOB TICKET: {data['job_id']} ---")
        print(f"Client:   {data['client_name']}")
        print(f"Status:   {data['status'].upper()}")
        print(f"Progress: {data['quantity']['completed']} / {data['quantity']['total']}")
        print(f"Created:  {data['created_at'].replace("T", " ")[:16]}")  # Show only the date
        if "finished_at" in data:
            # Formatting the ISO string for readability: YYYY-MM-DD HH:MM
            f_time = data['finished_at'].replace("T", " ")[:16]
            print(f"Finished: {f_time}")
        print(f"Specs:    {data['specs']}")
        print("-" * 25 + "\n")