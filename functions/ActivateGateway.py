import time
import json
import boto3
import shlex
import subprocess
import cfnresponse
from datetime import datetime
from dateutil import tz
ec2 = boto3.client('ec2')
gatewayClient = boto3.client('storagegateway')
def create(properties, physical_id):
    #instanceId = properties['InstanceId']
    instanceIP = properties['InstanceIP']
    instanceRegion = properties['InstanceRegion']
    gatewayName = properties['GatewayName']
    gatewayTimezone = properties['GatewayTimezone']
    zone=datetime.now(tz.gettz(gatewayTimezone)).strftime('%z')
    gatewayTimezoneOffset = f'{zone[0:3]}:{zone[3:5]}'
    '''
    instancestatuses = ec2.describe_instance_status(InstanceIds=[instanceId])['InstanceStatuses']
    while len(instancestatuses) <= 0:
        instancestatuses = ec2.describe_instance_status(InstanceIds=[instanceId])['InstanceStatuses']
        print(f'Waiting for Instance-{instanceId} to be launched ...')
        time.sleep(10)
    instancedetails = instancestatuses[0]['InstanceStatus']['Details'][0]['Status']
    systemstatus = instancestatuses[0]['SystemStatus']['Status']
    while instancedetails != 'passed' and systemstatus != 'ok':
        instancestatuses = ec2.describe_instance_status(InstanceIds=[instanceId])['InstanceStatuses']
        instancedetails = instancestatuses[0]['InstanceStatus']['Details'][0]['Status']
        systemstatus = instancestatuses[0]['SystemStatus']['Status']
        print(f'Waiting for Instance-{instanceId} to pass status check ...')
        time.sleep(30)                       
    '''
    print('Retrieving activation key ...')
    cmd = f"wget '{instanceIP}/?activationRegion={instanceRegion}'"
    command = shlex.split(cmd)
    activationKey=''
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT).decode()
        activationKey = output[output.find('activationKey=')+14:output.find('activationKey=')+43]
    except subprocess.CalledProcessError as e:
        output = e.output.decode()
    print(f'Activation Key={activationKey}')
    print('Activating storage gateway ...')
    gatewayARN = gatewayClient.activate_gateway(
        ActivationKey=activationKey,
        GatewayName=gatewayName,
        GatewayTimezone=f'GMT{gatewayTimezoneOffset}',
        GatewayRegion=instanceRegion,
        GatewayType='FILE_S3'
    )['GatewayARN']
    print(f'Gateway ARN = {gatewayARN}, Gateway Name = {gatewayName}')
    returnAttribute = {}
    returnAttribute['Arn'] = gatewayARN
    returnAttribute['Name'] = gatewayName
    returnAttribute['Action'] = 'CREATE'
    return cfnresponse.SUCCESS, gatewayARN, returnAttribute
def update(properties, physical_id):
    gatewayARN = physical_id
    gatewayName = properties['GatewayName']
    gatewayTimezone = properties['GatewayTimezone']
    zone=datetime.now(tz.gettz(gatewayTimezone)).strftime('%z')
    gatewayTimezoneOffset = f'{zone[0:3]}:{zone[3:5]}'
    print(f'Updating storage gateway {gatewayARN} ...')
    gatewayName = gatewayClient.update_gateway_information(
        GatewayARN=gatewayARN,                        
        GatewayName=gatewayName,
        GatewayTimezone=f'GMT{gatewayTimezoneOffset}'
    )['GatewayName'] 
    print(f'Gateway ARN = {gatewayARN}, Gateway Name = {gatewayName}')   
    returnAttribute = {}
    returnAttribute['Arn'] = gatewayARN
    returnAttribute['Name'] = gatewayName                                                                   
    returnAttribute['Action'] = 'UPDATE'
    return cfnresponse.SUCCESS, gatewayARN, returnAttribute
def delete(properties, physical_id):
    gatewayARN = physical_id
    print(f'Deleting storage gateway {gatewayARN} ...')
    gatewayName = properties['GatewayName']
    gatewayARN = gatewayClient.delete_gateway(
        GatewayARN=gatewayARN
    )['GatewayARN']                        
    returnAttribute = {}
    returnAttribute['Arn'] = gatewayARN
    returnAttribute['Name'] = gatewayName                                                                   
    returnAttribute['Action'] = 'DELETE'
    return cfnresponse.SUCCESS, gatewayARN, returnAttribute
def handler(event, context):
    print('Received event: ' + json.dumps(event))
    status = cfnresponse.FAILED
    new_physical_id = None
    try:
        properties = event.get('ResourceProperties')
        physical_id = event.get('PhysicalResourceId')
        status, new_physical_id, returnAttribute = {
            'Create': create,
            'Update': update,
            'Delete': delete
        }.get(event['RequestType'], lambda x, y: (cfnresponse.FAILED, None))(properties, physical_id)
    except Exception as e:
        print('Exception: ' + e)
        status = cfnresponse.FAILED
    finally:
        cfnresponse.send(event, context, status, returnAttribute, new_physical_id)