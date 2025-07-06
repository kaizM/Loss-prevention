# Video Upload Guide

## Current Status
Your DVR (gngpalacios.alibiddns.com:8000) is not directly accessible from this cloud server, which is normal and expected for security reasons. Your DVR is properly secured on your private network.

## How to Get Video Processing Working

### Option 1: Upload Daily Video Files (Recommended)
1. **Export from your DVR:** Use your Alibi app to export daily video files
2. **Name format:** Save as YYYY-MM-DD.mp4 (example: 2025-07-04.mp4)
3. **Upload location:** Place files in the `video_source/` folder
4. **Automatic processing:** System will automatically find and process clips

### Option 2: Manual Clip Upload
1. **When transactions are flagged:** Use your Alibi app to manually create clips
2. **Time range:** 90 seconds before + 30 seconds after transaction time
3. **Upload:** Place clips in `clips/YYYY-MM-DD/` folder
4. **Naming:** Use transaction ID in filename

### Option 3: Local Network Bridge (Advanced)
Set up a local computer on your network to:
1. Download clips from your DVR
2. Upload them to this system
3. Automate the process with a simple script

## Current Working Status
✅ Video processing is already working with uploaded files
✅ System successfully processed your test video
✅ All transaction parsing and review features are ready

## What You Have Now
- Complete loss prevention system
- Transaction parsing and suspicious activity detection  
- Video clip creation from uploaded files
- Review dashboard with video player
- Reporting and analytics

The only missing piece is the automatic video download, which you can easily handle by uploading daily video files from your DVR.