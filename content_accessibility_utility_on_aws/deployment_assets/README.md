# Managed Accessibility Pipeline — deployment

These files were written by `content-accessibility-utility-on-aws init-pipeline`.
They deploy an event-driven pipeline: a document uploaded to S3 triggers a
Lambda that invokes an Amazon Bedrock AgentCore Runtime, which converts (PDF),
audits, and agent-remediates the content and writes the accessible result back
to S3.

```
pdf/<name>.pdf            -> convert (PDF->HTML bundle) -> html/<name>/manifest.json
html/<name>.html | .zip   -> audit + agent-remediate     -> accessible/<name>/
html/<name>/manifest.json -> (auto, from convert)         -> accessible/<name>/
```

## Files

| File | Purpose |
|------|---------|
| `agentcore_app.py` | AgentCore Runtime entrypoint (the pipeline) |
| `requirements.txt` | Runtime container deps (installs the published package `[agent]` extra) |
| `template.yaml` | SAM stack: input bucket + S3 notification, DynamoDB job table, trigger Lambda, IAM |
| `trigger_lambda/handler.py` | Thin S3 -> InvokeAgentRuntime router |

## Prerequisites

- AWS credentials for an account where Amazon Bedrock AgentCore is available.
- The AgentCore CLI and SAM CLI:
  ```bash
  pip install bedrock-agentcore-starter-toolkit aws-sam-cli
  ```
- An execution role for the runtime with permissions for Bedrock (models + Data
  Automation), AgentCore Browser (`StartBrowserSession`/`StopBrowserSession`),
  S3 (your pipeline bucket), and DynamoDB (the job table). See the guide.
- A Bedrock Data Automation project configured for HTML output (only needed if
  you process PDFs).

## Deploy

```bash
# 1. Deploy the runtime (builds an ARM64 image in the cloud, no local Docker).
agentcore configure --entrypoint agentcore_app.py --name a11y_pipeline \
  --requirements-file requirements.txt --region <region>
agentcore launch
#    Note the runtime ARN it prints.

# 2. Deploy the S3 + Lambda + DynamoDB stack, passing the runtime ARN.
sam deploy --guided \
  --parameter-overrides \
    AgentRuntimeArn=<runtime-arn> \
    InputBucketName=<globally-unique-bucket-name>
```

Set the runtime's BDA config (for the PDF path) at launch time:

```bash
agentcore launch --env BDA_S3_BUCKET=<bucket> --env BDA_PROJECT_ARN=<bda-project-arn>
```

## Use

```bash
aws s3 cp report.pdf   s3://<bucket>/pdf/report.pdf     # PDF  -> convert -> audit -> accessible/
aws s3 cp page.html    s3://<bucket>/html/page.html     # HTML -> audit -> accessible/
aws s3 cp site.zip     s3://<bucket>/html/site.zip      # zip  -> audit -> accessible/
```

Results appear under `s3://<bucket>/accessible/<name>/`. Per-document status is
tracked in the DynamoDB job table.

See the full guide: https://github.com/awslabs/content-accessibility-utility-on-aws/blob/main/docs/rendered_agent_guide.md
