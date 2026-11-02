`backup.sh` should copy every `.txt` file from `data/` into a directory
named `backup/`. The directory does not exist yet, so the script currently
fails.

Fix `backup.sh`. Running `bash backup.sh` must exit 0 and produce
`backup/a.txt` and `backup/b.txt` with their original contents.
