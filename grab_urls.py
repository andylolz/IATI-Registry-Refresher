import sys
import json
from os.path import exists
from os import makedirs
from time import sleep

import requests


def request_with_backoff(*args, attempts=5, backoff=0.5, **kwargs):
    for attempt in range(1, attempts + 1):
        try:
            result = requests.request(*args, **kwargs)
            return result
        except requests.exceptions.ConnectionError:
            wait = attempt * backoff
            print(f'Rate limited! Retrying after {wait} seconds')
            sleep(wait)
    raise Exception(f'Failed after {attempts} attempts. Giving up.')


def main(args):
    skip_metadata = '--skip-metadata' in args
    if skip_metadata:
        print('Skipping metadata')

    # Loop through each page and save the URL end-points of the data files
    # You may need to set up an empty directory called "urls"
    print('Fetching:')
    api_root = 'https://iatiregistry.org/api/3/action'
    page = 1
    page_size = 1000

    tmpl = 'echo Downloading {package_name} : "{url}" ; ' + \
           'curl -L -k -f -s ' + \
           '-H "Accept: application/xhtml+xml, application/xml,*/*;q=0.9" ' + \
           '--retry 4 --retry-delay 10 -y 30 ' + \
           '-Y 1000 -A "IATI data dump" ' + \
           '--create-dirs -o data/{org_name}/{package_name}.xml ' + \
           '"{url}" 2>&1 >/dev/null ; exitcode=$? ; ' + \
           'test "$exitcode" != 0 && ' + \
           'echo $exitcode {org_name} {package_name} {url} > ' + \
           'logs/{package_name}.log\n'

    while True:
        print(f'Page {page}')
        start = page_size * (page - 1)
        result = request_with_backoff(
            'post',
            f'{api_root}/package_search',
            data={'start': start, 'rows': page_size}).json()['result']
        if result['results'] == []:
            break

        for package in result['results']:
            organization = package['organization']
            if package['resources'] == [] or not organization:
                continue
            package_name = package['name']
            url = package['resources'][0]['url']
            org_name = organization["name"]

            if not skip_metadata:
                metadata_filepath = f'metadata/{org_name}'
                if not exists(metadata_filepath):
                    makedirs(metadata_filepath)
                    org_metadata = request_with_backoff(
                        'post',
                        f'{api_root}/group_show',
                        data={'id': org_name}).json()['result']
                    org_metadata_file = f'{metadata_filepath}.json'
                    with open(org_metadata_file, 'w') as f:
                        json.dump(org_metadata, f)
                metadata_file = f'{metadata_filepath}/{package_name}.json'
                with open(metadata_file, 'w') as f:
                    json.dump(package, f)

            with open(f'urls/{org_name}', 'a') as f:
                f.write(f'{package_name} {url}\n')

            output = tmpl.format(
                org_name=org_name,
                package_name=package_name,
                url=url,
            )
            with open('downloads.curl', 'a') as f:
                f.write(output)
        page += 1

if __name__ == '__main__':
    main(sys.argv[1:])