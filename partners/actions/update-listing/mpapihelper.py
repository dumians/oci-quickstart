import time
import requests
import base64
import yaml
import json
import os.path
import re


action_api_uri_dic = {}
access_token = ''
creds = {}
api_url = 'https://ocm-apis-cloud.oracle.com/'
picCompartmentOcid = 'ocid1.compartment.oc1..aaaaaaaaxrcshrhpq6exsqibhdzseghk4yjgrwxn3uaev6poaek2ooz4n7eq'
picTenancyId = '59030347'
api_headers = {}

class Config:

    listingVersionId = None
    artifactId = None
    packageVersionId = None
    termsId = None
    termsVersionId = None
    action = None
    access_token = None
    imageOcid = None
    credsFile = None
    metadataFile = None
    versionString = None

    def __init__(self, credsFile):
        if self.access_token is None:
            set_access_token(credsFile)

def bind_action_dic(config):
    global action_api_uri_dic
    action_api_uri_dic = {
        'get_listingVersions': 'appstore/publisher/v1/listings',
        'get_listingVersion': f'appstore/publisher/v1/applications/{config.listingVersionId}',
        'get_artifacts': 'appstore/publisher/v1/artifacts',
        'get_artifact': f'appstore/publisher/v1/artifacts/{config.artifactId}',
        'get_applications': 'appstore/publisher/v1/applications',
        'get_application': f'appstore/publisher/v1/applications/{config.listingVersionId}',
        'get_listing_packages': f'appstore/publisher/v2/applications/{config.listingVersionId}/packages',
        'get_application_packages': f'appstore/publisher/v2/applications/{config.listingVersionId}/packages',
        'get_application_package': f'appstore/publisher/v2/applications/{config.listingVersionId}/packages/{config.packageVersionId}',
        'get_terms': 'appstore/publisher/v1/terms',
        'get_terms_version': f'appstore/publisher/v1/terms/{config.termsId}/version/{config.termsVersionId}',
        'create_listing': f'appstore/publisher/v1/applications',
        'create_new_version': f'appstore/publisher/v1/applications/{config.listingVersionId}/version',
        'new_package_version': f'appstore/publisher/v2/applications/{config.listingVersionId}/packages/{config.packageVersionId}/version',
        'upload_icon': f'appstore/publisher/v1/applications/{config.listingVersionId}/icon',
    }

def set_access_token(credsFile):
    global access_token
    global creds
    global api_headers

    with open(credsFile, 'r') as stream:
        creds = yaml.safe_load(stream)

    auth_string = creds['client_id']
    auth_string += ':'
    auth_string += creds['secret_key']

    encoded = base64.b64encode(auth_string.encode('ascii'))
    encoded_string = encoded.decode('ascii')

    token_url = 'https://login.us2.oraclecloud.com:443/oam/oauth2/tokens?grant_type=client_credentials'

    auth_headers = {}
    auth_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    auth_headers['charset'] = 'UTF-8'
    auth_headers['X-USER-IDENTITY-DOMAIN-NAME'] = 'usoracle30650'
    auth_headers['Authorization'] = f'Basic {encoded_string}'

    r = requests.post(token_url, headers=auth_headers)

    access_token = json.loads(r.text).get('access_token')
    api_headers['charset'] = 'UTF-8'
    api_headers['X-Oracle-UserId'] = creds['user_email']
    api_headers['Authorization'] = f'Bearer {access_token}'

def sanitize_name(name):
    return re.sub('[^a-zA-Z0-9_\.\-\+ ]+', '', name)

def find_file(file_name):
    # github actions put files in a chroot jail, so we need to look in root
    file_name = file_name if os.path.isfile(file_name) \
        else '/{}'.format(file_name) if os.path.isfile('/{}'.format(file_name)) \
        else 'marketplace/{}'.format(file_name) if os.path.isfile('marketplace/{}'.format(file_name)) \
        else '/marketplace/{}'.format(file_name) if os.path.isfile('/marketplace/{}'.format(file_name)) \
        else file_name #return the original file name if not found so the open can throw the exception
    return file_name

def do_get_action(config):
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    r = requests.get(uri, headers=api_headers)
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json

