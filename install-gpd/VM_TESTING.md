# GPD Installer — VM Testing Guide

**Last updated**: 2026-04-16

## Incus Setup

Incus is installed on the host. User `nima` is in the `incus-admin` group.

All incus commands require group context:
```bash
newgrp incus-admin <<'EOF'
incus <command>
EOF
```

### Network Configuration

- Bridge: `incusbr0` (10.43.181.1/24, DHCP range 10.43.181.2–254)
- DHCP did not work automatically for VMs — static IP was assigned manually
- DNS required `iptables` FORWARD rules to be enabled on the host:
  ```bash
  sudo iptables -P FORWARD ACCEPT
  ```

---

## Ubuntu 24.04 VM (`gpd-test`)

**Status**: RUNNING, XFCE installed, ready for installer testing

| Setting | Value |
|---------|-------|
| Image | `images:ubuntu/24.04` |
| Type | Virtual machine |
| CPUs | 4 |
| RAM | 4 GiB |
| IP | 10.43.181.100 (static) |
| Desktop | XFCE4 + goodies |
| Packages | curl installed |

### Static IP Config (inside VM)

File: `/etc/netplan/99-static.yaml`
```yaml
network:
  version: 2
  ethernets:
    enp5s0:
      addresses:
        - 10.43.181.100/24
      routes:
        - to: default
          via: 10.43.181.1
      nameservers:
        addresses:
          - 10.43.181.1
          - 8.8.8.8
```

### DNS Fix (inside VM)

systemd-resolved was not forwarding. Fixed with:
```
/etc/resolv.conf → points to 8.8.8.8, 8.8.4.4 (symlink removed)
```

### Commands

```bash
# Start
newgrp incus-admin <<'EOF'
incus start gpd-test
EOF

# Shell access
newgrp incus-admin <<'EOF'
incus exec gpd-test -- bash
EOF

# Graphical console (XFCE)
newgrp incus-admin <<'EOF'
incus console gpd-test --type=vga
EOF

# Stop
newgrp incus-admin <<'EOF'
incus stop gpd-test
EOF
```

### Testing the installer

```bash
# Push installer files into VM
newgrp incus-admin <<'EOF'
incus file push -r install-gpd/ gpd-test/root/
incus exec gpd-test -- bash /root/install-gpd/ubuntu_24_04/install.sh
EOF
```

---

## Windows 11 VM (`win11`)

**Status**: STOPPED, Windows NOT yet installed (OS install requires VGA console interaction)

| Setting | Value |
|---------|-------|
| Type | Virtual machine (empty) |
| CPUs | 4 |
| RAM | 8 GiB |
| Disk | 64 GiB |
| Secure Boot | Disabled (for unsigned VirtIO drivers) |
| Windows ISO | `/home/nima/Downloads/Win11_25H2_English_x64_v2.iso` |
| VirtIO ISO | `/home/nima/Downloads/virtio-win.iso` (v0.1.285, Fedora) |

### Windows Install Steps

1. Start the VM and connect to VGA console:
   ```bash
   newgrp incus-admin <<'EOF'
   incus start win11
   incus console win11 --type=vga
   EOF
   ```

2. During setup, "Where do you want to install Windows?" will show an empty disk list.
   - Click **"Load driver"**
   - Browse to VirtIO CD-ROM → `viostor\w11\amd64`
   - Load **Red Hat VirtIO SCSI** driver
   - The 64GB disk will appear

3. Also load the **NetKVM** network driver (`NetKVM\w11\amd64`) for immediate network access.

4. Complete Windows install. No product key needed — skip when prompted. Unactivated Windows is fully functional for testing.

5. After install, run `virtio-win-guest-tools.exe` from the VirtIO ISO inside Windows to install all remaining drivers.

6. Remove ISOs after install:
   ```bash
   newgrp incus-admin <<'EOF'
   incus config device remove win11 win11-iso
   incus config device remove win11 virtio-drivers
   EOF
   ```

### Testing the installer

```powershell
# From inside Windows, open PowerShell and run:
Set-ExecutionPolicy Bypass -Scope Process
# Copy install.ps1 into the VM first, then:
.\install.ps1
```

---

## macOS Testing

macOS cannot be easily virtualized on Linux. Options to explore:
- Borrow a physical Mac (Apple Silicon + Intel)
- Use a macOS CI runner (GitHub Actions has macOS runners)
- Cloud Mac service (e.g., MacStadium, AWS EC2 Mac)

---

## Cleanup

```bash
# Delete VMs when testing is complete
newgrp incus-admin <<'EOF'
incus delete gpd-test --force
incus delete win11 --force
EOF

# Optionally remove incus entirely
sudo apt remove incus incus-client
```
