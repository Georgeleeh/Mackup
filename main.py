from Mackup import Mackup

b = Mackup('Big PC', script_folder='C:/Users/Georg/Documents/02 Git Repo/Mackup/', samba_folder="//pinas/backup/")

b.wait_for_previous('Mac Mini')

b.run_backup()
