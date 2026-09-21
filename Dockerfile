# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
# We don't have a requirements.txt yet, so let's just install them directly
RUN pip install --no-cache-dir fastapi uvicorn asyncpg pyjwt sentence-transformers groq python-dotenv mcp

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run uvicorn server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
