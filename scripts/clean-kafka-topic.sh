#!/bin/bash

# Simple script to reset the offset of a consumer group in Kafka
# Wait to run this until the user approves the overall plan.

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <topic_name> <group_id>"
    echo "Example: $0 smap.collector.output analysis-consumer"
    exit 1
fi

TOPIC=$1
GROUP=$2

echo "Resetting offsets for group '$GROUP' on topic '$TOPIC' to the latest offset (skipping all unprocessed messages)..."

kubectl exec -it kafka-cluster-broker-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group "$GROUP" \
  --topic "$TOPIC" \
  --reset-offsets --to-latest --execute

echo "Done! The consumer will now only process newly incoming messages."
