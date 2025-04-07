import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from botocore.client import Config
import asyncio
import aioboto3

load_dotenv()
aws_access_key = os.getenv("ACCESS")
aws_secret_key = os.getenv("SECACCESS")
bucket = os.getenv("bucket")
region = os.getenv("region")

s3 = boto3.resource("s3")

def generate_presigned_url(s3, client, method, expires_in):
    try:
        url = s3.generate_presigned_url(
            ClientMethod=client, Params=method, ExpiresIn=expires_in
        )
    except ClientError as err: 
        print(err)
        raise
    return url


# prefix = "0/"
# client = boto3.client("s3")

# def list_buckets_items():
#     ls = []
#     response = client.list_objects_v2(
#         Bucket=bucket,
#         Prefix="0/"
#     )
#     for content in response.get("Contents", []):
#         ls.append(content["Key"])
#     url = generate_presigned_url(client, "get_object", {"Bucket": bucket, "Key": ls[0]}, 1000)
#     print(url)

# list_buckets_items()


async def get_demo_from_s3():
    demo_list = []
    prefix = "0/"
    session = aioboto3.Session()
    async with session.client('s3', aws_access_key_id=aws_access_key,
                             aws_secret_access_key=aws_secret_key, 
                             region_name=region, 
                             config=Config(signature_version='s3v4')) as s3_client:

        try:
            resp = await s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )
            for content in resp.get("Contents", []):
                demo_list.append(content["Key"])
            return demo_list
        except Exception as e:
            print(f"Error upload file to S3 bucket: {e}")
out = get_demo_from_s3()
res = asyncio.run(out)
print(res)