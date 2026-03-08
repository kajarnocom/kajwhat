# kajwhat

Extract WhatsApp messages from iOS backup SQLite database and generate readable HTML conversation files.

## Prerequisites
### Take iOS backup of iPhone 
In my case, this was a painful operation
* The backup file usually lands in **`~/Library/Application Support/MobileSync/Backup`**
* Terminal gave me **`Operation not permitted`** when merely wanting to list the file, even with `**sudo**` (thanks to the Spirit of Steve Jobs) 
* I needed to open `System Preferences / Integrity and security` and give `Terminal` so called `Full Disk Access`
* In my case the backup is over 300 GB and I hence placed the backup on an external hard disk using a symlink from `~/Library/Application Support/MobileSync/Backup` to my external HD `/Volumes/LaCie` where I put the iOS backup in the directory `MobileSync/Backup`
* The first backup took 27 h to create 
### Update **the location** of that backup in the configuration parameters
```python
  LACIE_PATH = Path("/Volumes/LaCie")
  IOS_BACKUP_ROOT = LACIE_PATH / "MobileSync" / "Backup"
```
which so far are part of the code (they might be promoted to a config file later)

## Pipeline:
iOS backup → ChatStorage.sqlite → WhatsApp.csv → HTML
