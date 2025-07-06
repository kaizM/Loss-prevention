# Loss Prevention System - Architecture Guide

## Overview

This is a Flask-based loss prevention system designed to automatically detect and review suspicious transactions from Modisoft point-of-sale systems. The application processes daily transaction reports, identifies suspicious activities (voids, refunds, no-sales, discount removals), and creates corresponding video clips for manual review.

## System Architecture

### Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM
- **Database**: PostgreSQL (Neon-backed, built-in Replit database)
- **File Processing**: Pandas for CSV/Excel parsing
- **Video Processing**: FFmpeg for video clip extraction
- **Storage**: Local filesystem for video clips and uploads

### Frontend Architecture
- **Template Engine**: Jinja2 templates
- **CSS Framework**: Bootstrap 5 with dark theme
- **JavaScript**: Vanilla JavaScript with Video.js for video playback
- **Responsive Design**: Mobile-friendly interface for Android/iOS browsers

### Database Schema
The system uses three main tables:
- **TransactionReport**: Stores uploaded report metadata
- **SuspiciousTransaction**: Contains flagged transactions with video references
- **ReviewLog**: Tracks review status changes and audit trail

## Key Components

### 1. File Upload & Processing (`routes.py`, `utils/file_parser.py`)
- Accepts CSV/Excel files from Modisoft systems
- Parses transaction data using flexible column mapping
- Identifies suspicious transaction types automatically
- Creates database records for review workflow

### 2. Video Processing (`utils/video_processor.py`)
- Matches transaction timestamps to video source files
- Extracts 15-second clips (5 seconds before, 10 seconds after)
- Organizes clips by date in structured folder hierarchy
- Uses FFmpeg for video manipulation

### 3. Review Dashboard (`templates/dashboard.html`, `templates/review.html`)
- Filterable transaction list with status indicators
- Video player integration for evidence review
- Quick action buttons (OK, Review, Fraud)
- Batch processing capabilities

### 4. Reporting & Analytics (`templates/reports.html`)
- Statistical summaries and trend analysis
- CSV export functionality
- Review status breakdowns

## Data Flow

1. **Input**: Daily transaction reports uploaded via web interface
2. **Processing**: System parses files and identifies suspicious patterns
3. **Video Matching**: Timestamps matched to camera footage
4. **Clip Creation**: Automated video clip extraction using FFmpeg
5. **Review**: Human review via web dashboard
6. **Classification**: Transactions marked as OK, Review, or Fraud
7. **Reporting**: Analytics and export capabilities

## External Dependencies

### Video Processing
- **FFmpeg**: Required for video clip extraction
- **Video Source**: Expects organized video files with timestamp naming
- **Storage**: Local filesystem for video clips and uploads

### File Processing
- **Pandas**: CSV/Excel parsing
- **Supported Formats**: CSV, XLS, XLSX files up to 16MB

### Frontend Libraries
- **Bootstrap 5**: UI framework with dark theme
- **Video.js**: HTML5 video player
- **Font Awesome**: Icons and UI elements

## Deployment Strategy

### Environment Configuration
- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `SESSION_SECRET`: Flask session security key
- Video storage paths configurable via Flask config

### Directory Structure
```
/uploads/          # Uploaded transaction reports
/clips/YYYY-MM-DD/ # Video clips organized by date
/video_source/     # Source video files from cameras
```

### Production Considerations
- Proxy-aware configuration (ProxyFix middleware)
- Connection pooling for database
- Automatic directory creation
- Debug logging enabled

## Recent Changes

```
Recent Changes:
- July 06, 2025: Enhanced filtering system for better user experience
  * Added report-specific filtering to dashboard
  * Implemented date-based filtering with visual indicators
  * Added "Clear Filters" button for easy navigation
  * Fixed context preservation when reviewing transactions
  * Added smart filtering badges to show active filters
  * Upgraded to PostgreSQL database for better performance and reliability
- July 06, 2025: Enhanced video processing system
  * Added Alibi Cloud API integration for direct video clip extraction
  * Added RTSP stream support for live camera feeds
  * Created video settings page for configuration and testing
  * Maintained backward compatibility with local video files
  * Added connection testing functionality
- July 06, 2025: Initial system setup
  * Built core Flask application with SQLAlchemy models
  * Implemented file upload and transaction parsing
  * Created responsive web dashboard with Bootstrap dark theme
  * Added review workflow and reporting features
```

## User Preferences

```
Preferred communication style: Simple, everyday language.
```

## Technical Notes

### Database Design
- Uses SQLAlchemy ORM with declarative base
- Foreign key relationships between reports and transactions
- Audit trail via ReviewLog table
- Flexible transaction type handling

### Video Processing Workflow
- Timestamp-based video file matching
- Configurable clip duration (currently 5s before, 10s after)
- Automatic error handling and logging
- Date-based file organization

### Security Considerations
- File upload validation and size limits
- Secure filename handling
- Session management with configurable secrets
- SQL injection protection via ORM

### Mobile Compatibility
- Responsive Bootstrap design
- Touch-friendly interface
- Video playback on mobile browsers
- Progressive enhancement approach