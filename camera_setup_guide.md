# Camera Setup Guide for Your System

## Camera Information (From Screenshots)
- **Camera IP**: 192.168.0.5
- **RTSP Port**: 1050
- **Device Name**: Embedded Net DVR
- **Device No**: 255

## RTSP Connection Setup

Based on your camera configuration, the RTSP URL is:
```
rtsp://admin:Patan@2020@192.168.0.5:1050/stream1
```

### Common RTSP URL Formats for Your Camera Type:
1. `rtsp://admin:Patan@2020@192.168.0.5:1050/cam/realmonitor?channel=1&subtype=0`
2. `rtsp://admin:Patan@2020@192.168.0.5:1050/stream1`
3. `rtsp://admin:Patan@2020@192.168.0.5:1050/live`
4. `rtsp://admin:Patan@2020@192.168.0.5:1050/h264`

## To Configure in Replit:

1. **Go to Replit Secrets** (🔐 icon in the sidebar)
2. **Add this secret**:
   - Name: `RTSP_STREAM_URL`
   - Value: `rtsp://admin:Patan@2020@192.168.0.5:1050/stream1`

3. **Optional: Test different stream paths** if the first one doesn't work:
   - Try the URLs listed above
   - Check your camera manual for the exact RTSP path

## Testing the Connection

Once configured, you can test the connection using the "Test Connections" button in the Video Setup page.

## Alternative: HTTP-based Access

If RTSP doesn't work, we can also try HTTP snapshot access:
- Snapshot URL: `http://192.168.0.5/cgi-bin/snapshot.cgi`
- Video stream: `http://192.168.0.5/videostream.cgi`

## Network Requirements

Make sure:
- The Replit environment can access your local network (192.168.0.5)
- Your camera allows external connections
- The RTSP port (1050) is not blocked by firewall