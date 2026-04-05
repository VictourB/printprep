# PrintPrep
**PrintPrep** is a Command Line Interface (CLI) designed to bridge the gap between digital artwork and physical factory production.

## Main Syntax:
Command	        Action	                Example
initialize	    Setup folders & ticket	python main.py initialize CD01 Pepsi 10 --size 20oz --image ./art.png
status	        View all active jobs	  python main.py status
update	        Log finished cases	    python main.py update CD01 5
update --units	Log individual cups	    python main.py update CD01 12 --units
delete	        Purge a job folder	    python main.py delete CD01

## Work in Progress
Please note that PrintPrep is an evolving project and may be subject to wild changes. 
The workflow it attempts to manage and automate is highly specific so may not be a solution for all users.
