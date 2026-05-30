FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend/ ./backend/

# Set working directory to backend
WORKDIR /app/backend

# Expose port
EXPOSE 7860

# Run FastAPI app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
