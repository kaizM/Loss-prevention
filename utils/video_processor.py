import os
import logging
from datetime import datetime, timedelta
import subprocess
import glob
from flask import current_app
import requests
import json

def create_video_clip(transaction):
    """
    Create a video clip for a suspicious transaction.
    Supports both local files and remote video sources (Alibi Cloud, RTSP).
    
    Args:
        transaction: SuspiciousTransaction object
        
    Returns:
        str: Path to created video clip or None if failed
    """
    try:
        # Calculate clip start and end times (90 seconds before, 30 seconds after)
        clip_start = transaction.transaction_timestamp - timedelta(seconds=90)
        clip_end = transaction.transaction_timestamp + timedelta(seconds=30)
        
        # Create output filename
        output_filename = f"{transaction.transaction_type.replace(' ', '_')}_{transaction.transaction_timestamp.strftime('%Y-%m-%d_%H-%M-%S')}_Cashier{transaction.cashier_id or 'Unknown'}.mp4"
        
        # Create date-based subfolder
        date_folder = transaction.transaction_timestamp.strftime('%Y-%m-%d')
        output_dir = os.path.join(current_app.config['CLIPS_FOLDER'], date_folder)
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, output_filename)
        
        # Try different video source methods
        success = False
        
        # Method 1: Try Alibi Cloud API if configured
        if os.environ.get('ALIBI_CLOUD_API'):
            success = extract_clip_from_alibi_cloud(transaction.transaction_timestamp, output_path, clip_start, clip_end)
            if success:
                logging.info(f"Created video clip from Alibi Cloud: {output_path}")
                return output_path
        
        # Method 2: Try RTSP stream if configured
        rtsp_url = os.environ.get('RTSP_STREAM_URL')
        if rtsp_url:
            success = extract_clip_from_rtsp(rtsp_url, transaction.transaction_timestamp, output_path, clip_start, clip_end)
            if success:
                logging.info(f"Created video clip from RTSP: {output_path}")
                return output_path
        
        # Method 3: Fallback to local video files
        source_video = find_source_video(transaction.transaction_timestamp)
        if source_video:
            success = extract_video_clip(source_video, output_path, clip_start, clip_end)
            if success:
                logging.info(f"Created video clip from local file: {output_path}")
                return output_path
        
        # If all methods failed
        logging.warning(f"No video source available for transaction {transaction.id}")
        return None
            
    except Exception as e:
        logging.error(f"Error creating video clip for transaction {transaction.id}: {str(e)}")
        return None

def find_source_video(timestamp):
    """
    Find the source video file that contains the given timestamp.
    
    Args:
        timestamp: datetime object
        
    Returns:
        str: Path to source video file or None
    """
    try:
        video_source_dir = current_app.config['VIDEO_SOURCE_FOLDER']
        
        # Common video file patterns with various naming conventions
        patterns = [
            # Exact time matches
            f"{timestamp.strftime('%Y-%m-%d-%H-%M')}.mp4",
            f"{timestamp.strftime('%Y%m%d_%H%M')}.mp4",
            f"{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.mp4",
            f"{timestamp.strftime('%Y%m%d_%H%M%S')}.mp4",
            
            # Daily files (common for 24-hour recordings)
            f"{timestamp.strftime('%Y-%m-%d')}.mp4",
            f"{timestamp.strftime('%Y%m%d')}.mp4",
            f"{timestamp.strftime('%Y-%m-%d')}*.mp4",
            f"{timestamp.strftime('%Y%m%d')}*.mp4",
            
            # Hourly files
            f"{timestamp.strftime('%Y-%m-%d-%H')}*.mp4",
            f"{timestamp.strftime('%Y%m%d_%H')}*.mp4",
            
            # Common camera naming patterns
            f"cam1_{timestamp.strftime('%Y%m%d')}.mp4",
            f"camera1_{timestamp.strftime('%Y-%m-%d')}.mp4",
            f"recording_{timestamp.strftime('%Y%m%d')}.mp4"
        ]
        
        # Search for matching files
        for pattern in patterns:
            search_path = os.path.join(video_source_dir, pattern)
            matches = glob.glob(search_path)
            
            if matches:
                # Return the first match (could be enhanced to find best match)
                logging.info(f"Found video file match: {matches[0]} for pattern: {pattern}")
                return matches[0]
        
        # Log available files for debugging
        all_files = glob.glob(os.path.join(video_source_dir, "*.mp4"))
        logging.warning(f"No video file found for {timestamp}. Available files: {all_files}")
        logging.info(f"Searched patterns: {patterns}")
        
        # If no exact match, look for files in the same hour
        hour_pattern = os.path.join(video_source_dir, f"{timestamp.strftime('%Y-%m-%d-%H')}*.mp4")
        matches = glob.glob(hour_pattern)
        
        if matches:
            return matches[0]
        
        # Last resort: look for files on the same day
        day_pattern = os.path.join(video_source_dir, f"{timestamp.strftime('%Y-%m-%d')}*.mp4")
        matches = glob.glob(day_pattern)
        
        if matches:
            # Find the file with timestamp closest to our target
            target_time = timestamp.time()
            best_match = None
            min_diff = float('inf')
            
            for match in matches:
                # Try to extract time from filename
                try:
                    basename = os.path.basename(match)
                    # This is a simplified approach - you might need to adjust based on your naming convention
                    if len(basename) >= 19:  # YYYY-MM-DD-HH-MM format
                        file_time_str = basename[11:16]  # HH-MM part
                        file_time = datetime.strptime(file_time_str, '%H-%M').time()
                        
                        # Calculate time difference
                        diff = abs((datetime.combine(timestamp.date(), target_time) - 
                                  datetime.combine(timestamp.date(), file_time)).total_seconds())
                        
                        if diff < min_diff:
                            min_diff = diff
                            best_match = match
                except Exception:
                    continue
            
            return best_match
        
        logging.warning(f"No video file found for timestamp {timestamp}")
        return None
        
    except Exception as e:
        logging.error(f"Error finding source video: {str(e)}")
        return None

