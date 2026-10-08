# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements.txt file first, to leverage Docker layer caching
COPY requirements.txt .

# Install the dependencies
RUN pip install -r requirements.txt

# Copy the rest of the project files into the container
COPY . .

# RUN alembic upgrade head

# Run the application when the container starts
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]