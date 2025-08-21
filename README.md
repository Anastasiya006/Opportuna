# Opportuna
<img width="711" height="363" alt="Screenshot 2025-08-20 at 10 12 36 PM" src="https://github.com/user-attachments/assets/8dab00c1-732c-4b77-b4e4-3a83cbb07c4b" />

## Overview 
A Python-based job monitoring bot that automatically tracks new internship postings, from popular GitHub repositories, and sends real-time notifications via email and updates Notion database for application tracking.

## Features

- **Real-time Monitoring**: Checks multiple GitHub repositories every 30 minutes
- **Email Notifications**: Instant email alerts with job details (company, title, term, locations, date posted, sponsorship and application URL)
- **Notion Integration**: Automatically adds new jobs to your Notion database
- **Smart Deduplication**: SQLite database prevents duplicate notifications
- **Rate Limiting**: Respectful API usage with built-in delays

## Tech Stack

- **Python 3.x** - Core application
- **SQLite** - Local database for tracking seen jobs
- **Gmail SMTP** - Email notifications
- **Notion API** - Job tracking and organization
- **Requests** - HTTP client for API calls
- **Google Cloud Platform** - VM deployment and hosting

## Data Sources
- **SimflifyJobs**: https://github.com/SimplifyJobs/Summer2026-Internships
- **vanshb03**: https://github.com/vanshb03/Summer2026-Internships
