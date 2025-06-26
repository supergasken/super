#!/usr/bin/env python3

import requests, time
from argparse import ArgumentParser
from rich import print as rprint
from rich.console import Console
from rich.text import Text
from rich.table import Table

parser = ArgumentParser()
parser.add_argument('-n', help='name', default='kvm', type=str)
parser.add_argument('-r', help='region', default='nyc3', type=str)
parser.add_argument('-s', help='size', default='s-4vcpu-8gb', type=str)
parser.add_argument('-i', help='image', default='ubuntu-22-04-x64', type=str)
parser.add_argument('-api', help='api key', default=None, type=str)
parser.add_argument('-total', help='total number of droplets to create', default=1, type=int)
parser.add_argument('--images', help='check available images', default=False, action='store_true')
parser.add_argument('--region', help='check available region', default=False, action='store_true')
parser.add_argument('--check', help='check available vps', default=False, action='store_true')
parser.add_argument('--delete', help='delete droplet by ip/ delete all', default=None, type=str)
parser.add_argument('--reboot', help='reboot droplet by ip', default=None, type=str)
parser.add_argument('--power', type=str, help='Power cycle a droplet/ hard reboot')
args = parser.parse_args()
console = Console()

passwd = 'inipass123'
startup_script = f'''
#cloud-config
runcmd:
  - echo "root:inipass123" | chpasswd
  - sed -i "s/#PermitRootLogin prohibit-password/PermitRootLogin yes/" /etc/ssh/sshd_config
  - sed -i "s/PasswordAuthentication no/PasswordAuthentication yes/" /etc/ssh/sshd_config
  - echo "PasswordAuthentication yes" > /etc/ssh/sshd_config.d/50-cloud-init.conf
  - service sshd restart
'''

url = 'https://api.digitalocean.com/v2'
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {args.api}',
}

def check_available_region():
    res = requests.get(f'{url}/regions', headers=headers)
    print([i['slug'] for i in res.json()['regions'] if i['available']])

def add_ssh_key():
    try:
        data = {
            'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAABJQAAAQBYF43pRId6iCnEJOLyCcnJeuCaYYWrBGeGU6izDFi9Iz2aYRR3K9e+kQsOj6Ptn8xc0xLzH/MXyiUhmIvJUwO6OiAxUpuZ9cquo2JI8EKuClzIF2KCtMz+ttC1xZZvq2qA3JwLEAhD/XsUR6v3DuSn+VmveTkrtP8EcpYDfVYPScyqLFelnYdDgqagGhFRSaGmG3IO6BZflf/UXJUaD9CPY25LhscIXeHSyRsbCYgTEZ2nOIRlzTVpCReJzcCTkj7MM7cFbZNx8jw228MXbgD+kOV56plQjWdawiLeG/bEANfblNirZdvt24K15q6JQ4/He31tJm8BuBkYTvj6PuWT rsa-key-20191121',
            'name': 'key1',
        }
        res = requests.post(f'{url}/account/keys', headers=headers, json=data)
        return res.json()['ssh_key']['fingerprint']
    except:
        pass
    return None

def get_ssh_key():
    try:
        with requests.get(f'{url}/account/keys?page=1&per_page=100', headers=headers) as response:
            data = response.json()
            for item in data['ssh_keys']:
                return item['fingerprint']
    except:
        pass
    return None

def get_droplet_data(ip=None):
    try:
        with requests.get(f'{url}/droplets?page=1&per_page=100', headers=headers) as response:
            data = response.json()
            droplets_info = []

            if not ip:
                for item in data['droplets']:
                    droplet_info = {
                        'name': item['name'],
                        'ip_addresses': [
                            item['networks']['v4'][0]['ip_address'],
                            item['networks']['v4'][1]['ip_address']
                        ],
                        'status': item['status']
                    }
                    droplets_info.append(droplet_info)

            else:
                for item in data['droplets']:
                    if ip in [item['networks']['v4'][0]['ip_address'], item['networks']['v4'][1]['ip_address']]:
                        return item['id']

            return droplets_info

    except Exception as e:
        print(e)
        return None

def delete_droplet(ip):
    if ip.lower() == 'all':
        droplets = get_droplet_data()
        for droplet in droplets:
            droplet_id = get_droplet_data(droplet['ip_addresses'][0])
            res = requests.delete(f'{url}/droplets/{droplet_id}', headers=headers)
            if res.status_code == 204:
                console.log(f"[green]Successfully deleted {droplet['name']}[/green]")
            else:
                console.log(f"[red][!] Error deleting {droplet['name']}[/red]")
    else:
        droplet_id = get_droplet_data(ip)
        res = requests.delete(f'{url}/droplets/{droplet_id}', headers=headers)
        if res.status_code == 204:
            console.log(f"[green]Successfully deleted {ip}[/green]")
        else:
            console.log(f"[red][!] Error deleting {ip}[/red]")

