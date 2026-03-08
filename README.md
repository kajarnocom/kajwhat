# kajwhat

Extract WhatsApp messages from iOS backup SQLite database
and generate readable HTML conversation files.

## Prerequisites
Take iOS backup of iPhone 
In my case the backup is over 300 GB and placed on an external hard disk 
Update the location of that backup in the configuration parameters
```python
  LACIE_PATH = Path("/Volumes/LaCie")
  IOS_BACKUP_ROOT = LACIE_PATH / "MobileSync" / "Backup"
```
which so far are part of the code (they might be promoted to a config file later)

## Pipeline:
iOS backup → ChatStorage.sqlite → WhatsApp.csv → HTML
