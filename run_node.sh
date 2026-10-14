#!/bin/bash
NODE_ID=$1
PORT=$2

python backend/main.py
--node-id $NODE_ID
--port $PORT