def get_new_versionId(config):
    config.action = 'create_new_version'
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    api_headers['Content-Type'] = 'application/json'
    r = requests.post(uri, headers=api_headers)
    del api_headers['Content-Type']
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['entityId']

def update_version_metadata(config, newVersionId):
    config.action = 'get_listingVersion'
    config.listingVersionId = newVersionId
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    file_name = find_file('metadata.yaml')
    if not os.path.isfile(file_name):
        return f'metadata file metadata.yaml not found. skipping metadata update.'
    with open(file_name,  'r') as stream:
        metadata = yaml.safe_load(stream)

    updateable_items = ['longDescription','name','shortDescription','systemRequirements','tagLine','tags','usageInformation']

    for k in list(metadata.keys()):
        if k not in updateable_items:
            del metadata[k]

    body = json.dumps(metadata)

    api_headers['Content-Type'] = 'application/json'
    r = requests.patch(uri, headers=api_headers, data=body)
    del api_headers['Content-Type']
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    if 'message' in r_json:
        return r_json['message']
    else:
        return r.text

def get_packageId(config, newVersionId):
    config.action = 'get_application_packages'
    config.listingVersionId = newVersionId
    r = do_get_action(config)
    return r['items'][0]['Package']['id']

def get_new_packageVersionId(config, newVersionId, packageId):
    config.action = 'new_package_version'
    config.listingVersionId = newVersionId
    config.packageVersionId = packageId
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    api_headers['Content-Type'] = 'application/json'
    r = requests.patch(uri, headers=api_headers)
    del api_headers['Content-Type']
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['entityId']

def update_versioned_package_version(config, newPackageVersionId):
    time_stamp = str(time.ctime()).replace(':','')
    config.action = 'get_application_package'
    config.packageVersionId = newPackageVersionId
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    if config.imageOcid is None:
        service_type = 'OCIOrchestration'
    else:
        service_type = 'OCI'
    body = {}
    body['version'] = sanitize_name(config.versionString) + ' ' + time_stamp
    body['description'] = config.versionString
    body['serviceType'] = service_type
    payload = {'json': (None, json.dumps(body))}
    r = requests.put(uri, headers=api_headers, files=payload)
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['message']


def create_new_stack_artifact(config, fileName):
    time_stamp = str(time.ctime()).replace(':','')
    config.action = 'get_artifacts'
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    body={}
    body['name'] = sanitize_name(config.versionString) + ' ' + time_stamp
    body['artifactType'] = 'TERRAFORM_TEMPLATE'
    payload = {'json': (None, json.dumps(body))}
    index = fileName.rfind('/')
    name = fileName[index+1:]
    files = {'file': (name, open(fileName, 'rb'))}
    r = requests.post(uri, headers=api_headers, files=files, data=payload)
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['entityId']

def create_new_image_artifact(config, old_listing_artifact_version):
    time_stamp = str(time.ctime()).replace(':', '')
    config.action = 'get_artifacts'
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    if old_listing_artifact_version is not None:
        new_version = {key:old_listing_artifact_version[key] for key in ['name', 'artifactType', 'source', 'artifactProperties']}
        new_version['name'] = sanitize_name(config.versionString) + ' ' + time_stamp
        new_version['source']['uniqueIdentifier'] = config.imageOcid
        new_version['artifactType'] = 'OCI_COMPUTE_IMAGE'
    else:
        new_version = {}
        new_version['name'] = sanitize_name(config.versionString) + ' ' + time_stamp
        new_version['artifactType'] = 'OCI_COMPUTE_IMAGE'
        new_version['source'] = {}
        new_version['source']['regionCode'] = 'us-ashburn-1'
        new_version['source']['uniqueIdentifier'] = config.imageOcid
        new_version['artifactProperties'] = [{},{}]
        new_version['artifactProperties'][0]['artifactTypePropertyName'] = 'compartmentOCID'
        new_version['artifactProperties'][0]['value'] = picCompartmentOcid
        new_version['artifactProperties'][1]['artifactTypePropertyName'] = 'ociTenancyID'
        new_version['artifactProperties'][1]['value']  = picTenancyId

    api_headers['Content-Type'] = 'application/json'
    r = requests.post(uri, headers=api_headers, data=json.dumps(new_version))
    del api_headers['Content-Type']
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['entityId']

