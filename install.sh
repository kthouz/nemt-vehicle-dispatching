# take input from user
echo "Enter the name of the location you want to download pdf for (e.g. kentucky). Go to https://download.geofabrik.de/ to see the list of available locations."
read LOCATION
OSM_FILE="${LOCATION}-latest.osm.pbf"

mkdir -p data

# check if file doesn't exist yet and download it
if [ ! -f "docker/osrm/data/${OSM_FILE}" ]; then
    wget https://download.geofabrik.de/north-america/us/${OSM_FILE} -O docker/osrm/data/${OSM_FILE}
    if [ $? -ne 0 ]; then
        echo "wget failed"
        exit 1
    fi
else
    echo "the pbf file already exists"
fi

# check if docker image exists and pull it. If it doesn't exist, build it. If it fails, exit
if [[ "$(docker images -q ghcr.io/project-osrm/osrm-backend 2> /dev/null)" == "" ]]; then
    docker build -t ghcr.io/project-osrm/osrm-backend docker/osrm
    if [ $? -ne 0 ]; then
        echo "docker build failed"
        exit 1
    fi
else
    docker pull ghcr.io/project-osrm/osrm-backend
fi

docker run -t -v "./docker/osrm/data:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /docker/osrm/data/${OSM_FILE} || echo "osrm-extract failed"
docker run -t -v "./docker/osrm/data:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /docker/osrm/data/${OSM_FILE} || echo "osrm-partition failed"
docker run -t -v "./docker/osrm/data:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /docker/osrm/data/${OSM_FILE} || echo "osrm-customize failed"

docker-compose -f docker/osrm/docker-compose.yml down
docker-compose -f docker/osrm/docker-compose.yml build
docker-compose -f docker/osrm/docker-compose.yml up -d

