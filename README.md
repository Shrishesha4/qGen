# Question Bank Generator

A powerful, AI-driven application to generate comprehensive question banks for any subject or topic. This tool leverages Gemini AI to create high-quality multiple-choice questions (MCQs), true/false questions, and short answers from topics or uploaded PDF/text content.

## Features

*   **Topic-Based Generation:** Generate questions simply by providing a topic (e.g., "Quantum Physics", "History of Rome").
*   **Context-Aware:** Upload PDF documents or paste text content to generate questions strictly based on that material.
*   **Batch Generation:** Generate multiple sets of questions in one go.
*   **Custom Instructions:** Provide specific context or instructions (e.g., "Focus on dates", "Make it hard for grad students").
*   **Real-time Validation:** An integrated AI validator checks every generated question for correctness, relevance, and formatting before showing it to you.
*   **Streaming UI:** Real-time progress updates and result streaming in a modern Svelte frontend.
*   **Admin Dashboard:** Manage users, tasks, and monitor all generation activity.
*   **User Management:** Role-based access control with admin and user roles.
*   **Task Assignment:** Admins can assign question generation tasks to users.
*   **History Tracking:** Complete history of all generated question sets.
*   **Mobile Responsive:** Fully optimized for mobile, tablet, and desktop devices.

## Quick Start with Docker (Recommended)

### Prerequisites
- Docker and Docker Compose installed
- Gemini API key

### One-Command Start

```bash
./start.sh
```

Or manually:

```bash
# Copy environment file and add your API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the application
docker-compose up -d
```

Access the application at: **http://localhost:8000**

**Default Admin Credentials:**
- Email: `admin@example.com`
- Password: `admin`

For detailed Docker instructions, see [DOCKER.md](DOCKER.md)

## Manual Installation (Development)

### Prerequisites

*   **Python 3.10+**
*   **Node.js & npm** (for the frontend)
*   **Google Gemini API Key**

### 1. Clone the Repository
```bash
git clone <repository-url>
cd question-bank-gen
```

### 2. Backend Setup

It's recommended to use a virtual environment.

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Configuration:**
Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin
```

### 3. Frontend Setup

Navigate to the `app` directory.

```bash
cd app
npm install
```

## Running the Application

### Start the Backend
From the project root:

```bash
python backend/main.py
```
The API will start at `http://0.0.0.0:8000`.

### Start the Frontend
Open a new terminal, navigate to `app/`, and run:

```bash
cd app
npm run dev
```
The UI will be accessible at the URL provided (usually `http://localhost:5173`).

## Usage Guide

1.  Open the web interface.
2.  **Topic:** Enter the main subject (e.g., "Photosynthesis").
3.  **Difficulty/Type:** Select your preferred difficulty and question format.
4.  **Questions per Set:** Choose how many questions you want in one bank.
5.  **Number of Sets:** Choose how many unique question banks to generate (e.g., 3 sets of 5 questions).
6.  **Context (Optional):**
    *   **Upload:** Drag and drop a PDF or text file to base questions on that specific document.
    *   **Text Area:** Paste specific text content.
    *   **User Instructions:** Add specific constraints (e.g., "No 'all of the above' options").
7.  Click **Generate**. The system will stream the status ("Generating...", "Validating...") and display the question sets as they are completed.

## Project Structure

*   `backend/`: FastAPI application and core logic.
    *   `services/generator.py`: Main logic for prompting LLMs.
    *   `services/validator.py`: Logic for validating generated questions.
    *   `core/llm.py`: Gemini model configuration.
    *   `core/pdf_processor.py`: PDF text extraction utility.
*   `app/`: Svelte frontend source code.

## Production Deployment

### Quick Deploy to Server

```bash
# Pull the latest image
docker pull shrishesha4/qgen:latest

# Run the deploy script
./deploy.sh
```

### Building and Pushing to DockerHub

```bash
# Build and push with version tag
./build-and-push.sh v1.0.0

# Build and push as latest
./build-and-push.sh
```

### Custom Domain Setup

1. Update your domain's DNS to point to your server
2. Configure SSL certificates (recommended: Let's Encrypt)
3. Use `nginx-ssl.conf` for HTTPS configuration
4. Update environment variables in `.env`:
```bash
CORS_ORIGINS=https://yourdomain.com
```

For detailed deployment instructions, including:
- Custom domain configuration
- SSL/HTTPS setup
- Database migration to PostgreSQL
- Load balancing
- Monitoring and maintenance

See **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Docker Hub

Pre-built images are available at:
```bash
docker pull shrishesha4/qgen:latest
```

### GitHub Actions

Automated builds are configured via GitHub Actions. Every push to `main` branch automatically:
- Builds the frontend
- Creates Docker images
- Pushes to DockerHub (shrishesha4/qgen)

To enable automated builds:
1. Add `DOCKERHUB_TOKEN` to GitHub repository secrets
2. Push to main branch or create a version tag
