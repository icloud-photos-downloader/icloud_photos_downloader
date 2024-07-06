# Network Attached Storage

The following are example setups for NAS.

## TrueNAS

Use `Install Custom App` button to set up `icloudpd`:
| Field | Value | Note |
|-------|-------|------|
Application Name | `icloudpd` |
Version | N/A | Leave default
Container Images/Image repository | `icloudpd/icloudpd` |
Container Images/Image tag | `latest` |
Container Entrypoint/Container Args | `icloudpd` `-u` `your@email.address` `-d` `/data` `--password-provider` `webui` `--mfa-provider` `webui` `--watch-with-interval` `3600` | each as a separate arg (param name and param value become two separate args)
Port Forwarding/Container Port | `8080` |
Port Forwarding/Host Port | `9090` | or other available port on your host
Storage/Host Path Volumes/Host Path | /mnt/my_pool/photos | or another location on your host
Storage/Host Path Volumes/Mount Path | /data | 
Portal Configuration/Enable Portal Configuration | checked | 
Portal Configuration/Portal Name | `icloudpd` | 
Portal Configuration/Protocol to Portal | `HTTP Protocol` | 
Portal Configuration/Use Node IP for Portal IP/Domain | checked | 
Portal Configuration/Port | `9090` | 

Once the app has started, connect to the [WebUI](webui) to enter password and MFA code one of two ways:
- Using browser from your PC to 9090 port of your NAS
- Clicking on `icloudp` button in Detail/Application Info section of TrueNAS portal