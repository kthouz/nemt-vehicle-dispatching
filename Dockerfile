FROM python:3.11-slim
LABEL maintainer=cgirabawe@gmail.com

COPY ./data/vehicles.csv /app/data/vehicles.csv
COPY ./data/jobs.csv /app/data/jobs.csv
COPY ./data/addresses.json /app/data/addresses.json
COPY ./docker/osrm /app/osrm
COPY ./docker/vroom /app/vroom
COPY ./.env /app/.env
COPY ./app.py /app/app.py
COPY ./constants.py /app/constants.py
COPY ./docker-compose.yml /app/docker-compose.yml
COPY ./Dockerfile /app/Dockerfile
COPY ./helpers.py /app/helpers.py
COPY ./install.sh /app/install.sh
COPY ./README.md /app/README.md
COPY ./requirements.txt /app/requirements.txt
COPY ./routing.py /app/routing.py

# Set the working directory to /app
WORKDIR /app

# Install the requirements using pip
RUN pip install -r requirements.txt
RUN pip install --upgrade gradio

# Expose port 7860
EXPOSE 7860

# Run the application using flask
# CMD ["gradio", "app.py", "--port", "7860"]
CMD ["python", "app.py"]
