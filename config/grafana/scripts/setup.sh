#!/bin/sh
yq -i -y ".datasources[].url = \"$1\"" /etc/grafana/provisioning/datasources/automatic.yml
yq -i -y ".datasources[].jsonData.organization = \"$2\"" /etc/grafana/provisioning/datasources/automatic.yml
yq -i -y ".datasources[].jsonData.defaultBucket = \"$3\"" /etc/grafana/provisioning/datasources/automatic.yml
yq -i -y ".datasources[].secureJsonData.token = \"$4\"" /etc/grafana/provisioning/datasources/automatic.yml