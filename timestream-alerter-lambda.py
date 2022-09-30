#
# Adapted from the AWS blog post "Trigger notifications on time series data with Amazon Timestream"
# https://aws.amazon.com/blogs/database/trigger-notifications-on-time-series-data-with-amazon-timestream/
#

import boto3
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUCCULENTPI_DATABASE = os.environ.get("SUCCULENTPI_DATABASE", "")
SUCCULENTPI_TABLE = os.environ.get("SUCCULENTPI_TABLE", "")
VALUE_NAME = os.environ.get("VALUE_NAME", "")
SNS_TOPIC = os.environ.get("SNS_TOPIC", "")

logger.info("SUCCULENTPI_DATABASE: {} SUCCULENTPI_TABLE: {} ".format(SUCCULENTPI_DATABASE, SUCCULENTPI_TABLE))

QUERY =  f'SELECT * FROM "{SUCCULENTPI_DATABASE}"."{SUCCULENTPI_TABLE}" WHERE (time between ago(5m) and now()) and (measure_name = \'{VALUE_NAME}\')'
 
def lambda_handler(event, context):
    logger.debug("event:\n{}".format(json.dumps(event, indent=2)))

    records_sensordata = []
    records_ggmetrics = []

    try:
        c_ts_query = boto3.client('timestream-query')
        sns = boto3.client('sns')

        response = c_ts_query.describe_endpoints()
        logger.info("response describe_endpoints: {}".format(response))
        if not SUCCULENTPI_DATABASE or not SUCCULENTPI_TABLE or len(SUCCULENTPI_DATABASE)==0 or len(SUCCULENTPI_TABLE)==0:
            logger.warn(f"database or table for SucculentPi not defined: SUCCULENTPI_DATABASE: {SUCCULENTPI_DATABASE} SUCCULENTPI_TABLE: {SUCCULENTPI_TABLE}")
            return {"status": "warn", "message": "database or table for succulentpi not defined"}
        response = c_ts_query.query(QueryString=QUERY)
        if not response :
            return {"status": "error", "message": "Empty response"}
        ret_val = {"status": "success"}
        ret_val["records size"] = "{}" .format(len(response['Rows']))
        result = int(ret_val["records size"]);
    
    except Exception as e:
        logger.error("{}".format(e))
        return {"status": "query error", "message": "{}".format(e)}   

    try:
        logger.info(f"Number of Rows: {result}")
        logger.info(f"Value of {VALUE_NAME}: {response['Rows'][0]['Data'][4]['ScalarValue']}")
        
        if result < 1:
            logger.info("Sending Missing Data SNS Message...")
            sns.publish(TopicArn=SNS_TOPIC, Message="ALERT: The latest SucculentPi sensor data is missing", Subject="Alert: Sensor Data Missing")
            
        elif result > 0 and (int(response['Rows'][0]['Data'][4]['ScalarValue']) < 0 or int(response['Rows'][0]['Data'][4]['ScalarValue']) > 950):
            logger.info("Sending Data Out Of Range SNS Message...")
            sns.publish(TopicArn=SNS_TOPIC, Message=f"ALERT: The SucculentPi sensor data is out of range: {VALUE_NAME} = {response['Rows'][0]['Data'][4]['ScalarValue']}", Subject="Alert: Sensor Data Out of Range")
        
        elif result > 0:
            logger.info("Results OK")
            return {"status": "success", "message": "Results OK"}

    except Exception as e:
        logger.error("{}".format(e))
        return {"status": "error sending notification", "message": "{}".format(e)}
        
     