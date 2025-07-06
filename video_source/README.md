# Video Source Folder

This folder is for storing video files from your camera system.

## For Your Camera Setup (192.168.0.5):

Since your camera is on a local network and this system runs on the cloud, you have two options:

### Option 1: Manual File Upload (Recommended)
1. Export/download video files from your camera system
2. Upload them to this folder
3. Name them with timestamps like: `2025-07-05-14-30.mp4`

### Option 2: Network Configuration (Advanced)
1. Set up port forwarding on your router for RTSP port 1050
2. Configure the system with your public IP address
3. Ensure proper security measures

## File Naming Convention
- `YYYY-MM-DD-HH-MM.mp4` (e.g., `2025-07-05-14-30.mp4`)
- `YYYYMMDD_HHMM.mp4` (e.g., `20250705_1430.mp4`)
- `YYYY-MM-DD.mp4` for daily files

The system will automatically match these timestamps with suspicious transactions.