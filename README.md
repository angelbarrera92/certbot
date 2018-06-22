# CertBot
![CertBot](./assets/logo.png)

This bot is in responsible for auto renewing SSL/TLS certificates for domains *(including wildcards)*.

## Configuration
This bot is executed by reading certain environment variables to request the certificates. These variables are:
- `LETSENCRYPT_DOMAINS` *(Required)*: List of domains separated by commas. Example: `example.com,*.example.com`
- `LETSENCRYPT_EMAIL` *(Required)*: Email to which certificates are registered in letsencrypt.
- `NOTIFICATION_SNS_ARN` *(Optional)*: ARN of the SNS topic used to send emails of the result of the certificate generation.
- `SENTRY_DSN` *(Optional)*: URL use to send process errors to Sentry.
- `S3_BUCKET_NAME` *(Optional)*: S3 Bucket to upload the certificates. The keys should looks like S3_BUCKET_NAME/certbot/domain_name/domain_name.`crt`||`key`||`chain`.
- `DAYS_TO_EXPIRE` *(Optional)*: Maximun number of days before certificates expire to renew the it. Default value: `30`.

## Execute on premises
To run this script locally we must have several requirements:
- Python 3.6 installed
- virtualenv
- AWS execution permissions (acm resources, route53, s3...)

Run the following commands *(once this repository is cloned)*:
```
$ virtualenv -p python3 venv
$ source venv/bin/activate
$ pip install certbot certbot-dns-route53 raven
$ export AWS_REGION=eu-central-1
$ export AWS_DEFAULT_REGION=eu-central-1
$ export LETSENCRYPT_DOMAINS=example.com,*.example.com
$ export LETSENCRYPT_EMAIL=devops@example.com
$ python main.py
```

## To be taken into consideration
Certificates are only renewed when they are 30 days to expire.

### Based on
We have developed this pipeline based on [this blog post](https://arkadiyt.com/2018/01/26/deploying-effs-certbot-in-aws-lambda/) but with some changes.
- We do not use **AWS Lambda**: Instead we use the planned travis pipelines.
- We have modified the python script ([`main.py`](./main.py)) to use version two of the letsencrypt api.
