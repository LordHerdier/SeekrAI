# SeekrAI

SeekrAI is an intelligent job analysis and processing platform that helps users analyze job postings, extract insights, and process job-related data using AI-powered tools.

[![Docker Image](https://img.shields.io/badge/docker-lordherdier%2Fseekrai-blue)](https://hub.docker.com/r/lordherdier/seekrai)
[![Docker Pulls](https://img.shields.io/docker/pulls/lordherdier/seekrai)](https://hub.docker.com/r/lordherdier/seekrai)

## 🚀 Features

- **Job Data Processing**: Upload and analyze job posting data
- **AI-Powered Analysis**: Leverage OpenAI's API for intelligent job content analysis
- **File Management**: Upload, process, and manage various file formats
- **Real-time Processing**: Background job processing with status tracking
- **Web Interface**: User-friendly web interface for easy interaction
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **Caching**: Redis-based caching for improved performance
- **Production Ready**: Docker containerization and production deployment support

## 🛠️ Technology Stack

- **Backend**: Python 3.9+ with Flask
- **AI Integration**: OpenAI API
- **Caching**: Redis
- **Database**: File-based storage with Redis caching
- **Frontend**: HTML/CSS/JavaScript with Flask templates
- **Deployment**: Docker & Docker Compose
- **Production Server**: Gunicorn

## 📋 Prerequisites

### Development Requirements
- Python 3.9 or higher
- pip (Python package manager)
- Redis server (for caching)
- OpenAI API key

### Production Requirements
- Docker 20.10+
- Docker Compose 2.0+

## 🔧 Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/LordHerdier/seekrai.git
cd seekrai
```

### 2. Set up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your configuration
# Required variables:
# - OPENAI_API_KEY=your_openai_api_key_here
# - SECRET_KEY=your_secret_key_here
```

### 4. Start Redis Server
```bash
# Install Redis (if not already installed)
# On Ubuntu/Debian:
sudo apt-get install redis-server

# On macOS with Homebrew:
brew install redis

# Start Redis
redis-server
```

### 5. Run the Application
```bash
# Navigate to src directory
cd src

# Run the Flask application
python app.py
```

The application will be available at `http://localhost:5000`

## 🔑 Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_secret_key_here

# Optional - Development settings
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

# File upload settings
MAX_FILE_SIZE_MB=10
UPLOAD_FOLDER=uploads
ALLOWED_EXTENSIONS=txt,pdf,docx,csv,json

# Redis settings
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO
LOGS_FOLDER=logs
```

### Configuration Files

- `config/config.yaml` - Main application configuration
- `.env` - Environment variables
- `gunicorn.conf.py` - Production server configuration

## 📚 API Endpoints

### Core Endpoints
- `GET /` - Main application interface
- `POST /upload` - File upload endpoint
- `GET /jobs` - Job listing and management
- `GET /files` - File management interface
- `GET /config` - Configuration management

### Health & Monitoring
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health information
- `GET /ready` - Readiness check

## 🏗️ Project Structure

```
seekrai/
├── src/                    # Source code
│   ├── app.py             # Main Flask application
│   ├── wsgi.py            # WSGI entry point
│   ├── config_loader.py   # Configuration management
│   ├── routes/            # Route blueprints
│   │   ├── upload_routes.py
│   │   ├── job_routes.py
│   │   ├── file_routes.py
│   │   ├── config_routes.py
│   │   └── health_routes.py
│   └── utils/             # Utility modules
│       ├── logging_setup.py
│       └── directory_setup.py
├── templates/             # HTML templates
├── static/               # Static files (CSS, JS)
├── config/               # Configuration files
├── uploads/              # File upload directory
├── logs/                 # Application logs
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile           # Docker image configuration
└── requirements.txt     # Python dependencies
```
## 🐳 Docker Quick Start

### Pull and Run from Docker Hub
```bash
# Pull the latest image
docker pull lordherdier/seekrai:latest

# Run with environment variables
docker run -d \
  -p 5000:5000 \
  -e OPENAI_API_KEY=your_api_key_here \
  -e SECRET_KEY=your_secret_key_here \
  --name seekrai \
  lordherdier/seekrai:latest
```

### Using Docker Compose (Recommended)

#### Production Deployment (Docker Hub Image)
```bash
# Clone and configure
git clone https://github.com/LordHerdier/seekrai.git
cd seekrai
cp .env.production .env
# Edit .env with your values

# Deploy using Docker Hub image
./deploy.sh
# OR
docker-compose up -d
```

#### Development Deployment (Local Build)
```bash
# Clone the repository
git clone https://github.com/LordHerdier/seekrai.git
cd seekrai

# Deploy with local build for development
./deploy.sh dev
# OR  
docker-compose -f docker-compose.dev.yml up -d
```

### Docker Compose Files

- **`docker-compose.yml`** - Production deployment using Docker Hub image
- **`docker-compose.dev.yml`** - Development deployment with local build and source code mounting

### Available Docker Tags

- `lordherdier/seekrai:latest` - Latest stable release
- `lordherdier/seekrai:v1.0.0` - Specific version tags

### Deployment Commands

```bash
# Production deployment (Docker Hub image)
./deploy.sh

# Development deployment (local build)  
./deploy.sh dev

# Stop all services
./deploy.sh stop

# View logs
./deploy.sh logs

# Check status
./deploy.sh status

# Health check
./deploy.sh health
```

## 🔍 Usage Examples

### Basic File Upload and Analysis
1. Navigate to `http://localhost:5000`
2. Upload a job posting file (PDF, DOCX, TXT, CSV)
3. Wait for processing to complete
4. View analysis results and insights

### API Usage
```bash
# Upload a file
curl -X POST -F "file=@job_posting.pdf" http://localhost:5000/upload

# Check job status
curl http://localhost:5000/jobs

# Health check
curl http://localhost:5000/health
```

## 🐛 Troubleshooting

### Common Issues

**Application won't start**
- Check if Redis is running
- Verify environment variables are set
- Check Python dependencies are installed

**File upload fails**
- Check file size limits in configuration
- Verify upload directory permissions
- Ensure file type is in allowed extensions

**AI analysis not working**
- Verify OpenAI API key is valid
- Check internet connectivity
- Review API rate limits

### Getting Help
- Check the logs in the `logs/` directory
- Review Flask application logs
- Use health check endpoints to diagnose issues

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for providing the AI analysis capabilities
- Flask community for the excellent web framework
- Redis for high-performance caching

---

For production deployment instructions, see [README_PRODUCTION.md](README_PRODUCTION.md)