def associate_artifact_with_package(config, artifactId, newPackageVersionId):

    body = {}
    body['resources'] = [{}]
    body['resources'][0]['serviceType'] = 'OCIOrchestration' if config.imageOcid is None else 'OCI'
    body['resources'][0]['type'] = 'terraform' if config.imageOcid is None else 'ocimachineimage'
    body['resources'][0]['properties'] = [{}]
    body['resources'][0]['properties'][0]['name'] = 'artifact'
    body['resources'][0]['properties'][0]['value'] = artifactId
    body['resources'][0]['properties'][0]['valueProperties'] = [{}]
    body['resources'][0]['properties'][0]['valueProperties'][0]['name'] = 'name'
    body['resources'][0]['properties'][0]['valueProperties'][0]['value'] = sanitize_name(config.versionString)

    payload = {'json': (None, json.dumps(body))}
    config.action = 'get_application_package'
    config.packageVersionId = newPackageVersionId
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    r = requests.put(uri, headers=api_headers, files=payload)
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['message']

def submit_listing(config):
    autoApprove = 'true'
    while (True):
        config.action = 'get_listingVersion'
        bind_action_dic(config)
        apicall = action_api_uri_dic[config.action]
        uri = api_url + apicall
        body = {}
        body['action'] = 'submit'
        body['note'] = 'submitting new version'
        body['autoApprove'] = autoApprove
        api_headers['Content-Type'] = 'application/json'
        r = requests.patch(uri, headers=api_headers, data=json.dumps(body))
        del api_headers['Content-Type']
        if r.status_code > 299:
            print(r.text)
        r_json = json.loads(r.text)
        if 'message' in r_json:
            return r_json['message']
        if autoApprove == 'false':
            return 'this partner has not yet been approved for auto approval. please contact MP admin.'
        else:
            autoApprove = 'false'



def publish_listing(config):
    config.action = 'get_listingVersion'
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    body = {}
    body['action'] = 'publish'
    api_headers['Content-Type'] = 'application/json'
    r = requests.patch(uri, headers=api_headers, data=json.dumps(body))
    del api_headers['Content-Type']
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    if 'message' in r_json:
        return r_json['message']
    else:
        return 'Failed to auto-publish, please contact MP admin to maunaully approve listing.'

def create_new_listing(config):

    config.action = 'get_applications'
    file_name = find_file('metadata.yaml')
    with open(file_name, 'r') as stream:
        new_version = yaml.safe_load(stream)
        del new_version['listingId']
    if 'versionDetails' in new_version:
        vd = new_version['versionDetails']
        config.versionString = vd['versionNumber']
        if 'releaseDate' in vd:
            new_version['versionDetails']['releaseDate'] = str(new_version['versionDetails']['releaseDate'])
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    api_headers['Content-Type'] = 'application/json'
    body = json.dumps(new_version)
    r = requests.post(uri, headers=api_headers, data=body)
    del api_headers['Content-Type']
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['entityId']

def create_new_package(config, artifactId):

    body = {}
    body['version'] = sanitize_name(config.versionString)
    body['description'] = config.versionString
    body['serviceType'] = 'OCIOrchestration'
    body['resources'] = [{}]
    body['resources'][0]['serviceType'] = 'OCIOrchestration'
    body['resources'][0]['type'] = 'terraform'
    body['resources'][0]['properties'] = [{}]
    body['resources'][0]['properties'][0]['name'] = 'artifact'
    body['resources'][0]['properties'][0]['value'] = artifactId

    config.action = 'get_application_packages'
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    payload = {'json': (None, json.dumps(body))}
    r = requests.post(uri, headers=api_headers, files=payload)
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['message']

def upload_icon(config):
    config.action = 'upload_icon'
    bind_action_dic(config)
    apicall = action_api_uri_dic[config.action]
    uri = api_url + apicall
    file_name = find_file('icon.png')
    files = {'image': open(file_name, 'rb')}
    r = requests.post(uri, headers=api_headers, files=files)
    if r.status_code > 299:
        print(r.text)
    r_json = json.loads(r.text)
    return r_json['entityId']
