import boto3
import certbot.main
import datetime
import os
import raven
import subprocess

def read_and_delete_file(path):
	with open(path, 'r') as file:
		contents = file.read()
	os.remove(path)
	return contents

def provision_cert(email, domains):
	certbot.main.main([
		'certonly',                             # Obtain a cert but don't install it
		'-n',                                   # Run in non-interactive mode
		'--agree-tos',                          # Agree to the terms of service,
		'--email', email,                       # Email
		'--dns-route53',                        # Use dns challenge with route53
		'-d', domains,                          # Domains to provision certs for
		'--server', 'https://acme-v02.api.letsencrypt.org/directory',
		# Override directory paths so script doesn't have to be run as root
		'--config-dir', '/tmp/config-dir/',
		'--work-dir', '/tmp/work-dir/',
		'--logs-dir', '/tmp/logs-dir/',
  	])

	first_domain = domains.split(',')[0]
	path = '/tmp/config-dir/live/' + first_domain + '/'
	return {
		'certificate': read_and_delete_file(path + 'cert.pem'),
		'private_key': read_and_delete_file(path + 'privkey.pem'),
		'certificate_chain': read_and_delete_file(path + 'chain.pem')
  	}

def should_provision(domains):
	existing_cert = find_existing_cert(domains)
	if existing_cert:
		now = datetime.datetime.now(datetime.timezone.utc)
		not_after = existing_cert['Certificate']['NotAfter']
		return (not_after - now).days <= int(os.environ.get('DAYS_TO_EXPIRE', '30'))
	else:
		return True

def find_existing_cert(domains):
	domains = frozenset(domains.split(','))

	client = boto3.client('acm')
	paginator = client.get_paginator('list_certificates')
	iterator = paginator.paginate(PaginationConfig={'MaxItems':1000})

	sans = set()

	for page in iterator:
		for cert in page['CertificateSummaryList']:
			cert = client.describe_certificate(CertificateArn=cert['CertificateArn'])
			sans = frozenset(cert['Certificate']['SubjectAlternativeNames'])
		if sans.issubset(domains):
			return cert

	return None

def notify_via_sns(topic_arn, domains, certificate):
	process = subprocess.Popen(['openssl', 'x509', '-noout', '-text'],
		stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='utf8')
	stdout, stderr = process.communicate(certificate)

	client = boto3.client('sns')
	client.publish(TopicArn=topic_arn,
		Subject='Issued new LetsEncrypt certificate',
		Message='Issued new certificates for domains: ' + domains + '\n\n' + stdout,
	)

def upload_cert_to_acm(cert, domains):
	existing_cert = find_existing_cert(domains)
	certificate_arn = existing_cert['Certificate']['CertificateArn'] if existing_cert else None

	client = boto3.client('acm')
	if not certificate_arn:
		acm_response = client.import_certificate(
			Certificate=cert['certificate'],
			PrivateKey=cert['private_key'],
			CertificateChain=cert['certificate_chain']
		)
	else:
		acm_response = client.import_certificate(
			CertificateArn=certificate_arn,
			Certificate=cert['certificate'],
			PrivateKey=cert['private_key'],
			CertificateChain=cert['certificate_chain']
		)

	return None if certificate_arn else acm_response['CertificateArn']

def upload_cert_to_s3(cert, domains, bucket):
	first_domain = domains.split(',')[0]
	key_path = 'certbot/%s' % first_domain
	s3 = boto3.resource('s3')
	s3.Object(bucket, '%s/%s.crt' % (key_path, first_domain)).put(Body=cert['certificate'])
	s3.Object(bucket, '%s/%s.key' % (key_path, first_domain)).put(Body=cert['private_key'])
	s3.Object(bucket, '%s/%s.chain' % (key_path, first_domain)).put(Body=cert['certificate_chain'])

def handler(event, context):
	try:
		domains = os.environ.get('LETSENCRYPT_DOMAINS', None)
		if should_provision(domains):
			cert = provision_cert(os.environ.get('LETSENCRYPT_EMAIL', None), domains)
			upload_cert_to_acm(cert, domains)
			if os.environ.get('S3_BUCKET_NAME', None):
				upload_cert_to_s3(cert, domains, os.environ.get('S3_BUCKET_NAME', None))
			if os.environ.get('NOTIFICATION_SNS_ARN', None):
				notify_via_sns(os.environ.get('NOTIFICATION_SNS_ARN', None), domains, cert['certificate'])
	except:
		if os.environ.get('SENTRY_DSN', None):
			client = raven.Client(os.environ.get('SENTRY_DSN', None), transport=raven.transport.http.HTTPTransport)
			client.captureException()
		raise

if __name__ == '__main__':
	handler(None, None)