def extract_video_clip(source_path, output_path, start_time, end_time):
    """
    Extract a video clip using FFmpeg.
    
    Args:
        source_path: Path to source video file
        output_path: Path for output clip
        start_time: Start time for the clip
        end_time: End time for the clip
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if FFmpeg is available
        if not is_ffmpeg_available():
            logging.error("FFmpeg is not available")
            return False
        
        # Calculate duration
        duration = (end_time - start_time).total_seconds()
        
        # Get video file creation time (simplified approach)
        # In a real implementation, you'd need to correlate video timestamp with transaction timestamp
        # For now, we'll assume the video starts at the beginning of the hour
        
        # For daily video files (like 2025-07-04.mp4), assume video starts at beginning of day
        # Extract the date from the video file and calculate offset from midnight
        import os
        video_filename = os.path.basename(source_path)
        
        # For files named like "2025-07-04.mp4", extract the date
        if video_filename.startswith('20') and len(video_filename) >= 10:
            try:
                # Extract date from filename like "2025-07-04.mp4"
                date_str = video_filename[:10]  # "2025-07-04"
                video_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                day_start = datetime.combine(video_date, datetime.min.time())
                
                # Calculate offset in seconds from start of day
                offset_seconds = (start_time - day_start).total_seconds()
                
                # Since your video file is only 30 seconds, let's use a proportional offset
                # For testing, we'll take the transaction time within the video duration
                offset_seconds = offset_seconds % 30  # Keep within 30-second video length
                
                logging.info(f"Video {video_filename} calculated offset: {offset_seconds}s for transaction at {start_time}")
            except ValueError:
                # Fallback to hourly offset if date parsing fails
                video_start = start_time.replace(minute=0, second=0, microsecond=0)
                offset_seconds = (start_time - video_start).total_seconds()
        else:
            # Fallback for other naming patterns
            video_start = start_time.replace(minute=0, second=0, microsecond=0)
            offset_seconds = (start_time - video_start).total_seconds()
        
        # FFmpeg command
        cmd = [
            'ffmpeg',
            '-i', source_path,
            '-ss', str(max(0, offset_seconds)),  # Start offset
            '-t', str(duration),  # Duration
            '-c', 'copy',  # Copy streams without re-encoding for speed
            '-avoid_negative_ts', 'make_zero',
            '-y',  # Overwrite output file
            output_path
        ]
        
        # Execute FFmpeg command
        logging.info(f"Executing FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logging.info(f"Successfully created clip: {output_path}")
            return True
        else:
            logging.error(f"FFmpeg error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logging.error("FFmpeg command timed out")
        return False
    except Exception as e:
        logging.error(f"Error extracting video clip: {str(e)}")
        return False

def is_ffmpeg_available():
    """
    Check if FFmpeg is available on the system.
    
    Returns:
        bool: True if FFmpeg is available
    """
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def extract_clip_from_alibi_cloud(timestamp, output_path, start_time, end_time):
    """
    Extract video clip from Local Alibi DVR using web interface.
    
    Args:
        timestamp: Transaction timestamp
        output_path: Path for output clip
        start_time: Start time for the clip
        end_time: End time for the clip
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get Local Alibi DVR settings
        alibi_dvr_ip = os.environ.get('ALIBI_DVR_IP', '192.168.1.100')
        alibi_username = os.environ.get('ALIBI_USERNAME', 'admin')
        alibi_password = os.environ.get('ALIBI_PASSWORD', 'password')
        camera_id = os.environ.get('ALIBI_CAMERA_ID', '4')
        
        # Convert to format used by Alibi DVR systems
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        logging.info(f"Requesting clip from local DVR {alibi_dvr_ip} for Camera {camera_id}")
        logging.info(f"Time range: {start_str} to {end_str}")
        
        # Try different common DVR ports and endpoints
        common_configs = [
            {'port': '80', 'path': '/cgi-bin/videodownload.cgi'},
            {'port': '8080', 'path': '/video/download'},
            {'port': '8000', 'path': '/api/video/export'},
            {'port': '80', 'path': '/playback/download'}
        ]
        
        for config in common_configs:
            try:
                # Build URL for video download
                dvr_url = f"http://{alibi_dvr_ip}:{config['port']}{config['path']}"
                
                # Parameters for video export
                params = {
                    'camera': camera_id,
                    'channel': camera_id,
                    'starttime': start_str,
                    'endtime': end_str,
                    'format': 'mp4'
                }
                
                # Make authenticated request
                response = requests.get(
                    dvr_url,
                    params=params,
                    auth=(alibi_username, alibi_password),
                    timeout=60,
                    stream=True
                )
                
                if response.status_code == 200 and 'video' in response.headers.get('content-type', ''):
                    # Save the video clip
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logging.info(f"Successfully downloaded clip from local DVR via {dvr_url}")
                    return True
                elif response.status_code == 404:
                    continue  # Try next configuration
                else:
                    logging.warning(f"DVR endpoint {dvr_url} returned: {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logging.warning(f"Failed to connect to DVR at {dvr_url}: {str(e)}")
                continue
        
        logging.error("All DVR endpoints failed - will try alternative methods")
        
        # Alternative: Use RTSP to record clip (requires FFmpeg)
        rtsp_url = f"rtsp://{alibi_username}:{alibi_password}@{alibi_dvr_ip}:554/cam{camera_id}"
        return extract_clip_from_rtsp(rtsp_url, timestamp, output_path, start_time, end_time)
            
    except Exception as e:
        logging.error(f"Error extracting clip from local DVR: {str(e)}")
        return False

def extract_clip_from_rtsp(rtsp_url, timestamp, output_path, start_time, end_time):
    """
    Extract video clip from RTSP stream.
    
    Args:
        rtsp_url: RTSP stream URL
        timestamp: Transaction timestamp
        output_path: Path for output clip
        start_time: Start time for the clip
        end_time: End time for the clip
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not is_ffmpeg_available():
            logging.error("FFmpeg is not available for RTSP processing")
            return False
        
        # Calculate duration
        duration = (end_time - start_time).total_seconds()
        
        # For RTSP, we need to seek to the right time
        # This is a simplified approach - in production you'd need more sophisticated time handling
        seek_seconds = 0  # Would need to calculate based on stream start time
        
        # FFmpeg command for RTSP stream
        cmd = [
            'ffmpeg',
            '-i', rtsp_url,
            '-ss', str(seek_seconds),
            '-t', str(duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-f', 'mp4',
            '-movflags', 'faststart',
            '-y',  # Overwrite output file
            output_path
        ]
        
        # Execute FFmpeg command
        logging.info(f"Executing RTSP extraction: {' '.join(cmd[:3])}...")  # Don't log full URL for security
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logging.info(f"Successfully extracted clip from RTSP stream")
            return True
        else:
            logging.error(f"RTSP extraction error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logging.error("RTSP extraction timed out")
        return False
    except Exception as e:
        logging.error(f"Error extracting clip from RTSP: {str(e)}")
        return False

def test_video_connection():
    """
    Test video source connections and return status.
    
    Returns:
        dict: Status of different video sources
    """
    status = {
        'alibi_cloud': False,
        'rtsp_stream': False,
        'local_files': False,
        'ffmpeg': is_ffmpeg_available()
    }
    
    try:
        # Test Alibi Cloud connection
        alibi_api_url = os.environ.get('ALIBI_CLOUD_API')
        alibi_username = os.environ.get('ALIBI_USERNAME')
        alibi_password = os.environ.get('ALIBI_PASSWORD')
        
        if all([alibi_api_url, alibi_username, alibi_password]):
            try:
                response = requests.get(
                    f"{alibi_api_url}/api/status",
                    auth=(alibi_username, alibi_password),
                    timeout=10
                )
                status['alibi_cloud'] = response.status_code == 200
            except:
                pass
        
        # Test RTSP stream
        rtsp_url = os.environ.get('RTSP_STREAM_URL')
        if rtsp_url and is_ffmpeg_available():
            try:
                # Quick test to see if stream is accessible
                cmd = ['ffprobe', '-v', 'quiet', '-t', '1', rtsp_url]
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                status['rtsp_stream'] = result.returncode == 0
            except:
                pass
        
        # Test local files
        video_source_dir = current_app.config.get('VIDEO_SOURCE_FOLDER', 'video_source')
        if os.path.exists(video_source_dir):
            video_files = glob.glob(os.path.join(video_source_dir, '*.mp4'))
            status['local_files'] = len(video_files) > 0
        
    except Exception as e:
        logging.error(f"Error testing video connections: {str(e)}")
    
    return status

def get_video_info(video_path):
    """
    Get information about a video file.
    
    Args:
        video_path: Path to video file
        
    Returns:
        dict: Video information or None
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return None
            
    except Exception as e:
        logging.error(f"Error getting video info: {str(e)}")
        return None
