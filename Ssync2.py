// handlers.go
func GetCurrentChunk(w http.ResponseWriter, r *http.Request) {
    userID := r.URL.Query().Get("user_id")
    currentTime, _ := strconv.Atoi(r.URL.Query().Get("current_time"))

    // Fetch sequence from Redis (cached) or DynamoDB
    sequence := fetchUserSequence(userID) 

    // Binary search to find the current chunk
    chunk, offset := binarySearch(sequence, currentTime)
    
    response := map[string]interface{}{
        "video_id": chunk.VideoID,
        "offset":   offset,
        "bitrates": chunk.Bitrates,
    }
    json.NewEncoder(w).Encode(response)
}

// binary_search.go
func binarySearch(sequence []VideoChunk, elapsedTime int) (VideoChunk, int) {
    low, high := 0, len(sequence)-1
    for low <= high {
        mid := (low + high) / 2
        chunk := sequence[mid]
        if chunk.Start <= elapsedTime && elapsedTime < chunk.Start+chunk.Duration {
            return chunk, elapsedTime - chunk.Start
        } else if elapsedTime < chunk.Start {
            high = mid - 1
        } else {
            low = mid + 1
        }
    }
    panic("Chunk not found")
}

#Deployment 
# Dockerfile
FROM golang:1.19
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . ./
RUN go build -o /metadata-service
EXPOSE 8080
CMD ["/metadata-service"]

#Directory: phase2-core/backend/lambda/resolve_chunk.py (Use AWS Lambda)
import boto3
import os
import json
from redis import Redis

redis = Redis(host=os.getenv("REDIS_HOST"))

def lambda_handler(event, context):
    user_id = event["queryStringParameters"]["user_id"]
    current_time = int(event["queryStringParameters"]["current_time"])
    
    # Fetch sequence from Redis
    sequence = redis.get(f"sequence:{user_id}")
    if not sequence:
        # Fallback to DynamoDB
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table("StreamSync-Sequences")
        sequence = table.get_item(Key={"user_id": user_id})["Item"]["sequence"]
    
    # Binary search logic (similar to Go implementation)
    chunk = binary_search(sequence, current_time)
    
    return {
        "statusCode": 200,
        "body": json.dumps(chunk)
    }

#Directory: phase2-core/cdn/pre-fetch-scripts/prefetch.js (CDN prefetching Lambda@Edge)
// Lambda@Edge viewer request handler
exports.handler = async (event) => {
    const request = event.Records[0].cf.request;
    const user_id = request.headers["x-user-id"][0].value;
    
    // Fetch user's sequence from Metadata Service
    const sequence = await fetchSequence(user_id);
    const currentChunk = getCurrentChunk(sequence, Date.now());
    
    // Pre-fetch next 3 chunks to CDN edge
    const nextChunks = sequence.slice(currentChunk.index + 1, currentChunk.index + 4);
    nextChunks.forEach(chunk => {
        prefetchFromS3(chunk.video_id);
    });
    
    return request;
};

async function prefetchFromS3(videoId) {
    // Trigger background fetch to CDN edge
    const s3 = new AWS.S3();
    await s3.getObject({
        Bucket: "streamsync-videos",
        Key: `videos/${videoId}/chunks/240p/chunk_0.ts`
    }).promise();
}
#Test API endpoint: GET /sequence?user_id=user1&current_time=3600 returns correct chunk.
#Invoke manually with test event Json:   Confirm response includes video_id, offset, and bitrates.
{ "queryStringParameters": { "user_id": "user1", "current_time": "3600" } 
}





