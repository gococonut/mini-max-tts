# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables for non-interactive frontend
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

# Install ffmpeg (required by pydub)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY ./app /app

# Create output directory (though usually mounted as a volume)
RUN mkdir -p /app/output

# Make port 80 available to the world outside this container
EXPOSE 8000

# Define environment variables (can be overridden at runtime)
# It's better to pass secrets like API keys at runtime, not build them in
ENV MINIMAX_GROUP_ID=""
ENV MINIMAX_API_KEY=""
ENV OUTPUT_DIR="/app/output"
ENV LOG_LEVEL="INFO"

# Run main.py when the container launches
# Use uvicorn to run the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]