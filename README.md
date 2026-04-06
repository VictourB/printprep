# PrintPrep
**PrintPrep** is a Command Line Interface (CLI) designed to bridge the gap between digital artwork and physical factory production. It offers a robust ticketing system and automatic proof generation.

## Main Syntax:

| Command    | Action                 | Example                                                        |
| ---------- | ---------------------- | -------------------------------------------------------------- |
| initialize | Setup folders & ticket | main.py initialize CD01 Pepsi 10 --size 20oz --image ./art.png |
| status     | View all active jobs   | main.py status                                                 |
| update     | Log finished cases     | main.py update CD01 5                                          |
| process    | perform actions        | main.py process CD01 --proof                                   |
| delete     | Purge a job folder     | main.py delete CD01                                            |


## Work in Progress
Please note that PrintPrep is an evolving project and may be subject to wild changes. 
The workflow it attempts to manage and automate is highly specific so may not be a solution for all users.

Eventually a processing component is to be added that will prepare images automatically.
