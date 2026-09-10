## aws Dynamodb schema 
   aws dynamodb create-table `
        --table-name zerodaily-articles `
        --region us-east-1 `
        --billing-mode PAY_PER_REQUEST `
        --attribute-definitions `
            AttributeName=id,AttributeType=S `
            AttributeName=category,AttributeType=S `
            AttributeName=published_at,AttributeType=S `
            AttributeName=feed_bucket,AttributeType=S `
        --key-schema `
            AttributeName=id,KeyType=HASH `
        --global-secondary-indexes `
            "[
                {
                    \"IndexName\": \"CategoryIndex\",
                    \"KeySchema\": [
                        {\"AttributeName\": \"category\", \"KeyType\": \"HASH\"},
                        {\"AttributeName\": \"published_at\", \"KeyType\": \"RANGE\"}
                    ],
                    \"Projection\": {\"ProjectionType\": \"ALL\"}
                },
                {
                    \"IndexName\": \"GlobalFeedIndex\",
                    \"KeySchema\": [
                        {\"AttributeName\": \"feed_bucket\", \"KeyType\": \"HASH\"},
                        {\"AttributeName\": \"published_at\", \"KeyType\": \"RANGE\"}
                    ],
                    \"Projection\": {\"ProjectionType\": \"ALL\"}
                }
            ]"