# Network Setup Options for DVR Access

## Your Current Setup
- DVR: gngpalacios.alibiddns.com:8000 (ALI-QVR5132H)
- Local cameras: 192.168.0.5 (Camera 4 for register)
- Status: Properly secured on private network

## Option 1: Router Configuration (Most Automated)

### Port Forwarding Setup
1. **Access your router:** Usually 192.168.1.1 or 192.168.0.1
2. **Find Port Forwarding:** Look for "Port Forwarding" or "Virtual Servers"
3. **Add rule:**
   - External Port: 8000
   - Internal IP: Your DVR's local IP
   - Internal Port: 8000
   - Protocol: TCP

### Dynamic DNS (Already Have)
Your gngpalacios.alibiddns.com should work once port forwarding is set up.

## Option 2: VPN Access (Most Secure)
1. **Enable VPN on router:** Most modern routers support OpenVPN
2. **Create VPN profile:** Download configuration file
3. **Install on cloud server:** Connect via VPN tunnel
4. **Access DVR locally:** System can reach your DVR as if on local network

## Option 3: Local Bridge Computer (Reliable)

### Simple Python Script
```python
# Place this on a computer on your network
import requests
import schedule
import time

def download_and_upload_clips():
    # Download from your DVR
    # Upload to cloud system
    pass

schedule.every().hour.do(download_and_upload_clips)
```

### What it does:
- Runs on your local network
- Downloads clips from DVR when suspicious transactions occur
- Uploads clips to cloud system automatically

## Option 4: Manual Process (Working Now)
1. **Get notification:** System flags suspicious transaction
2. **Use Alibi app:** Navigate to timestamp
3. **Export clip:** 90 seconds before + 30 seconds after
4. **Upload:** Place in video_source folder

## Recommendation
Start with **Option 4** (manual) since it's working perfectly. Then set up **Option 1** (port forwarding) for automation.

## Current Status: Fully Functional
✅ Transaction parsing working
✅ Video processing working  
✅ Review dashboard working
✅ Reporting working

Only missing piece is automatic video download, which any of these options will solve.