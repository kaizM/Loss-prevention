import os
import logging
from datetime import datetime, timedelta
import subprocess
import glob
from flask import current_app

def create_video_clip(transaction):
    """
    Create a video clip for a suspicious transaction.
    
    Args:
        transaction: SuspiciousTransaction object
        
    Returns:
        str: Path to created video clip or None if failed
    """
    try:
        # Find source video file based on timestamp
        source_video = find_source_video(transaction.transaction_timestamp)
        
        if not source_video:
            logging.warning(f"No source video found for transaction {transaction.id}")
            return None
        
        # Calculate clip start and end times
        clip_start = transaction.transaction_timestamp - timedelta(seconds=5)
        clip_end = transaction.transaction_timestamp + timedelta(seconds=10)
        
        # Create output filename
        output_filename = f"{transaction.transaction_type}_{transaction.transaction_timestamp.strftime('%Y-%m-%d_%H-%M-%S')}_Cashier{transaction.cashier_id}.mp4"
        
        # Create date-based subfolder
        date_folder = transaction.transaction_timestamp.strftime('%Y-%m-%d')
        output_dir = os.path.join(current_app.config['CLIPS_FOLDER'], date_folder)
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, output_filename)
        
        # Extract video clip using FFmpeg
        success = extract_video_clip(source_video, output_path, clip_start, clip_end)
        
        if success:
            logging.info(f"Created video clip: {output_path}")
            return output_path
        else:
            logging.error(f"Failed to create video clip for transaction {transaction.id}")
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
        
        # Common video file patterns
        patterns = [
            f"{timestamp.strftime('%Y-%m-%d-%H-%M')}.mp4",
            f"{timestamp.strftime('%Y%m%d_%H%M')}.mp4",
            f"{timestamp.strftime('%Y-%m-%d')}*.mp4",
            f"{timestamp.strftime('%Y%m%d')}*.mp4"
        ]
        
        # Search for matching files
        for pattern in patterns:
            search_path = os.path.join(video_source_dir, pattern)
            matches = glob.glob(search_path)
            
            if matches:
                # Return the first match (could be enhanced to find best match)
                return matches[0]
        
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
        
        # Extract time offset from transaction timestamp
        # This is a simplified approach - you'll need to adjust based on your video naming/timing
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
            import json
            return json.loads(result.stdout)
        else:
            return None
            
    except Exception as e:
        logging.error(f"Error getting video info: {str(e)}")
        return None