def add_droplet():
    ssh_key = get_ssh_key()
    if not ssh_key:
        ssh_key = add_ssh_key()
    for i in range(args.total):
        data = {
            'name': f"{args.n}{i+1}",
            'region': args.r,
            'size': args.s,
            'image': args.i,
            'ssh_keys': [ssh_key],
            'backups': False,
            'ipv6': False,
            'monitoring': False,
            'tags': [],
            'user_data': startup_script,
            'with_droplet_agent': False,
        }
        res = requests.post(f'{url}/droplets', headers=headers, json=data)
        if res.status_code == 202:
            console.log(f"[green]Successfully created droplet {args.n}{i+1}: {res.json()['droplet']['id']}[/green]")
        else:
            console.log(f"[red]Failed to create droplet {args.n}{i+1}[/red]")

def get_droplet_status(droplet_id):
    res = requests.get(f'{url}/droplets/{droplet_id}', headers=headers)
    if res.status_code == 200:
        return res.json()['droplet']['status']
    else:
        print(f"Failed to get status of droplet with ID {droplet_id}. Response: {res.text}")
        return None
    
def reboot_droplet(ip):
    res = requests.get(f'{url}/droplets', headers=headers)
    droplets = res.json()['droplets']
    droplet_id = None
    for droplet in droplets:
        for network in droplet['networks']['v4']:
            if network['ip_address'] == ip:
                droplet_id = droplet['id']
                break
        if droplet_id is not None:
            break

    if droplet_id is None:
        print(f"No droplet found with IP {ip}")
        return

    res = requests.post(f'{url}/droplets/{droplet_id}/actions', headers=headers, json={"type": "reboot"})

    if res.status_code == 201:
        print(f"Reboot command sent to droplet with IP {ip}")
        time.sleep(10) 
        status = get_droplet_status(droplet_id)
        print(f"Droplet status: {status}")
    else:
        print(f"Failed to reboot droplet with IP {ip}. Response: {res.text}")

def power_cycle_droplet(ip):
    res = requests.get(f'{url}/droplets', headers=headers)
    droplets = res.json()['droplets']
    droplet_id = None
    for droplet in droplets:
        for network in droplet['networks']['v4']:
            if network['ip_address'] == ip:
                droplet_id = droplet['id']
                break
        if droplet_id is not None:
            break

    if droplet_id is None:
        print(f"No droplet found with IP {ip}")
        return

    res = requests.post(f'{url}/droplets/{droplet_id}/actions', headers=headers, json={"type": "power_cycle"})

    if res.status_code == 201:
        print(f"Power cycle command sent to droplet with IP {ip}")
    else:
        print(f"Failed to power cycle droplet with IP {ip}. Response: {res.text}")

def check_available_images():
    res = requests.get(f'{url}/images?per_page=200', headers=headers)
    images = res.json()['images']
    sorted_images = sorted(images, key=lambda image: image['slug'])
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Slug")
    table.add_column("Distribution")
    table.add_column("Name")
    for image in sorted_images:
        table.add_row(image['slug'], image['distribution'], image['name'])
    console.print(table)

if __name__ == '__main__':
    try:
        if args.region:
            check_available_region()
        elif args.check:
            droplets_info = get_droplet_data()

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name")
            table.add_column("IP Addresses")
            table.add_column("Status")

            for droplet_info in droplets_info:
                droplet_name = droplet_info['name']
                droplet_ips = ', '.join(droplet_info['ip_addresses'])
                droplet_status = droplet_info['status']
                status_indicator = '[green]\u25CF[/green]' if droplet_status == 'active' else '[red]\u25CF[/red]'
                table.add_row(droplet_name, droplet_ips, f"{status_indicator} {droplet_status}")

            console.print(table)

            console.print('=' * 30)

            root_output = []
            for droplet_info in droplets_info:
                root_output.append(f"root:{passwd}||{droplet_info['ip_addresses'][1]}:22")

            console.print('\n'.join(root_output))

        elif args.images:
            check_available_images()
        elif args.delete:
            delete_droplet(args.delete)
        elif args.reboot:
            reboot_droplet(args.reboot)
        elif args.power:
            power_cycle_droplet(args.power)
        else:
            add_droplet()
    except Exception as e:
        print(e)
