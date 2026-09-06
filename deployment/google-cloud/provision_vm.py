"""Provision one isolated Aureon host; execute in authenticated Cloud Shell."""
import json, pathlib, subprocess

PROJECT = 'aureon-trading'
ZONE = 'europe-west1-b'
VM = 'aureon-sero-20260906'
NETWORK = 'aureon-sero-network'
SUBNET = 'aureon-sero-europe-west1'
HERE = pathlib.Path(__file__).resolve().parent

def gc(*args, check=True):
    return subprocess.run(['gcloud', *args, '--project='+PROJECT, '--quiet'], check=check, text=True, capture_output=True)

def exists(*args):
    result = gc(*args, '--format=json', check=False)
    if result.returncode == 0:
        return json.loads(result.stdout)
    if 'not found' in result.stderr.lower() or 'was not found' in result.stderr.lower():
        return None
    raise RuntimeError(result.stderr)

if exists('compute', 'networks', 'describe', NETWORK) is None:
    gc('compute', 'networks', 'create', NETWORK, '--subnet-mode=custom')
if exists('compute', 'networks', 'subnets', 'describe', SUBNET, '--region=europe-west1') is None:
    gc('compute', 'networks', 'subnets', 'create', SUBNET, '--network='+NETWORK, '--region=europe-west1', '--range=10.40.0.0/24')
if exists('compute', 'firewall-rules', 'describe', 'aureon-sero-iap-ssh') is None:
    gc('compute', 'firewall-rules', 'create', 'aureon-sero-iap-ssh', '--network='+NETWORK,
       '--direction=INGRESS', '--action=ALLOW', '--rules=tcp:22', '--source-ranges=35.235.240.0/20', '--target-tags=aureon-sero-iap')
current = exists('compute', 'instances', 'describe', VM, '--zone='+ZONE)
if current is None:
    gc('compute', 'instances', 'create', VM, '--zone='+ZONE, '--machine-type=e2-standard-2',
       '--image-family=debian-12', '--image-project=debian-cloud', '--boot-disk-size=50GB',
       '--boot-disk-type=pd-balanced', '--no-boot-disk-auto-delete', '--network='+NETWORK, '--subnet='+SUBNET,
       '--no-service-account', '--no-scopes', '--tags=aureon-sero-iap', '--shielded-secure-boot',
       '--metadata=block-project-ssh-keys=true', '--labels=application=aureon-sero,mode=deployment-hold',
       '--metadata-from-file=startup-script='+str(HERE/'bootstrap-vm.sh'))
    current = exists('compute', 'instances', 'describe', VM, '--zone='+ZONE)
assert current['machineType'].endswith('/e2-standard-2')
assert current['networkInterfaces'][0]['network'].endswith('/'+NETWORK)
assert not current.get('serviceAccounts')
assert current['disks'][0]['autoDelete'] is False
receipt = {'project': PROJECT, 'name': VM, 'zone': ZONE, 'status': current['status'], 'id': current['id'],
           'machine_type': 'e2-standard-2', 'disk_gb': current['disks'][0]['diskSizeGb'], 'boot_disk_auto_delete': False,
           'service_accounts': [], 'network': NETWORK, 'ssh_ingress': 'Google IAP only',
           'console_url': f'https://console.cloud.google.com/compute/instancesDetail/zones/{ZONE}/instances/{VM}?project={PROJECT}'}
(HERE/'vm-receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
