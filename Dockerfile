FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Create a non-root user with UID 1000 required by Hugging Face
RUN useradd -m -u 1000 user
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and set ownership to the non-root user
COPY --chown=user backend/ ./backend/

# Switch to the non-root user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set working directory to backend
WORKDIR /app/backend

# Expose port 7860 (Hugging Face standard)
EXPOSE 7860

# Run FastAPI app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
