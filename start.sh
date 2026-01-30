#!/bin/bash
# Kill existing processes
pkill -f streamlit
pkill -f cloudflared

# Remove old URL
rm -f tunnel_url.txt

# Start Streamlit in background
echo "Starting Streamlit..."
./venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &

# Wait for Streamlit to initialize
sleep 5

# Start Cloudflare Tunnel
echo "Starting Cloudflare Tunnel..."
# Use trycloudflare to get a random URL, redirect stderr where the URL appears to a file
./cloudflared tunnel --url http://localhost:8501 > tunnel.log 2>&1 &

# Wait for URL to be generated
echo "Waiting for Tunnel URL..."
limit=30
count=0
while [ $count -lt $limit ]; do
    url=$(grep -o 'https://.*\.trycloudflare\.com' tunnel.log | head -n 1)
    if [ ! -z "$url" ]; then
        echo "$url" > tunnel_url.txt
        echo "Tunnel URL found: $url"
        # Rerun streamlit to pick up the file? Streamlit auto-reloads on file change usually, 
        # but app.py reads file on run. Use touch to trigger reload if needed.
        touch app.py 
        break
    fi
    sleep 1
    count=$((count+1))
done

if [ -z "$url" ]; then
    echo "Failed to get Tunnel URL. Check tunnel.log."
fi

# Keep script running
wait
