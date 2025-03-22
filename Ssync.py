# Configure AWS provider : Phase 1

provider "aws" {
  region = "us-east-1"
}
# S3 Bucket for Video Storage
resource "aws_s3_bucket" "video_storage" {
  bucket = "streamsync-videos"
  acl    = "private"

  lifecycle_rule {
    id      = "glacier-transition"
    enabled = true

    transition {
      days          = 30
      storage_class = "GLACIER"
    }
  }

  versioning {
    enabled = true
  }
}

# DynamoDB for Metadata Storage
resource "aws_dynamodb_table" "user_sequences" {
  name           = "StreamSync-Sequences"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }
}

# EC2/Kubernetes Nodes (Time Sync)
resource "aws_iam_role" "ntp_sync_role" {
  name = "StreamSync-NTP-Sync"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

# Attach AWS Time Sync Policy
resource "aws_iam_role_policy_attachment" "time_sync" {
  role       = aws_iam_role.ntp_sync_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonTimeSyncServiceFullAccess"
}

# Outputs
output "s3_bucket" {
  value = aws_s3_bucket.video_storage.id
}

output "dynamodb_table" {
  value = aws_dynamodb_table.user_sequences.name
}


#to Deploy
terraform init
terraform plan -out=phase1.tfplan
terraform apply phase1.tfplan

#Metadata Schema (Protobuf)
syntax = "proto3";

package streamsync;

message VideoChunk {
  string video_id = 1;
  int32 start = 2;        // Start time (seconds since 00:00)
  int32 duration = 3;     // Chunk duration (seconds)
  repeated string bitrates = 4; // Available bitrates (e.g., "240p", "720p")
}

message UserSequence {
  string user_id = 1;
  repeated VideoChunk sequence = 2;
}

#Compile the schema to ensure correctness:

protoc --python_out=. metadata-schema.proto

#Insert a sample UserSequence into DynamoDB using AWS CLI:
aws dynamodb put-item --table-name StreamSync-Sequences --item '{"user_id": {"S": "user1"}, "sequence": {"L": []}}'

