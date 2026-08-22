# Tech blog image generator with Amazon Bedrock

`generate_tech_blog_image.py` calls a real image-generation model on Amazon
Bedrock and saves the returned image as a PNG. It defaults to Amazon Nova
Canvas, a first-party Amazon image-generation model.

> **AWS availability:** Nova Canvas is currently marked as a legacy model and
> is scheduled for end of life on September 30, 2026. AWS may reject accounts
> that have not used it during the previous 30 days. This is an account/model
> restriction rather than a script error.

## Setup

Put your Bedrock bearer API key in `.env`:

```dotenv
BEDROCK_API_KEY=your_bedrock_api_key
AWS_REGION=us-east-1
```

The key must be an Amazon Bedrock API key, not an AWS access key ID or secret
access key. The IAM identity behind it must be allowed to call
`bedrock:InvokeModel`, and the selected model must be enabled in the region.

Run it with Python 3.9+:

```powershell
python .\generate_tech_blog_image.py `
  --title "How edge AI is changing mobile apps" `
  --summary "An accessible introduction to on-device inference." `
  --style "clean editorial, futuristic but realistic"
```

The image is saved as `tech_blog_image.png`, with accessibility text in
`tech_blog_image.alt.txt`, unless `--output` is provided.

To use Nova Canvas explicitly:

```powershell
python .\\generate_tech_blog_image.py `
  --region us-east-1 `
  --model "amazon.nova-canvas-v1:0" `
  --title "How edge AI is changing mobile apps" `
  --summary "An accessible introduction to on-device inference."
```
