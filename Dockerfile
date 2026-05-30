FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and set ownership to UID 1000 (pre-existing user)
COPY --chown=1000 backend/ ./backend/

# Switch to the pre-existing non-root user (UID 1000 / pwuser)
USER 1000
ENV PATH="/home/pwuser/.local/bin:$PATH"

# Set working directory to backend
WORKDIR /app/backend

# Expose port 7860 (Hugging Face standard)
EXPOSE 7860

# Run FastAPI app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
