current_dir=`pwd`
docker run --rm --name prometheus_test --net host \
    -p 9090:9090 \
    -v ${current_dir}/prometheus.yml:/etc/prometheus/prometheus.yml \
    prom/prometheus
