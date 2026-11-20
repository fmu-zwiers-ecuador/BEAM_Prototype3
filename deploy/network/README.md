# Network deployment

Temporary network, gateway, and update scripts, kept here until Ansible takes
ownership of them. Scripts refer to this directory on a Pi as
`/home/pi/BEAM_Prototype3/deploy/network/`.

| File | Purpose |
|---|---|
| `repull.sh` | Deletes and re-clones the repository on `main` |
| `wlan0.sh`, `wlan1.sh`, `wpa_supplicant-wlan1.conf` | Wi-Fi interfaces |
| `NodeInternet_Setup.sh` | Node gateway and mesh boot (`mesh-boot.service`, `mesh-timesync.service`); run once by hand |
| `SupervisorGateway_Setup.sh` | Supervisor gateway |
| `set_internetservice.sh` | Installs the internet restart and monitor services |
| `monitor_internet.sh`, `restart_internet.sh` | Supervisor internet watchdog |
| `batman/` | BATMAN mesh install and start scripts, plus `batctl_translate.py` |

`wlan0.sh` and `wpa_supplicant-wlan1.conf` hold placeholder credentials. Fill
them in on the Pi only and never commit real values.

`batman.service` is in `deploy/systemd/`, and the mesh documentation is in
`docs/mesh/`.
